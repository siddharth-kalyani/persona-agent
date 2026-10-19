"""S5 PII backstop (architecture §7.2 S5, F11): a second detector after our own.

The redactor sends it text that is already partly L1 (never-send words, regulated identifiers,
addresses, phone numbers and known names are masked), so the service sees only what our detectors
let through. Its findings come back as offsets and types (never values) and the redactor masks them
before the verify pass.

* `ComprehendDetector` — Amazon Comprehend `DetectPiiEntities` (English; includes Aadhaar, PAN,
  voter ID and NREGA). Offsets are character offsets, so they index a Python `str` directly. Text is
  sent in chunks under the 100 KB (UTF-8) limit. Any failure raises `PiiUnavailable`: the caller
  blocks the item, never passes it (fail-closed).
* `OfflinePiiDetector` — the clearly labelled stand-in until the AWS account exists: local rules for
  names after a title or "my name is", and street addresses. Not a model.

Results are cached in memory for a few minutes, keyed by a keyed hash of the text (the same thread is
redacted again on every draft); the cache holds offsets and types only.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import re
import time
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from vanimo.logs import get_logger

log = get_logger("vanimo.backstops")

# Comprehend accepts up to 100 KB of UTF-8 per call; stay under it with room for multi-byte splits.
MAX_CHUNK_BYTES = 90_000
CACHE_SIZE = 4096
CACHE_TTL_S = 900


class PiiUnavailable(Exception):
    """The detector couldn't be reached or answered badly. Content-free."""


@dataclass(frozen=True)
class Finding:
    start: int
    end: int
    type: str  # Comprehend's entity type (NAME, ADDRESS, IN_AADHAAR, ...)
    score: float


# What each entity type becomes in L1: a person token, a Tier P token, or a typed slot (Tier R).
# Types that aren't identifying on their own (dates, ages, URLs) are left in the text.
Action = tuple[Literal["person", "email", "phone", "slot"], str]
ACTIONS: dict[str, Action] = {
    "NAME": ("person", "name"),
    "EMAIL": ("email", "email"),
    "PHONE": ("phone", "phone"),
    "ADDRESS": ("slot", "address"),
    "SSN": ("slot", "SSN"),
    "US_INDIVIDUAL_TAX_IDENTIFICATION_NUMBER": ("slot", "SSN"),
    "CREDIT_DEBIT_NUMBER": ("slot", "card number"),
    "CREDIT_DEBIT_CVV": ("slot", "card details"),
    "CREDIT_DEBIT_EXPIRY": ("slot", "card details"),
    "PIN": ("slot", "PIN"),
    "BANK_ACCOUNT_NUMBER": ("slot", "bank account"),
    "INTERNATIONAL_BANK_ACCOUNT_NUMBER": ("slot", "bank account"),
    "BANK_ROUTING": ("slot", "routing number"),
    "SWIFT_CODE": ("slot", "SWIFT code"),
    "PASSPORT_NUMBER": ("slot", "passport number"),
    "DRIVER_ID": ("slot", "driver ID"),
    "PASSWORD": ("slot", "password"),
    "USERNAME": ("slot", "username"),
    "AWS_ACCESS_KEY": ("slot", "secret"),
    "AWS_SECRET_KEY": ("slot", "secret"),
    "IN_AADHAAR": ("slot", "Aadhaar number"),
    "IN_PERMANENT_ACCOUNT_NUMBER": ("slot", "PAN"),
    "IN_VOTER_NUMBER": ("slot", "voter ID"),
    "IN_NREGA": ("slot", "NREGA job card"),
    "UK_NATIONAL_INSURANCE_NUMBER": ("slot", "national ID"),
    "UK_UNIQUE_TAXPAYER_REFERENCE_NUMBER": ("slot", "national ID"),
    "UK_NATIONAL_HEALTH_SERVICE_NUMBER": ("slot", "national ID"),
    "CA_SOCIAL_INSURANCE_NUMBER": ("slot", "national ID"),
    "CA_HEALTH_NUMBER": ("slot", "national ID"),
    "LICENSE_PLATE": ("slot", "vehicle ID"),
    "VEHICLE_IDENTIFICATION_NUMBER": ("slot", "vehicle ID"),
    "IP_ADDRESS": ("slot", "network address"),
    "MAC_ADDRESS": ("slot", "network address"),
}
# Minimum confidence to act on. Names, addresses and credentials are where ordinary words get
# mistaken for PII, so they need more. To re-tune on real (synthetic) traffic once AWS is connected.
MIN_SCORE = 0.5
MIN_SCORE_BY_TYPE = {"NAME": 0.7, "ADDRESS": 0.7, "USERNAME": 0.8, "PASSWORD": 0.8, "PIN": 0.8}


def wanted(f: Finding) -> bool:
    return f.type in ACTIONS and f.score >= MIN_SCORE_BY_TYPE.get(f.type, MIN_SCORE)


class PiiDetector(Protocol):
    name: Literal["comprehend", "offline"]
    label: str

    async def detect(self, text: str) -> list[Finding]: ...


