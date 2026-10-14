"""Pre-send checks (MVP plan M3; architecture §9.2 "guardrails specific to drafting", §10).

Deterministic rules, no model. They run on every draft Vanimo writes and, through
`POST /api/drafts/check`, on the text the user is about to send:

  invented facts   dates, times, amounts and promises in a draft that the thread and the user's
                   instruction don't contain (generated drafts only: the user's own words are theirs)
  wrong recipient  look-alike domains, first contact with a domain, a personal address or an
                   outsider added to an internal thread, a greeting naming someone not on To, a client
                   named in front of a different client
  BEC              requests to change payment details or pay urgently: insert is switched off until
                   the user confirms they verified it another way
  regulated IDs    Aadhaar, PAN, account numbers, cards, secrets … in the text being sent

Messages are shown only to the owner and may quote their own draft; they are never logged or
stored (only the codes are kept with a draft).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from vanimo.redaction import detectors
from vanimo.redaction.marks import L1_MARKS
from vanimo.sources.base import CONSUMER_DOMAINS, Address

Severity = Literal["block", "warn", "info"]


@dataclass(frozen=True)
class Check:
    code: str  # stable and content-free; stored with the draft
    severity: Severity  # block = insert is off until the user confirms
    message: str  # for the owner's screen only


@dataclass(frozen=True)
class ClientAccount:
    name: str
    domain_hashes: frozenset[str]


def _in(domain: str, domains: Iterable[str]) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in domains)


def _quote(text: str, limit: int = 120) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


# --- invented facts -----------------------------------------------------------------------------
_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
_FACTS = re.compile(
    "|".join(
        [
            r"\b(?:mon|tues|wednes|thurs|fri|satur|sun)day\b",
            r"\b(?:day after tomorrow|tomorrow|today|tonight|tmrw|this week|next week|this month|next month|"
            r"end of (?:the )?(?:day|week|month|quarter)|eod|eow|cob)\b",
            rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTH}(?:\s+\d{{4}})?",
            rf"\b{_MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?\b(?:,?\s+\d{{4}})?",
            r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b",
            r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b|\b\d{1,2}:\d{2}\b",
            r"(?:₹|\brs\.?|\binr|\busd|\$|€|£)\s*\d[\d,]*(?:\.\d+)?(?:\s*(?:k|lakhs?|crores?|million|mn|bn)\b)?",
            r"\b\d[\d,]*(?:\.\d+)?\s*(?:lakhs?|crores?|usd|inr|dollars|rupees)\b",
            r"\b\d+(?:\.\d+)?\s*%",
            r"\b\d+(?:\.\d+)?\s*(?:days?|weeks?|months?|hours?|hrs?|people|resources|engineers|ftes?|sprints?)\b",
            r"\bv?\d+\.\d+(?:\.\d+)?\b",
        ]
    ),
    re.I,
)
_COMMITMENT = re.compile(
    r"\b(?:i'll|i will|we'll|we will|i shall|we shall|i promise|we promise|guarantee|committed to|"
    r"will (?:send|share|deliver|complete|finish|get|have|provide|update|revert|confirm|fix|deploy|schedule|"
    r"arrange|book|be ready|be done|go live))\b",
    re.I,
)
_NOT_A_FACT = re.compile(r"24\s*[/x]\s*7|365\s*/\s*24", re.I)  # round-the-clock, not a date
_SENTENCE = re.compile(r"[^.!?\n]+[.!?]?")
_CONTENT_WORD = re.compile(r"[a-z][a-z'-]{3,}")
_STOP = frozenset(
    "this that with will have from your they them their there about would could should shall which when what "
    "been were also just than then into over only very more most some such like make sure here please thanks "
    "thank need needs want know".split()
)


def _norm(text: str) -> str:
    text = L1_MARKS.sub(" ", text.lower())
    text = re.sub(r"(?<=\d),(?=\d)", "", text)
    return " ".join(text.replace("’", "'").split())  # noqa: RUF001 - typographic apostrophe


def _grounded(fact: str, grounding: str) -> bool:
    f = _norm(fact)
    if f in grounding:
        return True
    # The same numbers written another way ground it: "$18,400" by "USD 18400", "28 Oct" by "Oct 28".
    numbers = re.findall(r"\d+(?:\.\d+)?", f)
    return bool(numbers) and all(re.search(rf"(?<![\d.]){re.escape(n)}(?![\d])", grounding) for n in numbers)


def invented_facts(draft: str, grounding: str) -> list[Check]:
    """Dates, times, amounts and promises in a generated draft that nothing it was given contains."""
    ground = _norm(grounding)
    ground_words = set(_CONTENT_WORD.findall(ground))
    out: list[Check] = []
    loose: list[str] = []
    for sentence in _SENTENCE.findall(L1_MARKS.sub(" ", draft)):
        facts = [
            m.group()
            for m in _FACTS.finditer(sentence)
            if not _NOT_A_FACT.fullmatch(m.group()) and not _grounded(m.group(), ground)
        ]
        if _COMMITMENT.search(sentence):
            words = [w for w in _CONTENT_WORD.findall(sentence.lower()) if w not in _STOP]
            unsupported = bool(words) and sum(w in ground_words for w in words) / len(words) < 0.34
            if facts:
                out.append(
                    Check(
                        "invented_commitment",
                        "warn",
                        f"“{_quote(sentence)}” promises {', '.join(dict.fromkeys(facts))}, which isn't in the email "
                        "or your instruction. Check it before sending.",
                    )
                )
                continue
            if unsupported:
                out.append(
                    Check(
                        "unrequested_promise",
                        "warn",
                        f"“{_quote(sentence)}” makes a promise you didn't ask for. Keep it only if you mean it.",
                    )
                )
                continue
        loose += facts
    if loose:
        out.append(
            Check(
                "invented_fact",
                "warn",
                f"The draft mentions {', '.join(dict.fromkeys(loose))}, which isn't in the email or your instruction. "
                "Check before sending.",
            )
        )
    return out


# --- recipients ---------------------------------------------------------------------------------
_CONFUSABLE = str.maketrans({"0": "o", "1": "l", "3": "e", "5": "s", "7": "t", "|": "l", "-": "", "_": ""})


def _skeleton(domain: str) -> str:
    return domain.lower().translate(_CONFUSABLE).replace("rn", "m").replace("vv", "w").replace("i", "l")


def _distance_le_1(a: str, b: str) -> bool:
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        diffs = [i for i in range(len(a)) if a[i] != b[i]]
        return len(diffs) == 1 or (len(diffs) == 2 and diffs[1] == diffs[0] + 1 and a[diffs[0]] == b[diffs[1]])
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    return any(long_[:i] + long_[i + 1 :] == short for i in range(len(long_)))


def lookalike(domain: str, known: str) -> bool:
    """`domain` imitates `known`: confusable characters (c1oudnest), one edit (acmeretai.example),
    or the known name with a word glued on (cloudnest-billing.example)."""
    if domain == known or domain.endswith("." + known) or known.endswith("." + domain):
        return False
    d_label, _, d_rest = domain.partition(".")
    k_label, _, k_rest = known.partition(".")
    if _skeleton(domain) == _skeleton(known):
        return True
    if len(k_label) >= 5 and d_rest == k_rest and _distance_le_1(d_label, k_label):
        return True
    return len(k_label) >= 5 and k_label in d_label and bool(re.search(r"[-_]", d_label))


def _twin(domain: str, trusted: set[str]) -> str | None:
    if domain in CONSUMER_DOMAINS:
        return None
    return next((k for k in sorted(trusted - CONSUMER_DOMAINS) if lookalike(domain, k)), None)


def recipient_checks(
    recipients: Sequence[Address],
    *,
    thread_people: Sequence[Address],
    known_domains: Iterable[str],
    org_domains: Iterable[str],
    me: str,
) -> list[Check]:
    """`known_domains`: domains the user has written to before (their Sources index). A domain only
    seen in this thread is not trusted for the look-alike test: the look-alike sender is in it."""
    me = me.lower()
    org = {d.lower() for d in org_domains}
    trusted = {d.lower() for d in known_domains} | org
    thread = [a for a in thread_people if a.email and a.email.lower() != me]
    in_thread = {a.domain for a in thread}
    out: list[Check] = []
    seen: set[str] = set()
    for r in recipients:
        d = r.domain
        if not r.email or d in seen:
            continue
        seen.add(d)
        if _in(d, trusted):
            continue
        twin = _twin(d, trusted)
        if twin:
            out.append(
                Check(
                    "lookalike_domain",
                    "block",
                    f"{r.email} is at {d}, which looks like {twin} but isn't the same. This is a common phishing "
                    "trick: check the address before you send.",
                )
            )
        elif d in in_thread:
            continue
        elif d in CONSUMER_DOMAINS:
            out.append(Check("personal_address", "warn", f"{r.email} is a personal email address."))
        else:
            out.append(Check("new_domain", "warn", f"You haven't written to anyone at {d} before."))
    internal_thread = bool(thread) and all(_in(a.domain, org) for a in thread)
    outsiders = [r.email for r in recipients if r.email and not _in(r.domain, org)]
    if internal_thread and outsiders:
        out.append(
            Check(
                "external_added",
                "warn",
                f"This was an internal conversation, and {', '.join(outsiders[:3])} is outside your organisation.",
            )
        )
    return out


def sender_lookalike(
    senders: Sequence[Address], *, known_domains: Iterable[str], org_domains: Iterable[str]
) -> list[Check]:
    """The email being answered came from a domain that imitates one the user knows."""
    trusted = {d.lower() for d in known_domains} | {d.lower() for d in org_domains}
    for a in senders:
        if not a.email or _in(a.domain, trusted):
            continue
        twin = _twin(a.domain, trusted)
        if twin:
            return [
                Check(
                    "lookalike_sender",
                    "block",
                    f"This email came from {a.domain}, which looks like {twin} but isn't the same. Treat its requests "
                    "with suspicion and check with the sender another way.",
                )
            ]
    return []


_GREETING_NAME = re.compile(
    r"^\s*(?i:hi|hello|hey|dear|good (?:morning|afternoon|evening))[\s,]+"
    r"(?:(?i:mr|mrs|ms|miss|dr|prof|shri|sri|smt|sir|madam)\.?\s+)?([A-Z][A-Za-z'\-]+)",
    re.M,
)
_GROUP_WORDS = frozenset("all team everyone folks guys sir madam maam ma'am there".split())


def greeting_mismatch(text: str, to: Sequence[Address]) -> list[Check]:
    """The user's own greeting ("Hi Rahul,") names nobody on the To line."""
    m = _GREETING_NAME.search(text.strip().split("\n", 1)[0] if text.strip() else "")
    if not m or not to:
        return []
    name = m.group(1).lower()
    if name in _GROUP_WORDS:
        return []
    names: set[str] = set()
    for a in to:
        names |= {w.lower() for w in re.split(r"[\s.,]+", a.name or "") if w}
        names |= {w.lower() for w in re.split(r"[._\-+]", a.email.split("@", 1)[0]) if w}
    if name in names:
        return []
    return [
        Check(
            "greeting_mismatch",
            "warn",
            f"The greeting says “{m.group(1)}”, but nobody of that name is on the To line.",
        )
    ]


