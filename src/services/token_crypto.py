"""
src/services/token_crypto.py
Fernet encryption for OAuth refresh tokens at rest (Gmail connector M0).

Key management:
  * The key lives in the ``GMAIL_TOKEN_ENCRYPTION_KEY`` env var — a standard
    Fernet key (urlsafe base64, 32 bytes). Generate one with:
        python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  * Deliberately separate from JWT_SECRET (design doc §3 Token Storage).
  * ``KEY_VERSION`` is persisted alongside ciphertext so a future key rotation
    can decrypt old rows.

Fail-closed behavior:
  * Missing/invalid key → ``TokenCryptoError`` on encrypt AND decrypt.
    Callers must treat this as "feature unavailable", never store plaintext.
  * This module NEVER logs token material (plaintext or ciphertext).
"""
from __future__ import annotations

import os

__all__ = [
    "KEY_VERSION",
    "TokenCryptoError",
    "encryption_key_present",
    "encrypt_token",
    "decrypt_token",
]

ENV_KEY_NAME = "GMAIL_TOKEN_ENCRYPTION_KEY"
KEY_VERSION = "v1"


class TokenCryptoError(RuntimeError):
    """Raised when token encryption/decryption cannot be performed safely."""


def _fernet():
    """Build a Fernet instance from the env key. Raises TokenCryptoError."""
    key = (os.getenv(ENV_KEY_NAME) or "").strip()
    if not key:
        raise TokenCryptoError(
            f"{ENV_KEY_NAME} is not set — refusing to handle OAuth tokens. "
            "Generate a Fernet key and configure it before enabling Gmail sync."
        )
    try:
        from cryptography.fernet import Fernet

        return Fernet(key.encode("utf-8"))
    except TokenCryptoError:
        raise
    except Exception as exc:
        # Do not include the key (or any derivative) in the error message.
        raise TokenCryptoError(
            f"{ENV_KEY_NAME} is not a valid Fernet key: {type(exc).__name__}"
        ) from None


def encryption_key_present() -> bool:
    """True when a (non-empty) encryption key env var is configured."""
    return bool((os.getenv(ENV_KEY_NAME) or "").strip())


def encrypt_token(plaintext: str) -> str:
    """Encrypt an OAuth token for storage. Raises TokenCryptoError fail-closed."""
    if not isinstance(plaintext, str) or not plaintext:
        raise TokenCryptoError("Refusing to encrypt an empty token")
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a stored OAuth token. Raises TokenCryptoError fail-closed."""
    if not isinstance(ciphertext, str) or not ciphertext:
        raise TokenCryptoError("Refusing to decrypt an empty ciphertext")
    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except TokenCryptoError:
        raise
    except Exception as exc:
        # InvalidToken or corrupt input — never echo the ciphertext back.
        raise TokenCryptoError(
            f"Token decryption failed: {type(exc).__name__}"
        ) from None
