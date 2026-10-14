"""Draft generators: the body of the email, L1 in and L1 out (architecture §9.1, D7).

* `BedrockGenerator` — Claude on Amazon Bedrock through the model router (Haiku 5.5 by
  default, Sonnet 5.5 for premium drafts). One call; a second one only if the deterministic
  style checks fail (architecture §9.2 "the LLM revises only on failure").
* `OfflineGenerator` — the clearly labelled stand-in until the AWS account exists (founder,
  2026-10-13). No model: it turns the user's instruction into first-person sentences in their
  register (or a short acknowledgement with fill-in slots when there is no instruction). It
  never reuses text from other conversations, so it can't leak facts between audiences.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Literal, Protocol

from vanimo.drafting.context import LiveContext
from vanimo.drafting.pack import PersonaPack
from vanimo.drafting.prompt import AI_TELLS, Prompt, style_problems
from vanimo.learning import labels, style
from vanimo.llm.router import LlmClient, Route

OFFLINE_LABEL = "Offline stand-in, no AI model: your greeting, sign-off and register around your instruction"


@dataclass(frozen=True)
class Body:
    text: str  # L1, before the output gate
    model_id: str | None  # None for the offline stand-in
    ttft_ms: float | None
    total_ms: float
    revised: bool = False


class Generator(Protocol):
    kind: Literal["offline", "bedrock"]

    async def body(self, ctx: LiveContext, pack: PersonaPack, prompt: Prompt, route: Route) -> Body: ...


# --- Claude on Bedrock ---------------------------------------------------------------------------
class BedrockGenerator:
    kind: Literal["offline", "bedrock"] = "bedrock"

    def __init__(self, llm: LlmClient) -> None:
        self._llm = llm

    async def body(self, ctx: LiveContext, pack: PersonaPack, prompt: Prompt, route: Route) -> Body:
        max_tokens = min(1500, max(300, prompt.bounds[1] * 3))
        messages = [{"role": "user", "content": prompt.user}]
        first = await self._llm.generate(
            model=route.model_id, system=prompt.system, messages=messages, max_tokens=max_tokens
        )
        problems = style_problems(first.text, prompt)
        if not problems:
            return Body(first.text, first.model_id, first.ttft_ms, first.total_ms)
        fix = (
            "Revise the body you wrote. Problems: "
            + "; ".join(problems)
            + ". Keep the meaning, the voice and every marker as it is. Return only the revised body."
        )
        second = await self._llm.generate(
            model=route.model_id,
            system=prompt.system,
            messages=[*messages, {"role": "assistant", "content": first.text}, {"role": "user", "content": fix}],
            max_tokens=max_tokens,
        )
        better = len(style_problems(second.text, prompt)) < len(problems)
        return Body(
            second.text if better else first.text,
            first.model_id,
            first.ttft_ms,
            round(first.total_ms + second.total_ms, 1),
            revised=better,
        )


# --- offline stand-in ----------------------------------------------------------------------------
_OBJ = r"(?:him|her|them|everyone|all|the (?:client|team|vendor|customer)|⟦[^⟦⟧]{1,40}⟧)"
_LEAD = r"^(?:please\s+|pls\s+|can you\s+)?"
_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(_LEAD + rf"(?:tell|inform)\s+(?:{_OBJ}\s+)?(?:that\s+)?(.+)$", re.I), "state"),
    (re.compile(_LEAD + rf"let\s+{_OBJ}\s+know\s+(?:that\s+)?(.+)$", re.I), "state"),
    (re.compile(_LEAD + rf"ask\s+(?:{_OBJ}\s+)?(?:if|whether)\s+(.+)$", re.I), "ask_if"),
    (re.compile(_LEAD + rf"ask\s+(?:{_OBJ}\s+)?for\s+(.+)$", re.I), "ask_for"),
    (re.compile(_LEAD + rf"ask\s+(?:{_OBJ}\s+)?(?:to\s+)?(.+)$", re.I), "ask_to"),
    (re.compile(_LEAD + rf"(?:say\s+)?thanks?\s+(?:{_OBJ}\s+)?(?:for\s+)?(.+)$", re.I), "thanks"),
    (re.compile(_LEAD + r"confirm\s+(?:that\s+)?(.+)$", re.I), "confirm"),
    (re.compile(_LEAD + r"(?:apologi[sz]e|say sorry)\s+(?:for\s+)?(.+)$", re.I), "sorry"),
    (re.compile(_LEAD + r"(?:politely\s+)?(?:decline|say no to)\s+(.+)$", re.I), "decline"),
]
# With no instruction: a short acknowledgement by what the last message was, plus a fill-in slot.
_ACK = {
    "question": "Thanks for checking. [Your answer]",
    "request": "Thanks, noted. [What you'll do, and by when]",
    "scheduling": "Thanks. [Confirm whether the time works for you]",
    "update": "Thanks for the update.",
    "thanks": "Glad it helped.",
    "apology": "No problem at all.",
    "general": "Thanks for your note. [Your reply]",
}


def _cap(s: str) -> str:
    s = s.strip()
    return s[0].upper() + s[1:] if s and s[0].isalpha() else s


def _end(s: str, mark: str = ".") -> str:
    s = s.rstrip(" ,;:")
    return s if s.endswith((".", "!", "?")) else s + mark


def _clauses(instruction: str) -> list[str]:
    parts = re.split(r"\n+|;\s*|(?<=[.!?])\s+|,?\s+and also\s+|,?\s+also\s+", instruction.strip())
    return [p.strip() for p in parts if p and p.strip()]


def instruction_to_body(instruction: str, *, formal: bool, kindly: bool) -> str:
    """The user's instruction as first-person sentences ("ask him to share the deck" → "Could you
    please share the deck?"). Rules only; anything else is kept as written."""
    out: list[str] = []
    for clause in _clauses(instruction):
        for pattern, kind in _RULES:
            m = pattern.match(clause)
            if not m:
                continue
            rest = m.group(1).strip().rstrip(".!?")
            if kind == "state":
                out.append(_end(_cap(rest)))
            elif kind == "ask_if":
                out.append(_end(f"Could you confirm whether {rest}", "?"))
            elif kind == "ask_for":
                out.append(_end(f"Kindly share {rest}") if kindly else _end(f"Could you please share {rest}", "?"))
            elif kind == "ask_to":
                out.append(_end(f"Kindly {rest}") if kindly else _end(f"Could you please {rest}", "?"))
            elif kind == "thanks":
                out.append(_end(f"Thank you for {rest}" if formal else f"Thanks for {rest}"))
            elif kind == "confirm":
                out.append(_end(f"Confirming that {rest}"))
            elif kind == "sorry":
                out.append(_end(f"Apologies for {rest}" if formal else f"Sorry for {rest}"))
            elif kind == "decline":
                out.append(_end(f"Unfortunately, we won't be able to {rest}"))
            break
        else:
            out.append(_end(_cap(clause)))
    return " ".join(out)


class OfflineGenerator:
    kind: Literal["offline", "bedrock"] = "offline"

    async def body(self, ctx: LiveContext, pack: PersonaPack, prompt: Prompt, route: Route) -> Body:
        start = time.perf_counter()
        card = pack.card
        formal = float(card.get("formality", 0.5)) + 0.15 * pack.settings.formality >= 0.6
        kindly = "kindly" in card.get("keep_list", []) and (
            formal or ctx.audience.relationship in ("external", "manager")
        )
        if ctx.instruction:
            text = instruction_to_body(ctx.instruction, formal=formal, kindly=kindly)
        else:
            text = _ACK[labels.intent(ctx.last_received or "") if ctx.last_received else "general"]
        text = _strip_tells(text)
        return Body(text, None, None, round((time.perf_counter() - start) * 1000, 1))


def _strip_tells(text: str) -> str:
    sentences = re.findall(r"[^.!?]+[.!?]?\s*", text)
    kept = [s for s in sentences if not any(t in s.lower() for t in AI_TELLS)]
    return "".join(kept).strip() or text


def words(text: str) -> int:
    return len(style._words(text))