def cross_client(
    text: str,
    recipients: Sequence[Address],
    accounts: Sequence[ClientAccount],
    domain_hashes: Callable[[str], list[str]],
) -> list[Check]:
    """A client account named in an email that nobody from that client receives, while someone
    outside the organisation does (IT services: client A's details sent to client B)."""
    out: list[Check] = []
    folded = text.casefold()
    rec_hashes = [set(domain_hashes(r.domain)) for r in recipients if r.email]
    for acc in accounts:
        if len(acc.name) < 3 or not re.search(rf"(?<!\w){re.escape(acc.name.casefold())}(?!\w)", folded):
            continue
        if any(h & acc.domain_hashes for h in rec_hashes):
            continue
        out.append(
            Check(
                "other_client_named",
                "warn",
                f"This email names {acc.name}, but nobody from {acc.name} is on it. Make sure it's meant for these "
                "recipients.",
            )
        )
    return out


# --- payment changes (BEC) ----------------------------------------------------------------------
_PAY_THING = (
    r"(?:bank|banking|beneficiary|payment|remittance|wire|wiring)\s+"
    r"(?:details|information|info|instructions|accounts?|number)"
)
_CHANGE = r"(?:changed|change|changing|updated|update|new|different|revised)"
_PAYMENT_CHANGE = re.compile(
    "|".join(
        [
            rf"\b{_PAY_THING}\b[^.\n]{{0,80}}\b{_CHANGE}\b",
            rf"\b{_CHANGE}\b[^.\n]{{0,40}}\b{_PAY_THING}\b",
            # "our bank has changed", "we have moved banks", "switched our bank"
            r"\bbank(?:s|ing)?\s+(?:has|have)\s+(?:changed|moved|switched)\b",
            r"\b(?:moved|switched|changed)\s+(?:our\s+|my\s+)?banks?\b",
            r"\bnew\s+(?:bank\s+account|beneficiary|remittance|account\s+(?:number|details))\b",
            r"\b(?:pay|send|remit|transfer|wire)\w*\b[^.\n]{0,60}\binstead\s+of\b",
            r"\b(?:pay|payment|remit\w*|transfer|wire)\b[^.\n]{0,40}\b(?:to|into)\s+(?:our|the|this)\s+new\s+account\b",
        ]
    ),
    re.I,
)
_GIFT_CARDS = re.compile(r"\bgift\s*cards?\b[^\n]{0,120}\b(?:codes?|scratch|pins?)\b", re.I)
_MONEY_MOVE = (
    r"(?:payment|wire|bank transfer|fund transfer|money transfer|transfer (?:the )?(?:funds|money|amount)|remit\w*)"
)
_URGENT_PAYMENT = re.compile(
    rf"\b(?:urgent|urgently|immediately|today|asap|right away|eod)\b[^.\n]{{0,60}}\b{_MONEY_MOVE}\b"
    rf"|\b{_MONEY_MOVE}\b[^.\n]{{0,60}}\b(?:urgent|urgently|immediately|today|asap|right away|eod)\b",
    re.I,
)


