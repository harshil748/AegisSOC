"""Append-only repository for the audit log. No function here ever issues
an UPDATE or DELETE against ``audit_events`` -- ``append_event`` is an
INSERT, and everything else is a read."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_common.utils.helpers import utcnow

from audit_core.hashchain import GENESIS_HASH, compute_record_hash
from audit_core.models import AuditEventORM
from audit_core.schemas import AuditEventIn

# Single global sequence counter guarded by the DB transaction (max(sequence)+1).
# For Postgres under concurrent writers this is enforced by the unique index
# on `sequence` plus a retry at the caller; for the single-writer sync-mode
# demo this is never a contention issue.


async def _next_sequence(session: AsyncSession) -> int:
    result = await session.execute(select(func.max(AuditEventORM.sequence)))
    current_max = result.scalar()
    return (current_max or 0) + 1


async def _last_hash(session: AsyncSession) -> str:
    result = await session.execute(
        select(AuditEventORM.record_hash).order_by(AuditEventORM.sequence.desc()).limit(1)
    )
    row = result.scalar()
    return row or GENESIS_HASH


async def append_event(session: AsyncSession, event: AuditEventIn) -> AuditEventORM:
    sequence = await _next_sequence(session)
    prev_hash = await _last_hash(session)
    timestamp = utcnow()

    record_hash = compute_record_hash(
        sequence=sequence,
        prev_hash=prev_hash,
        tenant_id=event.tenant_id,
        actor=event.actor,
        actor_type=event.actor_type,
        action=event.action,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        timestamp=timestamp,
        details=event.details,
        prompt_hash=event.prompt_hash,
        evidence_refs=event.evidence_refs,
    )

    record = AuditEventORM(
        audit_id=str(uuid.uuid4()),
        sequence=sequence,
        tenant_id=event.tenant_id,
        actor=event.actor,
        actor_type=event.actor_type,
        action=event.action,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        timestamp=timestamp,
        details=event.details,
        prompt_hash=event.prompt_hash,
        evidence_refs=event.evidence_refs,
        prev_hash=prev_hash,
        record_hash=record_hash,
    )
    session.add(record)
    await session.flush()
    return record


async def query_events(
    session: AsyncSession,
    *,
    resource_id: str | None = None,
    resource_type: str | None = None,
    actor: str | None = None,
    actor_type: str | None = None,
    action: str | None = None,
    tenant_id: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 100,
) -> list[AuditEventORM]:
    stmt = select(AuditEventORM)
    if resource_id:
        stmt = stmt.where(AuditEventORM.resource_id == resource_id)
    if resource_type:
        stmt = stmt.where(AuditEventORM.resource_type == resource_type)
    if actor:
        stmt = stmt.where(AuditEventORM.actor == actor)
    if actor_type:
        stmt = stmt.where(AuditEventORM.actor_type == actor_type)
    if action:
        stmt = stmt.where(AuditEventORM.action == action)
    if tenant_id:
        stmt = stmt.where(AuditEventORM.tenant_id == tenant_id)
    if since:
        stmt = stmt.where(AuditEventORM.timestamp >= since)
    if until:
        stmt = stmt.where(AuditEventORM.timestamp <= until)
    stmt = stmt.order_by(AuditEventORM.sequence.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def verify_chain(session: AsyncSession) -> tuple[bool, int, int | None, str]:
    """Recomputes every record's hash from its stored fields and checks
    prev_hash linkage across the *entire* log (the hash chain is a single
    global sequence spanning all tenants by design, so it cannot be verified
    correctly on a tenant-filtered subset). Returns
    (valid, events_checked, first_broken_sequence, detail)."""

    stmt = select(AuditEventORM).order_by(AuditEventORM.sequence.asc())
    result = await session.execute(stmt)
    records = list(result.scalars().all())

    expected_prev = GENESIS_HASH
    for idx, record in enumerate(records):
        if record.prev_hash != expected_prev:
            return False, idx, record.sequence, f"prev_hash mismatch at sequence={record.sequence}"

        recomputed = compute_record_hash(
            sequence=record.sequence,
            prev_hash=record.prev_hash,
            tenant_id=record.tenant_id,
            actor=record.actor,
            actor_type=record.actor_type,
            action=record.action,
            resource_type=record.resource_type,
            resource_id=record.resource_id,
            timestamp=record.timestamp,
            details=record.details,
            prompt_hash=record.prompt_hash,
            evidence_refs=record.evidence_refs,
        )
        if recomputed != record.record_hash:
            return False, idx, record.sequence, f"record_hash mismatch at sequence={record.sequence} (tampered content)"

        expected_prev = record.record_hash

    return True, len(records), None, "chain intact"
