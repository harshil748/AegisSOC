"""Lightweight cross-source identity resolution.

Real deployments would resolve identities via an IdP/AD directory sync;
for the demo we normalize casing/domain prefixes and maintain a small alias
table so the same human shows up as one entity regardless of which log
source spelled their name differently.
"""

from __future__ import annotations

ALIASES: dict[str, str] = {
    "jdoe": "jdoe",
    "john.doe": "jdoe",
    "asmith": "asmith",
    "alice.smith": "asmith",
    "mchen": "mchen",
    "administrator": "administrator",
    "svc-backup": "svc-backup",
}


def resolve_user(raw_user: str | None) -> str | None:
    if not raw_user:
        return None
    cleaned = raw_user.split("\\")[-1].strip().lower()
    return ALIASES.get(cleaned, cleaned)


def resolve_host(raw_host: str | None) -> str | None:
    if not raw_host:
        return None
    return raw_host.strip().upper()
