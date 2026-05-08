from __future__ import annotations

import hmac

import bcrypt
from passlib.context import CryptContext

# Prefer pbkdf2_sha256 because it doesn't depend on passlib+bcrypt integration.
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    default="pbkdf2_sha256",
    deprecated="auto",
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify passwords across supported legacy/new hash formats.

    - New hashes: pbkdf2_sha256 (passlib)
    - Legacy hashes: bcrypt ($2...) verified via bcrypt module directly
    """
    if not password_hash:
        return False

    if password_hash.startswith("$2"):
        try:
            return hmac.compare_digest(
                bcrypt.hashpw(password.encode("utf-8"), password_hash.encode("utf-8")),
                password_hash.encode("utf-8"),
            )
        except ValueError:
            return False

    try:
        return pwd_context.verify(password, password_hash)
    except Exception:
        return False
