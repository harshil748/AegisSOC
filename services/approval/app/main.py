"""AegisSOC Approval Service.

Human-in-the-loop gate for every disruptive action recommendation.
Nothing marked ``disruptive=true`` by response_policy may execute without
an explicit approval decision recorded here. Execution itself only ever
runs a dry-run SOAR adapter simulation -- this service never calls a real
external system -- and every request/decision/execution/rollback is
mirrored to the audit service for non-repudiation. This is the primary
control evaluated in the "approval bypass" section of
docs/threat-model/THREAT_MODEL.md.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query

from aegis_common.auth.rbac import Role, current_user_dependency, require_roles, role_satisfies
from aegis_common.config import Settings
from aegis_common.service import create_service_app

from approval_core import repository
from approval_core.adapters import ADAPTERS
from approval_core.audit_client import HTTPAuditSink
from approval_core.db import init_db, sessionmaker_for
from approval_core.schemas import (
    ApprovalOut,
    CreateApprovalRequest,
    DecisionRequest,
    ExecuteRequest,
    ExecutionOut,
    RollbackOut,
    RollbackRequest,
)

settings = Settings()
logger = logging.getLogger("aegis.approval")

SERVICE_NAME = "approval"
AUDIT_URL = os.getenv("AUDIT_URL", "http://audit:8010")
_state: dict = {}

get_current_user = current_user_dependency(settings.jwt_secret, settings.jwt_algorithm)
require_analyst = require_roles(Role.ANALYST.value, get_current_user)
require_senior = require_roles(Role.SENIOR_ANALYST.value, get_current_user)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db(settings.postgres_dsn)
    _state["sessionmaker"] = sessionmaker_for(settings.postgres_dsn)
    _state["audit"] = HTTPAuditSink(AUDIT_URL)
    logger.info("approval_service_started")
    yield


app = create_service_app(
    service_name=SERVICE_NAME,
    description="Human approval workflow, dry-run SOAR adapters, rollback recording. Never auto-executes.",
    lifespan=lifespan,
)


@app.post("/api/v1/approvals", response_model=ApprovalOut, tags=["approvals"])
async def create_request(req: CreateApprovalRequest) -> ApprovalOut:
    """Unauthenticated/system-facing: response_policy or the demo orchestrator
    calls this whenever a disruptive action needs a human decision."""

    sessionmaker = _state["sessionmaker"]
    async with sessionmaker() as session:
        async with session.begin():
            record = await repository.create_approval(session, req, _state["audit"])
        return ApprovalOut.model_validate(record)


@app.get("/api/v1/approvals", response_model=list[ApprovalOut], tags=["approvals"])
async def list_pending(
    status: str | None = Query(default="pending"),
    case_id: str | None = None,
    limit: int = Query(50, le=200),
    _user=Depends(require_analyst),
) -> list[ApprovalOut]:
    sessionmaker = _state["sessionmaker"]
    async with sessionmaker() as session:
        records = await repository.list_approvals(session, status=status, case_id=case_id, limit=limit)
        return [ApprovalOut.model_validate(r) for r in records]


@app.get("/api/v1/approvals/{approval_id}", response_model=ApprovalOut, tags=["approvals"])
async def get_approval(approval_id: str, _user=Depends(require_analyst)) -> ApprovalOut:
    sessionmaker = _state["sessionmaker"]
    async with sessionmaker() as session:
        record = await repository.get_approval(session, approval_id)
        if record is None:
            raise HTTPException(status_code=404, detail="approval_not_found")
        return ApprovalOut.model_validate(record)


@app.post("/api/v1/approvals/{approval_id}/decide", response_model=ApprovalOut, tags=["approvals"])
async def decide(approval_id: str, req: DecisionRequest, user=Depends(require_analyst)) -> ApprovalOut:
    """Any analyst may reject or approve a non-disruptive action; approving a
    *disruptive* action requires senior_analyst or admin -- the actual
    escalation boundary the platform is built around."""

    sessionmaker = _state["sessionmaker"]
    async with sessionmaker() as session:
        existing = await repository.get_approval(session, approval_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="approval_not_found")
        if (
            req.decision == "approved"
            and existing.disruptive
            and not role_satisfies(user.role, Role.SENIOR_ANALYST.value)
        ):
            raise HTTPException(
                status_code=403, detail="requires_role>=senior_analyst to approve a disruptive action"
            )

        async with session.begin():
            try:
                record = await repository.decide_approval(
                    session, approval_id, user.username, req.decision, req.rationale, _state["audit"]
                )
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        if record is None:
            raise HTTPException(status_code=404, detail="approval_not_found")
        return ApprovalOut.model_validate(record)


@app.post("/api/v1/approvals/{approval_id}/execute", response_model=ExecutionOut, tags=["execution"])
async def execute(approval_id: str, req: ExecuteRequest, _user=Depends(require_analyst)) -> ExecutionOut:
    """Runs the dry-run SOAR adapter for an already-approved action. Always
    simulated: no real external system is ever called."""

    sessionmaker = _state["sessionmaker"]
    async with sessionmaker() as session:
        async with session.begin():
            try:
                execution = await repository.execute_action(session, approval_id, req.executed_by, _state["audit"])
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        if execution is None:
            raise HTTPException(status_code=404, detail="approval_not_found")
        return ExecutionOut.model_validate(execution)


@app.get("/api/v1/approvals/{approval_id}/executions", response_model=list[ExecutionOut], tags=["execution"])
async def executions(approval_id: str, _user=Depends(require_analyst)) -> list[ExecutionOut]:
    sessionmaker = _state["sessionmaker"]
    async with sessionmaker() as session:
        records = await repository.list_executions(session, approval_id)
        return [ExecutionOut.model_validate(r) for r in records]


@app.post("/api/v1/approvals/{approval_id}/rollback", response_model=RollbackOut, tags=["execution"])
async def rollback(approval_id: str, req: RollbackRequest, _user=Depends(require_senior)) -> RollbackOut:
    sessionmaker = _state["sessionmaker"]
    async with sessionmaker() as session:
        async with session.begin():
            try:
                record = await repository.rollback_execution(
                    session, approval_id, req.initiated_by, req.reason, _state["audit"]
                )
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        if record is None:
            raise HTTPException(status_code=404, detail="approval_not_found")
        return RollbackOut.model_validate(record)


@app.get("/api/v1/adapters", tags=["execution"])
async def list_adapters() -> dict:
    return {"action_classes": list(ADAPTERS.keys())}
