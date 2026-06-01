"""Async repository for the approval workflow: request -> decide -> execute
(dry-run SOAR adapter) -> optional rollback. Every state transition is
mirrored to the audit sink."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_common.utils.helpers import utcnow

from approval_core.adapters import rollback_action, run_adapter
from approval_core.audit_client import AuditSink, build_event
from approval_core.models import ApprovalRequestORM, ExecutionRecordORM, RollbackRecordORM
from approval_core.schemas import CreateApprovalRequest

TERMINAL_STATUSES = {"rejected", "rolled_back"}


async def create_approval(session: AsyncSession, req: CreateApprovalRequest, audit: AuditSink) -> ApprovalRequestORM:
    record = ApprovalRequestORM(
        approval_id=str(uuid.uuid4()),
        tenant_id=req.tenant_id,
        action_id=req.action_id,
        case_id=req.case_id,
        action_class=req.action_class,
        title=req.title or req.action_class.replace("_", " ").title(),
        description=req.description,
        disruptive=req.disruptive,
        dry_run=req.dry_run,
        requested_by=req.requested_by,
        status="pending",
        payload=req.payload,
    )
    session.add(record)
    await session.flush()
    await audit.send(
        build_event(
            actor=req.requested_by,
            actor_type="system",
            action="approval_requested",
            resource_type="approval",
            resource_id=record.approval_id,
            details={"action_id": req.action_id, "case_id": req.case_id, "action_class": req.action_class, "disruptive": req.disruptive},
            tenant_id=req.tenant_id,
        )
    )
    return record


async def get_approval(session: AsyncSession, approval_id: str) -> ApprovalRequestORM | None:
    return await session.get(ApprovalRequestORM, approval_id)


async def list_approvals(
    session: AsyncSession, status: str | None = None, case_id: str | None = None, limit: int = 50
) -> list[ApprovalRequestORM]:
    stmt = select(ApprovalRequestORM)
    if status:
        stmt = stmt.where(ApprovalRequestORM.status == status)
    if case_id:
        stmt = stmt.where(ApprovalRequestORM.case_id == case_id)
    stmt = stmt.order_by(ApprovalRequestORM.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def decide_approval(
    session: AsyncSession, approval_id: str, decided_by: str, decision: str, rationale: str, audit: AuditSink
) -> ApprovalRequestORM | None:
    record = await session.get(ApprovalRequestORM, approval_id)
    if record is None:
        return None
    if record.status != "pending":
        raise ValueError(f"approval already in terminal/decided state '{record.status}'")

    record.status = "approved" if decision == "approved" else "rejected"
    record.decision = decision
    record.decided_by = decided_by
    record.rationale = rationale
    record.decided_at = utcnow()
    record.updated_at = utcnow()
    await session.flush()

    await audit.send(
        build_event(
            actor=decided_by,
            actor_type="user",
            action=f"approval_{decision}",
            resource_type="approval",
            resource_id=approval_id,
            details={"rationale": rationale, "action_class": record.action_class, "case_id": record.case_id},
            tenant_id=record.tenant_id,
        )
    )
    return record


async def execute_action(
    session: AsyncSession, approval_id: str, executed_by: str, audit: AuditSink
) -> ExecutionRecordORM | None:
    record = await session.get(ApprovalRequestORM, approval_id)
    if record is None:
        return None
    if record.status not in {"approved"}:
        raise ValueError(f"cannot execute approval in status '{record.status}' -- must be 'approved'")

    ctx: dict[str, Any] = {
        "case_id": record.case_id,
        "title": record.title,
        "parameters": record.payload.get("parameters", {}),
    }
    result = await run_adapter(record.action_class, ctx)

    execution = ExecutionRecordORM(
        execution_id=str(uuid.uuid4()),
        approval_id=approval_id,
        action_class=record.action_class,
        adapter=result.get("adapter", "unknown"),
        dry_run=True,
        status=result.get("status", "failed"),
        result=result,
        rollback_token=result.get("rollback_token"),
        executed_by=executed_by,
    )
    session.add(execution)

    record.status = "executed"
    record.updated_at = utcnow()
    await session.flush()

    await audit.send(
        build_event(
            actor=executed_by,
            actor_type="system",
            action="action_executed_dry_run",
            resource_type="approval",
            resource_id=approval_id,
            details={"execution_id": execution.execution_id, "adapter": execution.adapter, "result": result},
            tenant_id=record.tenant_id,
        )
    )
    return execution


async def get_latest_execution(session: AsyncSession, approval_id: str) -> ExecutionRecordORM | None:
    stmt = (
        select(ExecutionRecordORM)
        .where(ExecutionRecordORM.approval_id == approval_id)
        .order_by(ExecutionRecordORM.executed_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalars().first()


async def list_executions(session: AsyncSession, approval_id: str) -> list[ExecutionRecordORM]:
    stmt = select(ExecutionRecordORM).where(ExecutionRecordORM.approval_id == approval_id).order_by(ExecutionRecordORM.executed_at)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def rollback_execution(
    session: AsyncSession, approval_id: str, initiated_by: str, reason: str, audit: AuditSink
) -> RollbackRecordORM | None:
    approval = await session.get(ApprovalRequestORM, approval_id)
    if approval is None:
        return None
    execution = await get_latest_execution(session, approval_id)
    if execution is None:
        raise ValueError("no execution record found for this approval; nothing to roll back")

    result = await rollback_action(execution.action_class, execution.rollback_token, execution.result)

    rollback = RollbackRecordORM(
        rollback_id=str(uuid.uuid4()),
        execution_id=execution.execution_id,
        approval_id=approval_id,
        initiated_by=initiated_by,
        reason=reason,
        status=result.get("status", "failed"),
        result=result,
    )
    session.add(rollback)

    if result.get("status") == "success":
        approval.status = "rolled_back"
        approval.updated_at = utcnow()
    await session.flush()

    await audit.send(
        build_event(
            actor=initiated_by,
            actor_type="user",
            action="action_rolled_back",
            resource_type="approval",
            resource_id=approval_id,
            details={"execution_id": execution.execution_id, "reason": reason, "result": result},
            tenant_id=approval.tenant_id,
        )
    )
    return rollback
