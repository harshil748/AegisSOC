"""JWT auth + RBAC helpers shared across AegisSOC services."""

from aegis_common.auth.jwt import create_access_token, decode_access_token, TokenPayload
from aegis_common.auth.rbac import (
    Role,
    ROLE_HIERARCHY,
    require_roles,
    current_user_dependency,
)
from aegis_common.auth.passwords import hash_password, verify_password

__all__ = [
    "create_access_token",
    "decode_access_token",
    "TokenPayload",
    "Role",
    "ROLE_HIERARCHY",
    "require_roles",
    "current_user_dependency",
    "hash_password",
    "verify_password",
]
