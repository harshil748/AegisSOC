"""Role-based access control primitives.

Roles are hierarchical: admin > senior_analyst > analyst. Every endpoint
declares the *minimum* role required via ``require_roles`` and any higher
role automatically satisfies it.
"""

from __future__ import annotations

from enum import Enum
from typing import Callable

from fastapi import Depends, Header, HTTPException, status

from aegis_common.auth.jwt import TokenPayload, decode_access_token


class Role(str, Enum):
    ANALYST = "analyst"
    SENIOR_ANALYST = "senior_analyst"
    ADMIN = "admin"


ROLE_HIERARCHY: dict[str, int] = {
    Role.ANALYST.value: 1,
    Role.SENIOR_ANALYST.value: 2,
    Role.ADMIN.value: 3,
}


def role_satisfies(actual_role: str, minimum_role: str) -> bool:
    return ROLE_HIERARCHY.get(actual_role, 0) >= ROLE_HIERARCHY.get(minimum_role, 999)


def current_user_dependency(jwt_secret: str, jwt_algorithm: str = "HS256") -> Callable:
    """Build a FastAPI dependency that decodes the bearer/gateway-forwarded JWT."""

    async def _dep(
        authorization: str | None = Header(default=None),
        x_aegis_user: str | None = Header(default=None),
        x_aegis_role: str | None = Header(default=None),
        x_aegis_tenant: str | None = Header(default=None),
    ) -> TokenPayload:
        # Services behind frontend_gateway trust forwarded identity headers;
        # services called directly (or in tests) fall back to decoding the
        # bearer token themselves.
        if x_aegis_user and x_aegis_role:
            return TokenPayload(
                sub=x_aegis_user,
                username=x_aegis_user,
                role=x_aegis_role,
                tenant_id=x_aegis_tenant or "default",
            )
        if authorization and authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1]
            try:
                return decode_access_token(token, jwt_secret, jwt_algorithm)
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"invalid_token: {exc}",
                ) from exc
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_credentials")

    return _dep


def require_roles(minimum_role: str, get_current_user: Callable) -> Callable:
    """Build a dependency enforcing a minimum role for an endpoint."""

    async def _checker(user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
        if not role_satisfies(user.role, minimum_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"requires_role>={minimum_role}",
            )
        return user

    return _checker
