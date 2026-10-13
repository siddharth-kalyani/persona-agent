"""Password hashing, password rules and session tokens for local sign-in.

scrypt (stdlib) with N=2^15, r=8, p=1 (~32 MB, OWASP-recommended floor). Hashes are
self-describing (`scrypt$N$r$p$salt$hash`) so parameters can be raised later.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import unicodedata

SESSION_PREFIX = "vnm_s_"
_N, _R, _P, _DKLEN = 2**15, 8, 1, 32
_MAXMEM = 64 * 1024 * 1024

MIN_LENGTH = 12
MAX_LENGTH = 128
_COMMON = frozenset(
    {"password1234", "password12345", "passw0rd1234", "qwerty123456", "123456789012", "welcome12345", "letmein12345"}
)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _normalise(password: str) -> bytes:
    # NFKC so the same passphrase typed on different keyboards/OSes hashes the same (NIST 800-63B).
    return unicodedata.normalize("NFKC", password).encode("utf-8")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(_normalise(password), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN, maxmem=_MAXMEM)
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = _unb64(digest)
        actual = hashlib.scrypt(
            _normalise(password), salt=_unb64(salt), n=int(n), r=int(r), p=int(p), dklen=len(expected), maxmem=_MAXMEM
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


# Verifying against this when the email is unknown keeps response times the same either way.
DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


class WeakPassword(ValueError):
    """`code` is safe to show the user."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def check_new_password(new: str, *, email: str, current: str | None = None) -> None:
    """NIST SP 800-63B style: length and a blocklist, no composition rules."""
    new = unicodedata.normalize("NFKC", new)
    if len(new) < MIN_LENGTH:
        raise WeakPassword("password_too_short")
    if len(new) > MAX_LENGTH:
        raise WeakPassword("password_too_long")
    lowered = new.lower()
    if lowered in _COMMON or len(set(new)) < 4:
        raise WeakPassword("password_too_common")
    local_part = email.split("@", 1)[0].lower()
    if len(local_part) >= 4 and local_part in lowered:
        raise WeakPassword("password_contains_email")
    if current is not None and _normalise(new) == _normalise(current):
        raise WeakPassword("password_unchanged")


def new_one_time_password() -> str:
    """16 characters from an unambiguous alphabet, in groups for easy typing."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
    raw = "".join(secrets.choice(alphabet) for _ in range(16))
    return "-".join(raw[i : i + 4] for i in range(0, 16, 4))


def new_session_token() -> str:
    return SESSION_PREFIX + secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