def payment_change(received: Sequence[str], draft: str, *, sender_lookalike: bool = False) -> list[Check]:
    """A request to change where money goes, or to pay in a hurry: the classic business email
    compromise. Insert is switched off until the user confirms they verified it another way."""
    asked = any(_PAYMENT_CHANGE.search(t) for t in received)
    urgent = any(_URGENT_PAYMENT.search(t) for t in received)
    out: list[Check] = []
    if asked or (urgent and sender_lookalike):
        out.append(
            Check(
                "payment_change",
                "block",
                "This email asks to change payment details or pay urgently. Verify it by phone on a number you "
                "already have, not one from this email. Insert stays off until you confirm.",
            )
        )
    elif urgent:
        out.append(Check("urgent_payment", "warn", "This email asks for an urgent payment. Make sure it's genuine."))
    if any(_GIFT_CARDS.search(t) for t in received):
        out.append(
            Check("gift_cards", "warn", "This email asks for gift card codes, a common scam. Check with the sender.")
        )
    if not out and _PAYMENT_CHANGE.search(draft):
        out.append(
            Check(
                "payment_change_in_draft",
                "warn",
                "Your email changes payment details. Expect the recipient to verify it with you by phone.",
            )
        )
    return out


# --- regulated identifiers ----------------------------------------------------------------------
def regulated_ids(text: str) -> list[Check]:
    """Regulated identifiers and secrets in text the user is about to send (their own words, L0)."""
    kinds = list(dict.fromkeys(s.kind for s in detectors.detect(text) if s.tier == "R"))
    out: list[Check] = []
    secrets_ = [k for k in kinds if k in ("secret", "password")]
    ids = [k for k in kinds if k not in ("secret", "password")]
    if secrets_:
        out.append(Check("secret", "warn", "This email contains what looks like a password or secret key."))
    if ids:
        out.append(
            Check("regulated_id", "warn", f"This email contains {', '.join(ids)}. Make sure it's meant to be sent.")
        )
    return out


_SLOT_TEXT = re.compile(r"\[[A-Za-z][^\[\]\n]{1,48}\]")


def fill_ins(draft: str) -> list[Check]:
    """Values Vanimo never fills in itself ([PAN], [date]) are left for the user."""
    slots = list(dict.fromkeys(_SLOT_TEXT.findall(draft)))
    slots = [s for s in slots if s not in ("[removed]",)]
    if not slots:
        return []
    return [Check("fill_in", "info", f"Fill in {', '.join(slots[:6])} yourself before sending.")]


def blocked(checks: Iterable[Check]) -> bool:
    return any(c.severity == "block" for c in checks)
