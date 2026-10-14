"""Output gate and display (architecture §9.4 "output gate", §7.3, §6.5 X6).

Every generated body passes the gate before anyone sees it:
  * plain text: markdown dropped, and any greeting or sign-off the model wrote anyway removed
    (code adds the user's own);
  * marks: only tokens and placeholders that were in this request's prompt survive — a token the
    model made up is never revealed (token-spoofing defence); stray brackets are removed;
  * links: only ones that appear in the thread or the instruction; others become [link removed];
  * Tier R: a regulated identifier or secret in the output blocks the draft (no draft + reason);
    a raw email address or phone number the model wrote becomes a fill-in slot;
  * never-send words the model produced by itself are masked.

`render` then builds what the owner sees: tokens become names, never-send placeholders become
[removed] — or the word itself for words the user marked "Allow in my drafts" — and a last pass
masks never-send words that arrived inside a name.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from vanimo.controls.neversend import REMOVED, Matcher
from vanimo.drafting.checks import Check
from vanimo.learning import style
from vanimo.redaction import detectors
from vanimo.redaction.marks import L1_MARKS, NEVER_SEND, TOKEN

# Links: with a scheme or "www.", a bare host with a path ("paypa1-billing.example/pay"), and the
# common link shorteners even without one. Outlook turns all of these into clickable links.
_URL = re.compile(
    r"(?i)\b(?:https?://|www\.)[^\s<>()\[\]⟦⟧\"']+"
    r"|\b(?:[a-z0-9-]+\.)+[a-z]{2,24}/[^\s<>()\[\]⟦⟧\"']*"
    r"|\b(?:bit\.ly|tinyurl\.com|t\.co|goo\.gl|ow\.ly|is\.gd|buff\.ly|rb\.gy|cutt\.ly)\b[^\s<>()\[\]⟦⟧\"']*"
)
_ANY_MARK = re.compile(r"⟦[^⟦⟧\n]{0,60}⟧")
_MARKDOWN = [
    (re.compile(r"```[a-z]*\n?|```"), ""),
    (re.compile(r"\*\*(.+?)\*\*"), r"\1"),
    (re.compile(r"__(.+?)__"), r"\1"),
    (re.compile(r"^#{1,6}\s*", re.M), ""),
    (re.compile(r"^\s*[*•]\s+", re.M), "- "),
]
_SUBJECT_LINE = re.compile(r"^\s*subject:.*\n+", re.I)
_ME_LINE = re.compile(r"^\s*⟦ME(?:\.full|\.last)?⟧\.?\s*$")
# A line that is only a closing ("Best regards,"), never a sentence that starts with "Thanks for …".
_CLOSING_LINE = re.compile(
    r"^\s*(?:thanks|thank you|many thanks|thanks again|regards|best|best regards|kind regards|warm regards|"
    r"warmest regards|cheers|sincerely|br|thanks and regards|thanks & regards)"
    r"\s*[,.!]?\s*(?:⟦ME(?:\.full|\.last)?⟧)?\s*$",
    re.I,
)


@dataclass
class Gated:
    body: str  # L1
    notes: list[Check] = field(default_factory=list)
    blocked: str | None = None  # content-free reason; the draft is not shown


def clean(text: str) -> str:
    """Plain text with the model's own greeting and sign-off removed."""
    text = text.replace("\r\n", "\n").strip()
    for pattern, repl in _MARKDOWN:
        text = pattern.sub(repl, text)
    text = _SUBJECT_LINE.sub("", text)
    lines = text.rstrip().split("\n")
    first = lines[0].strip() if lines else ""
    if len(lines) > 1 and style.greeting_of(first) and (first.endswith((",", "!")) or len(first.split()) <= 3):
        lines = lines[1:]
    while len(lines) > 1 and (_ME_LINE.match(lines[-1]) or _CLOSING_LINE.match(lines[-1]) or not lines[-1].strip()):
        lines.pop()
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def gate(body: str, *, prompt_marks: set[str], grounding: str, matcher: Matcher) -> Gated:
    notes: list[Check] = []
    text = clean(body)

    spoofed = 0

    def _mark(m: re.Match[str]) -> str:
        nonlocal spoofed
        t = m.group()
        if t in prompt_marks:
            return t
        spoofed += 1
        if TOKEN.fullmatch(t) or t.startswith("⟦PERSON") or t.startswith("⟦EMAIL") or t.startswith("⟦PHONE"):
            return "[name]"
        return REMOVED if NEVER_SEND.fullmatch(t) or t.startswith("⟦NS") else ""

    text = _ANY_MARK.sub(_mark, text)
    # Stray brackets outside Vanimo's own marks are dropped (a half marker never reaches the screen).
    text = "".join(
        piece if L1_MARKS.fullmatch(piece) else piece.replace("⟦", "").replace("⟧", "")
        for piece in re.split(f"({L1_MARKS.pattern})", text)
    )
    if spoofed:
        notes.append(
            Check(
                "unknown_marker",
                "info",
                "A name the draft referred to wasn't in this conversation, so it was left out.",
            )
        )

    known = grounding.lower()
    removed_links = 0

    def _link(m: re.Match[str]) -> str:
        nonlocal removed_links
        url = m.group().rstrip(".,;:!?")
        tail = m.group()[len(url) :]
        if url.lower() in known:
            return m.group()
        removed_links += 1
        return "[link removed]" + tail

    text = _URL.sub(_link, text)
    if removed_links:
        notes.append(
            Check(
                "link_removed",
                "info",
                "A link that wasn't in the email or your instruction was removed from the draft.",
            )
        )

    # Tier R and raw contact details, looking only at free text (marks blanked, offsets kept).
    blank = L1_MARKS.sub(lambda m: " " * len(m.group()), text)
    spans = detectors.detect(blank)
    if any(s.tier == "R" for s in spans):
        return Gated("", notes, blocked="regulated_id_in_output")
    contact = [s for s in spans if s.tier == "P"]
    for s in sorted(contact, key=lambda s: -s.start):
        text = text[: s.start] + ("[email address]" if s.kind == "email" else "[phone number]") + text[s.end :]
    if contact:
        notes.append(
            Check(
                "contact_removed",
                "info",
                "An email address or phone number the draft made up was replaced with a fill-in.",
            )
        )

    text, _ = matcher.mask(text, opaque=L1_MARKS)
    return Gated((text or "").strip(), notes)


def compose(greeting: str, body: str, sign_off: str) -> str:
    return "\n\n".join(p for p in (greeting, body, sign_off) if p)


def render(
    l1: str,
    *,
    values: dict[str, str],
    allowed_marks: set[str],
    allowed_terms: dict[str, str],
    blocked_matcher: Matcher,
) -> tuple[str, int]:
    """What the owner sees. Returns (text, how many never-send words show as [removed])."""
    removed = 0

    def _token(m: re.Match[str]) -> str:
        t = m.group()
        return values.get(t, "[name]") if t in allowed_marks else "[name]"

    def _ns(m: re.Match[str]) -> str:
        nonlocal removed
        term_id = m.group()[4:12]
        if term_id in allowed_terms:
            return allowed_terms[term_id]
        removed += 1
        return REMOVED

    text = TOKEN.sub(_token, l1)
    text = NEVER_SEND.sub(_ns, text)
    # A display value (a name) can itself hold a never-send word: masked here, last.
    masked, hits = blocked_matcher.mask(text)
    removed += hits
    return NEVER_SEND.sub(REMOVED, masked or ""), removed
