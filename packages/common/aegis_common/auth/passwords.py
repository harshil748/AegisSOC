"""Password hashing helpers using bcrypt directly.

passlib 1.7.x is incompatible with bcrypt >= 4.1 (missing ``__about__`` and
stricter 72-byte checks), so we call bcrypt ourselves.
"""

from __future__ import annotations

import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False
