"""Gateway authentication: JWT issuance for a small seeded set of demo users.

This is intentionally a minimal, self-contained user store (no separate
identity service) since AegisSOC's threat model treats the gateway as the
single trust boundary between the analyst browser and the internal service
mesh -- everything behind it trusts ``X-Aegis-*`` headers set here after JWT
verification (see ``aegis_common.auth.rbac``).
"""

from __future__ import annotations

from dataclasses import dataclass

from aegis_common.auth.jwt import TokenPayload, create_access_token, decode_access_token
from aegis_common.auth.passwords import hash_password, verify_password
from aegis_common.auth.rbac import Role
from aegis_common.config import Settings


@dataclass(frozen=True)
class DemoUser:
    user_id: str
    username: str
    password_hash: str
    role: str
    tenant_id: str = "default"
    display_name: str = ""


def _seed_users() -> dict[str, DemoUser]:
    # Demo-only credentials (documented in README/docs/DEMO.md). Passwords
    # hashed with the same bcrypt helper real user records would use, so
    # swapping this dict for a Postgres-backed user table later is a
    # drop-in change, not a rewrite.
    seeds = [
        ("analyst", "analyst123", Role.ANALYST.value, "Alex Analyst"),
        ("senior", "senior123", Role.SENIOR_ANALYST.value, "Sam Senior-Analyst"),
        ("admin", "admin123", Role.ADMIN.value, "Ada Admin"),
    ]
    return {
        username: DemoUser(
            user_id=f"user-{username}",
            username=username,
            password_hash=hash_password(password),
            role=role,
            display_name=display_name,
        )
        for username, password, role, display_name in seeds
    }


_USERS = _seed_users()


def authenticate(username: str, password: str) -> DemoUser | None:
    user = _USERS.get(username)
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


def issue_token(user: DemoUser, settings: Settings) -> str:
    return create_access_token(
        subject=user.user_id,
        username=user.username,
        role=user.role,
        tenant_id=user.tenant_id,
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expires_minutes=settings.access_token_expire_minutes,
        extra_claims={"display_name": user.display_name},
    )


def decode_token(token: str, settings: Settings) -> TokenPayload:
    return decode_access_token(token, settings.jwt_secret, settings.jwt_algorithm)


def list_seeded_usernames() -> list[str]:
    return sorted(_USERS.keys())
