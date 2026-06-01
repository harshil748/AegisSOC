"""Optional integrity hash chain over the append-only audit log.

Each record's hash is a SHA-256 over its own canonical fields plus the
previous record's hash, so any single edited/deleted/reordered row breaks
the chain from that point forward -- the same tamper-evidence idea used by
certificate transparency logs and blockchains, without any of the
distributed-consensus machinery (this is a single system of record, not a
distributed ledger).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

GENESIS_HASH = "0" * 64


def _canonical(value: Any) -> Any:
    if isinstance(value, datetime):
        # SQLite drops tzinfo on round-trip (returns a naive datetime that was
        # always UTC), while Postgres preserves it. Normalize both to the same
        # naive-UTC microsecond-precision string so a value hashed at insert
        # time and the same value re-read from either backend at verify time
        # always produce an identical canonical representation.
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value.isoformat(timespec="microseconds")
    return value


def compute_record_hash(
    *,
    sequence: int,
    prev_hash: str,
    tenant_id: str,
    actor: str,
    actor_type: str,
    action: str,
    resource_type: str,
    resource_id: str,
    timestamp: datetime,
    details: dict[str, Any],
    prompt_hash: str | None,
    evidence_refs: list[str],
) -> str:
    payload = {
        "sequence": sequence,
        "prev_hash": prev_hash,
        "tenant_id": tenant_id,
        "actor": actor,
        "actor_type": actor_type,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "timestamp": _canonical(timestamp),
        "details": details,
        "prompt_hash": prompt_hash,
        "evidence_refs": evidence_refs,
    }
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
