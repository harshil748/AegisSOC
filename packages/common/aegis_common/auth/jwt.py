"""JWT issuance/verification shared by frontend_gateway and downstream services."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from pydantic import BaseModel


class TokenPayload(BaseModel):
    sub: str
    username: str
    role: str
    tenant_id: str = "default"
    exp: datetime | None = None
    iat: datetime | None = None


def create_access_token(
    *,
    subject: str,
    username: str,
    role: str,
    tenant_id: str,
    secret: str,
    algorithm: str = "HS256",
    expires_minutes: int = 480,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "username": username,
        "role": role,
        "tenant_id": tenant_id,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_access_token(token: str, secret: str, algorithm: str = "HS256") -> TokenPayload:
    data = jwt.decode(token, secret, algorithms=[algorithm])
    return TokenPayload(**data)
