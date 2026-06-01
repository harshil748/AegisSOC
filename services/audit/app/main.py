"""AegisSOC Audit Service.

Append-only log of every AI recommendation, retrieved evidence, prompt
hash, human decision, and override across the platform. This is the
system of record used for compliance, incident post-mortems, and the
groundedness/hallucination evaluation pipeline (docs/EVALUATION.md).

Writes are intentionally simple and never mutate/delete existing rows; a
SHA-256 hash chain over the sequence of records gives tamper-evidence for
anyone who might try to edit history directly at the database layer.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, Query

from aegis_common.auth.rbac import Role, current_user_dependency, require_roles
from aegis_common.config import Settings
from aegis_common.observability import EVENTS_PROCESSED
from aegis_common.service import create_service_app

from audit_core import repository
from audit_core.db import init_db, sessionmaker_for
from audit_core.schemas import AuditEventIn, AuditEventOut, ChainVerificationResult

settings = Settings()
logger = logging.getLogger("aegis.audit")

SERVICE_NAME = "audit"
_state: dict = {}

get_current_user = current_user_dependency(settings.jwt_secret, settings.jwt_algorithm)
require_analyst = require_roles(Role.ANALYST.value, get_current_user)
require_admin = require_roles(Role.ADMIN.value, get_current_user)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db(settings.postgres_dsn)
    _state["sessionmaker"] = sessionmaker_for(settings.postgres_dsn)
    logger.info("audit_service_started")
    yield


app = create_service_app(
    service_name=SERVICE_NAME,
    description="Append-only audit log with SHA-256 hash-chain integrity verification.",
    lifespan=lifespan,
)


@app.post("/api/v1/audit", response_model=AuditEventOut, tags=["audit"])
async def record(event: AuditEventIn) -> AuditEventOut:
    """Unauthenticated/system-facing by design: every other service (and the
    frontend_gateway on behalf of users) mirrors state changes here. Trust
    boundary is the internal network / gateway, matching every other
    service's `/api/v1/internal/*` convention."""

    sessionmaker = _state["sessionmaker"]
    async with sessionmaker() as session:
        async with session.begin():
            out = await repository.append_event(session, event)
        EVENTS_PROCESSED.labels(service=SERVICE_NAME, stage="record", outcome=event.action).inc()
        return AuditEventOut.model_validate(out)


@app.get("/api/v1/audit", response_model=list[AuditEventOut], tags=["audit"])
async def query(
    resource_id: str | None = None,
    resource_type: str | None = None,
    actor: str | None = None,
    actor_type: str | None = None,
    action: str | None = None,
    tenant_id: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(100, le=1000),
    _user=Depends(require_analyst),
) -> list[AuditEventOut]:
    sessionmaker = _state["sessionmaker"]
    async with sessionmaker() as session:
        records = await repository.query_events(
            session,
            resource_id=resource_id,
            resource_type=resource_type,
            actor=actor,
            actor_type=actor_type,
            action=action,
            tenant_id=tenant_id,
            since=since,
            until=until,
            limit=limit,
        )
        return [AuditEventOut.model_validate(r) for r in records]


@app.get("/api/v1/audit/verify", response_model=ChainVerificationResult, tags=["audit"])
async def verify(_user=Depends(require_admin)) -> ChainVerificationResult:
    """Recomputes the SHA-256 hash chain over the entire log to detect
    tampering. Admin-only: this is an integrity/compliance operation, not a
    routine analyst query."""

    sessionmaker = _state["sessionmaker"]
    async with sessionmaker() as session:
        valid, checked, broken_seq, detail = await repository.verify_chain(session)
        return ChainVerificationResult(
            tenant_id=None, events_checked=checked, valid=valid, first_broken_sequence=broken_seq, detail=detail
        )
