from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from tests.conftest import TENANT
from vanimo import audit, canary
from vanimo.db.session import provision_user, user_tx
from vanimo.evals import runner
from vanimo.evals.dataset import EvalCase, load_jsonl
from vanimo.evals.metrics import bucket, edit_ratio, levenshtein

DATASET = Path(__file__).resolve().parents[1] / "evals" / "datasets" / "synthetic_v0.jsonl"


def test_metrics() -> None:
    assert levenshtein("kitten", "sitting") == 3
    assert edit_ratio("same", "same") == 0
    assert edit_ratio("", "") == 0
    assert bucket(0.05) == "sent_as_is" and bucket(0.1) == "light_edit" and bucket(0.2) == "heavy_edit"


def test_dataset_loads_and_is_l1_only() -> None:
    cases = load_jsonl(DATASET)
    assert len(cases) >= 8
    assert all("⟦PERSON_" in c.reference_sent_l1 or c.slice.endswith("teams") for c in cases)


async def test_runner_bounds() -> None:
    cases = load_jsonl(DATASET)
    upper = await runner.run(cases, runner.reference_drafter, "reference")
    lower = await runner.run(cases, runner.brief_drafter, "brief")
    assert upper.send_without_edit == 1.0 and upper.gate_passed
    assert lower.send_without_edit < 0.5 and not lower.gate_passed
    assert {s.slice for s in upper.slices} == {c.slice for c in cases}
    assert "MVP gate: PASS" in runner.to_markdown(upper)


async def test_runner_rejects_empty() -> None:
    with pytest.raises(ValueError):
        await runner.run([], runner.reference_drafter, "x")


def test_duplicate_ids_rejected(tmp_path: Path) -> None:
    row = '{"id": "a", "slice": "s", "brief": "b", "context_l1": "c", "reference_sent_l1": "r"}\n'
    p = tmp_path / "d.jsonl"
    p.write_text(row + row, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_jsonl(p)
    assert EvalCase(id="a", slice="s", brief="b", context_l1="c", reference_sent_l1="r")


def test_canary_format_and_text_scan() -> None:
    c = canary.new_canary("chat")
    assert canary.PATTERN.fullmatch(c)
    assert canary.scan_texts([f"prefix {c} suffix", "clean"]) == [c]
    assert canary.scan_texts([c], canaries=["VNMCANARY-chat-000000000000"]) == []
    with pytest.raises(ValueError):
        canary.new_canary("Bad Kind")


@pytest.mark.db
async def test_database_canary_scan(database: dict[str, str]) -> None:
    engine = create_async_engine(database["app"])
    ref = await provision_user(engine, entra_tenant_id=TENANT, entra_oid=str(uuid.uuid4()), cell="in", data_region="IN")
    marker = canary.new_canary("store")
    async with user_tx(engine, ref) as conn:
        await audit.record(conn, ref, "canary.seed", target_kind="canary", target_ref=marker)
    await engine.dispose()
    hits = canary.scan_database(database["owner"], [marker])
    assert hits == {"audit_events.target_ref": [marker]}
    assert canary.scan_database(database["owner"], ["VNMCANARY-none-000000000000"]) == {}


def test_cli_fail_on_gate(capsys: pytest.CaptureFixture) -> None:
    assert runner.main(["--dataset", str(DATASET), "--drafter", "brief"]) == 0
    assert runner.main(["--dataset", str(DATASET), "--drafter", "brief", "--fail-on-gate"]) == 1
    assert runner.main(["--dataset", str(DATASET), "--drafter", "reference", "--fail-on-gate"]) == 0
    assert "MVP gate" in capsys.readouterr().out
