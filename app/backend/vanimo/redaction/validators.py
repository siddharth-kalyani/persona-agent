"""Checksum and structure validators for regulated identifiers (Tier R, architecture §7.1).

Detection is by pattern *and* validation, so a random 12-digit number isn't flagged as an
Aadhaar unless its Verhoeff checksum holds. These run in our own code: no AWS or Microsoft
service covers Aadhaar, PAN, GSTIN, IFSC, UPI or US EIN (architecture §0 decision 9).
"""

from __future__ import annotations

# --- Verhoeff (Aadhaar, VID) ------------------------------------------------------------------
_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]
_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def verhoeff_valid(digits: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _D[c][_P[i % 8][int(ch)]]
    return c == 0


def verhoeff_check_digit(digits: str) -> str:
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _D[c][_P[(i + 1) % 8][int(ch)]]
    return str(_INV[c])


def aadhaar_valid(digits: str) -> bool:
    # 12 digits, first digit 2-9 (UIDAI never issues 0/1), Verhoeff checksum.
    return len(digits) == 12 and digits.isdigit() and digits[0] not in "01" and verhoeff_valid(digits)


# --- PAN ---------------------------------------------------------------------------------------
PAN_ENTITY = set("ABCFGHJLPT")  # 4th character: P person, C company, H HUF, F firm, …


def pan_valid(value: str) -> bool:
    v = value.upper()
    return len(v) == 10 and v[:5].isalpha() and v[5:9].isdigit() and v[9].isalpha() and v[3] in PAN_ENTITY


# --- GSTIN (15 chars: 2-digit state + PAN + entity + 'Z' + checksum) ----------------------------
_GST_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gstin_check_char(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14.upper()):
        v = _GST_CHARS.index(ch) * (2 if i % 2 else 1)
        total += v // 36 + v % 36
    return _GST_CHARS[(36 - total % 36) % 36]


def gstin_valid(value: str) -> bool:
    v = value.upper()
    if len(v) != 15 or not v[:2].isdigit() or not (1 <= int(v[:2]) <= 38) or not pan_valid(v[2:12]):
        return False
    if any(c not in _GST_CHARS for c in v):
        return False
    return gstin_check_char(v[:14]) == v[14]


# --- IFSC ----------------------------------------------------------------------------------------
def ifsc_valid(value: str) -> bool:
    v = value.upper()
    return len(v) == 11 and v[:4].isalpha() and v[4] == "0" and v[5:].isalnum()


# --- Luhn (payment cards) ----------------------------------------------------------------------
def luhn_valid(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def card_valid(digits: str) -> bool:
    if not (13 <= len(digits) <= 19) or not luhn_valid(digits):
        return False
    # Major network prefixes (Visa, Mastercard, Amex, Discover, RuPay, Diners, JCB).
    return digits[0] in "3456" or digits.startswith(("60", "65", "81", "82", "508", "353", "356"))


# --- US SSN / ITIN / EIN / ABA -------------------------------------------------------------------
def ssn_valid(digits: str) -> bool:
    if len(digits) != 9 or not digits.isdigit():
        return False
    area, group, serial = digits[:3], digits[3:5], digits[5:]
    if area in ("000", "666") or area.startswith("9") or group == "00" or serial == "0000":
        return False
    return digits not in ("123456789", "078051120", "219099999")  # well-known invalid/advertised


def itin_valid(digits: str) -> bool:
    if len(digits) != 9 or not digits.startswith("9"):
        return False
    group = int(digits[3:5])
    return 50 <= group <= 65 or 70 <= group <= 88 or 90 <= group <= 92 or 94 <= group <= 99


EIN_PREFIXES = frozenset(
    "01 02 03 04 05 06 10 11 12 13 14 15 16 20 21 22 23 24 25 26 27 30 31 32 33 34 35 36 37 38 39 40 41 "
    "42 43 44 45 46 47 48 50 51 52 53 54 55 56 57 58 59 60 61 62 63 64 65 66 67 68 71 72 73 74 75 76 77 80 "
    "81 82 83 84 85 86 87 88 90 91 92 93 94 95 98 99".split()
)


def ein_valid(digits: str) -> bool:
    return len(digits) == 9 and digits.isdigit() and digits[:2] in EIN_PREFIXES


def aba_valid(digits: str) -> bool:
    if (
        len(digits) != 9
        or not digits.isdigit()
        or digits[:2] not in {f"{i:02d}" for i in (*range(0, 13), *range(21, 33), *range(61, 73), 80)}
    ):
        return False
    d = [int(c) for c in digits]
    return (3 * (d[0] + d[3] + d[6]) + 7 * (d[1] + d[4] + d[7]) + (d[2] + d[5] + d[8])) % 10 == 0
