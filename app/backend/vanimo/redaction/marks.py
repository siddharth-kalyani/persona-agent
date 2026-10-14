"""The marks redaction puts into L1 text, in one place (no imports, so both the never-send
matcher and the pipeline can use them).

Raw input never contains ⟦ or ⟧: the pipeline turns any it finds into [ and ] at S2, so every
⟦…⟧ in L1 was inserted by Vanimo and can be trusted as a mark.
"""

from __future__ import annotations

import re

TOKEN = re.compile(r"⟦(?:ME|PERSON_[0-9a-f]{8}|EMAIL_[0-9a-f]{8}|PHONE_[0-9a-f]{8})(?:\.(?:full|last))?⟧")
NEVER_SEND = re.compile(r"⟦NS_[0-9a-f]{8}⟧")
SLOT_KINDS = (
    "secret", "password", "GSTIN", "PAN", "IFSC", "Aadhaar number", "Aadhaar VID", "UPI ID", "voter ID",
    "passport number", "card number", "SSN", "EIN", "routing number", "bank account",
)  # fmt: skip
SLOT = re.compile(r"\[(?:" + "|".join(re.escape(k) for k in SLOT_KINDS) + r")\]")
# Everything in L1 that later passes must leave alone (never-send rescrub, name matching).
L1_MARKS = re.compile(f"{TOKEN.pattern}|{NEVER_SEND.pattern}|{SLOT.pattern}")