def chunks(text: str, limit: int = MAX_CHUNK_BYTES) -> list[tuple[int, str]]:
    """(offset, piece) pairs, each under `limit` bytes of UTF-8, split at line ends where possible,
    then at spaces, then anywhere."""
    if len(text.encode()) <= limit:
        return [(0, text)]
    out: list[tuple[int, str]] = []
    start = 0
    while start < len(text):
        end = start
        size = 0
        cut = -1
        while end < len(text):
            n = len(text[end].encode())
            if size + n > limit:
                break
            size += n
            end += 1
            if text[end - 1] == "\n":
                cut = end
        if end < len(text):
            if cut <= start:
                space = text.rfind(" ", start, end)
                cut = space + 1 if space > start else end
            end = cut
        out.append((start, text[start:end]))
        start = end
    return out


class _Cache:
    """Findings by keyed hash of the text (process-random key: nothing linkable is kept)."""

    def __init__(self, size: int = CACHE_SIZE, ttl_s: float = CACHE_TTL_S) -> None:
        self._key = os.urandom(32)
        self._size = size
        self._ttl = ttl_s
        self._items: OrderedDict[str, tuple[float, tuple[Finding, ...]]] = OrderedDict()

    def _k(self, text: str) -> str:
        return hmac.new(self._key, text.encode(), hashlib.sha256).hexdigest()

    def get(self, text: str) -> tuple[Finding, ...] | None:
        k = self._k(text)
        hit = self._items.get(k)
        if hit is None or time.monotonic() - hit[0] > self._ttl:
            self._items.pop(k, None)
            return None
        self._items.move_to_end(k)
        return hit[1]

    def put(self, text: str, findings: Sequence[Finding]) -> None:
        self._items[self._k(text)] = (time.monotonic(), tuple(findings))
        while len(self._items) > self._size:
            self._items.popitem(last=False)


class ComprehendDetector:
    name: Literal["comprehend", "offline"] = "comprehend"
    label = "Amazon Comprehend (DetectPiiEntities)"

    def __init__(self, region: str, *, client: Any = None, max_in_flight: int = 8) -> None:
        if client is None:
            import boto3
            from botocore.config import Config

            # Adaptive retries absorb throttling (50 calls/s in ap-south-1); short timeouts keep a
            # draft from hanging on a slow endpoint (it is blocked instead).
            client = boto3.client(
                "comprehend",
                region_name=region,
                config=Config(retries={"mode": "adaptive", "max_attempts": 4}, connect_timeout=3, read_timeout=10),
            )
        self._client = client
        self._cache = _Cache()
        self._slots = asyncio.Semaphore(max_in_flight)

    async def detect(self, text: str) -> list[Finding]:
        if not re.search(r"\w", text):
            return []
        cached = self._cache.get(text)
        if cached is not None:
            return list(cached)
        out: list[Finding] = []
        for offset, piece in chunks(text):
            if not re.search(r"\w", piece):
                continue
            try:
                async with self._slots:
                    resp = await asyncio.to_thread(self._client.detect_pii_entities, Text=piece, LanguageCode="en")
                entities = resp["Entities"]
                for e in entities:
                    start, end = int(e["BeginOffset"]), int(e["EndOffset"])
                    if not 0 <= start < end <= len(piece):
                        raise ValueError("offset out of range")
                    out.append(Finding(offset + start, offset + end, str(e["Type"]), float(e["Score"])))
            except Exception as exc:
                # The exception's message can echo request details: only its type is logged.
                log.warning("backstops.comprehend_failed", error_type=type(exc).__name__)
                raise PiiUnavailable("comprehend_unavailable") from None
        self._cache.put(text, out)
        return out


_TITLE_NAME = re.compile(
    r"\b(?:Mr|Mrs|Ms|Mx|Dr|Prof|Shri|Sri|Smt|Kumari)\.?\s+([A-Z][a-z]+(?:[ \-][A-Z][a-z]+){0,2})\b"
)
_MY_NAME = re.compile(r"\b[Mm]y name is\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b")
_STREET = (
    r"(?:Road|Rd|Street|St|Lane|Ln|Avenue|Ave|Marg|Nagar|Colony|Layout|Cross|Main|Boulevard|Blvd|Drive|"
    r"Highway|Hwy|Place|Pl|Court|Ct|Way|Terrace)"
)
_ADDRESS = re.compile(
    rf"\b\d{{1,5}}[A-Za-z]?(?:/\d{{1,4}})?,?\s+(?:[A-Z][A-Za-z]*\.?\s+){{1,4}}{_STREET}\b\.?"
    r"(?:,\s*[A-Z][a-z]+(?:\s[A-Z][a-z]+)?)?(?:[ ,\-]+\d{3}\s?\d{3}\b|[ ,]+[A-Z]{2}\s\d{5}\b)?"
)
_UNIT = re.compile(r"\b(?:Flat|Apt|Apartment)\s*(?:No\.?\s*)?#?\d{1,5}[A-Z]?\b")


class OfflinePiiDetector:
    """Stand-in for Comprehend: local rules only, conservative (titles, "my name is", street addresses)."""

    name: Literal["comprehend", "offline"] = "offline"
    label = "Offline stand-in for Amazon Comprehend: local rules (titled names, street addresses), not a model"

    async def detect(self, text: str) -> list[Finding]:
        out = [Finding(m.start(1), m.end(1), "NAME", 0.9) for m in _TITLE_NAME.finditer(text)]
        out += [Finding(m.start(1), m.end(1), "NAME", 0.9) for m in _MY_NAME.finditer(text)]
        out += [Finding(m.start(), m.end(), "ADDRESS", 0.85) for m in _ADDRESS.finditer(text)]
        out += [Finding(m.start(), m.end(), "ADDRESS", 0.75) for m in _UNIT.finditer(text)]
        return out
