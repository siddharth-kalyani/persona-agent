"""Eval runner: drafts every case with a pluggable drafter and scores it.

    uv run python -m vanimo.evals --dataset evals/datasets/synthetic_v0.jsonl --drafter reference

Drafters: `reference` (upper bound, sanity check), `brief` (lower-bound baseline),
`bedrock` (a plain Haiku prompt; the real drafting service plugs in here in M3).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from vanimo.evals.dataset import EvalCase, load_jsonl
from vanimo.evals.metrics import Gate, bucket, edit_ratio

Drafter = Callable[[EvalCase], Awaitable[str]]


@dataclass(frozen=True)
class CaseResult:
    id: str
    slice: str
    edit_ratio: float
    bucket: str


@dataclass(frozen=True)
class SliceSummary:
    slice: str
    cases: int
    send_without_edit: float
    light_or_better: float
    mean_edit_ratio: float


@dataclass(frozen=True)
class Report:
    drafter: str
    cases: int
    send_without_edit: float
    light_or_better: float
    mean_edit_ratio: float
    gate_passed: bool
    slices: list[SliceSummary]
    results: list[CaseResult]


def _summary(name: str, results: list[CaseResult]) -> SliceSummary:
    n = len(results)
    return SliceSummary(
        slice=name,
        cases=n,
        send_without_edit=round(sum(r.bucket == "sent_as_is" for r in results) / n, 3),
        light_or_better=round(sum(r.bucket != "heavy_edit" for r in results) / n, 3),
        mean_edit_ratio=round(sum(r.edit_ratio for r in results) / n, 3),
    )


async def run(cases: list[EvalCase], drafter: Drafter, name: str, *, concurrency: int = 4) -> Report:
    if not cases:
        raise ValueError("no eval cases")
    sem = asyncio.Semaphore(concurrency)

    async def one(case: EvalCase) -> CaseResult:
        async with sem:
            draft = await drafter(case)
        ratio = edit_ratio(draft, case.reference_sent_l1)
        return CaseResult(id=case.id, slice=case.slice, edit_ratio=round(ratio, 4), bucket=bucket(ratio))

    results = await asyncio.gather(*(one(c) for c in cases))
    by_slice: dict[str, list[CaseResult]] = defaultdict(list)
    for r in results:
        by_slice[r.slice].append(r)
    overall = _summary("all", list(results))
    return Report(
        drafter=name,
        cases=overall.cases,
        send_without_edit=overall.send_without_edit,
        light_or_better=overall.light_or_better,
        mean_edit_ratio=overall.mean_edit_ratio,
        gate_passed=Gate().passes(overall.send_without_edit, overall.light_or_better),
        slices=[_summary(k, v) for k, v in sorted(by_slice.items())],
        results=list(results),
    )


async def reference_drafter(case: EvalCase) -> str:
    return case.reference_sent_l1


async def brief_drafter(case: EvalCase) -> str:
    return case.brief


def bedrock_drafter() -> Drafter:
    from vanimo.config import get_settings
    from vanimo.llm.router import LlmClient, ModelRouter

    settings = get_settings()
    router = ModelRouter(settings)
    llm = LlmClient(settings, router)
    system = (
        "You draft a message for the user. Write only the message text, in plain text. "
        "Placeholders like ⟦PERSON_1⟧ stand for real names; keep them exactly as given."
    )

    async def draft(case: EvalCase) -> str:
        prompt = f"Thread so far:\n{case.context_l1}\n\nWhat I want to say: {case.brief}\n\nDraft my message."
        parts = [t async for t in llm.stream_text(model=router.model_for("default"), system=system, user_text=prompt)]
        return "".join(parts)

    return draft


def to_markdown(report: Report) -> str:
    lines = [
        f"# Eval report — drafter `{report.drafter}`",
        "",
        f"Cases: {report.cases} · send-without-edit: {report.send_without_edit:.0%} · "
        f"light-or-better: {report.light_or_better:.0%} · mean edit ratio: {report.mean_edit_ratio:.3f} · "
        f"MVP gate: {'PASS' if report.gate_passed else 'FAIL'}",
        "",
        "| Slice | Cases | Send without edit | Light or better | Mean edit ratio |",
        "|---|---|---|---|---|",
    ]
    lines += [
        f"| {s.slice} | {s.cases} | {s.send_without_edit:.0%} | {s.light_or_better:.0%} | {s.mean_edit_ratio:.3f} |"
        for s in report.slices
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vanimo.evals")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--drafter", choices=["reference", "brief", "bedrock"], default="reference")
    parser.add_argument("--out", type=Path, help="write the JSON report here")
    parser.add_argument("--fail-on-gate", action="store_true", help="exit 1 when the MVP gate fails (release gate)")
    args = parser.parse_args(argv)

    drafters: dict[str, Callable[[], Drafter]] = {
        "reference": lambda: reference_drafter,
        "brief": lambda: brief_drafter,
        "bedrock": bedrock_drafter,
    }
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252
    report = asyncio.run(run(load_jsonl(args.dataset), drafters[args.drafter](), args.drafter))
    print(to_markdown(report))
    if args.out:
        args.out.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    return 1 if args.fail_on_gate and not report.gate_passed else 0
