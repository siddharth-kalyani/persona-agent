"""Field encryption and keyed hashes for user data (the M1 "vault").

* Per-user AES-256-GCM keys encrypt display fields in the Sources index (names, addresses,
  subjects, chat topics) and never-send terms. Plaintext exists only in memory and on the
  owner's own screen. Per-tenant keys encrypt tenant settings such as client account names.
* Per-tenant HMAC keys turn identifiers (an email address, a chat ID) into rule keys, so
  exclusion rules never store the raw identifier (architecture §6.5).

Keys derive from one master key with HKDF (local/dev). Before external customers this moves to
KMS: a per-tenant CMK with per-user data keys, so deleting a user's key crypto-shreds their data
(architecture §8.2; tracked in app/README.md "Known deviations").
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import uuid
from functools import lru_cache

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

PREFIX = "v1:"


class VaultError(Exception):
    pass


class Vault:
    def __init__(self, master_key: str) -> None:
        if len(master_key) < 32:
            raise VaultError("vault master key must be at least 32 characters")
        self._master = master_key.encode()

    @lru_cache(maxsize=4096)  # noqa: B019 - one Vault per process; keys are small
    def _key(self, info: str) -> bytes:
        return HKDF(algorithm=hashes.SHA256(), length=32, salt=b"vanimo-vault-v1", info=info.encode()).derive(
            self._master
        )

    # --- Encryption -------------------------------------------------------------------------
    def encrypt_user(self, tenant: uuid.UUID, user: uuid.UUID, plaintext: str | None, purpose: str) -> str | None:
        return self._encrypt(f"user/{tenant}/{user}", plaintext, purpose)

    def decrypt_user(self, tenant: uuid.UUID, user: uuid.UUID, token: str | None, purpose: str) -> str | None:
        return self._decrypt(f"user/{tenant}/{user}", token, purpose)

    def encrypt_tenant(self, tenant: uuid.UUID, plaintext: str | None, purpose: str) -> str | None:
        return self._encrypt(f"tenant/{tenant}", plaintext, purpose)

    def decrypt_tenant(self, tenant: uuid.UUID, token: str | None, purpose: str) -> str | None:
        return self._decrypt(f"tenant/{tenant}", token, purpose)

    def _encrypt(self, scope: str, plaintext: str | None, purpose: str) -> str | None:
        if plaintext is None:
            return None
        nonce = os.urandom(12)
        # The purpose is bound as associated data: a subject can't be swapped in as a name.
        ct = AESGCM(self._key("enc/" + scope)).encrypt(nonce, plaintext.encode(), f"{scope}|{purpose}".encode())
        return PREFIX + base64.urlsafe_b64encode(nonce + ct).decode()

    def _decrypt(self, scope: str, token: str | None, purpose: str) -> str | None:
        if token is None:
            return None
        if not token.startswith(PREFIX):
            raise VaultError("unknown ciphertext version")
        raw = base64.urlsafe_b64decode(token[len(PREFIX) :])
        try:
            plain = AESGCM(self._key("enc/" + scope)).decrypt(raw[:12], raw[12:], f"{scope}|{purpose}".encode())
        except Exception as exc:  # InvalidTag: wrong key, scope or purpose
            raise VaultError("decryption failed") from exc
        return plain.decode()

    # --- Keyed hashes -----------------------------------------------------------------------
    def key_hash(self, tenant: uuid.UUID, kind: str, value: str) -> str:
        """Stable per-tenant HMAC of a normalised identifier (64 hex chars)."""
        return hmac.new(self._key(f"hmac/{tenant}"), f"{kind}:{value}".encode(), hashlib.sha256).hexdigest()


def normalise_identifier(kind: str, value: str) -> str:
    value = value.strip()
    if kind in ("person", "address", "domain"):
        return value.lower().rstrip(".")
    return value
