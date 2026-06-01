"""AegisSOC Case Management Service.

PostgreSQL-backed (SQLite fallback in sync/demo mode) case store: auto case
creation from alert clusters, timeline reconstruction, search/filter,
analyst feedback capture, and RBAC-aware endpoints (analyst / senior_analyst
/ admin).
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query

from aegis_common.auth.rbac import Role, current_user_dependency, require_roles
from aegis_common.config import Settings, TOPIC_ALERTS
from aegis_common.kafka.consumer import AegisConsumer
from aegis_common.observability import EVENTS_PROCESSED, QUEUE_LAG
from aegis_common.service import create_service_app

from case_core import repository
from case_core.db import init_db, sessionmaker_for
from case_core.schemas import (
    AssignRequest,
    CaseOut,
    CaseSearchParams,
    CreateCaseRequest,
    FeedbackOut,
    FeedbackRequest,
    StatusUpdateRequest,
)

settings = Settings()
logger = logging.getLogger("aegis.case_management")

SERVICE_NAME = "case_management"
_state: dict = {}

get_current_user = current_user_dependency(settings.jwt_secret, settings.jwt_algorithm)
require_analyst = require_roles(Role.ANALYST.value, get_current_user)
require_senior = require_roles(Role.SENIOR_ANALYST.value, get_current_user)


async def _handle_alert_message(message: dict) -> None:
    sessionmaker = _state["sessionmaker"]
    async with sessionmaker() as session:
        async with session.begin():
            await repository.upsert_case_from_alert(session, message)
    EVENTS_PROCESSED.labels(service=SERVICE_NAME, stage="auto_case", outcome="upserted").inc()


async def _consumer_loop(stop_event: asyncio.Event) -> None:
    consumer: AegisConsumer = _state["consumer"]
    while not stop_event.is_set():
        try:
            batch = await consumer.poll_batch()
            for message in batch:
                await _handle_alert_message(message)
            if not batch:
                await asyncio.sleep(1.0)
            QUEUE_LAG.labels(service=SERVICE_NAME, topic=TOPIC_ALERTS, group=SERVICE_NAME).set(consumer.lag())
        except Exception:
            logger.exception("consumer_loop_error")
            await asyncio.sleep(1.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db(settings.postgres_dsn)
    _state["sessionmaker"] = sessionmaker_for(settings.postgres_dsn)

    consumer = AegisConsumer(TOPIC_ALERTS, settings.kafka_bootstrap, group_id=SERVICE_NAME)
    await consumer.start()
    _state["consumer"] = consumer
    stop_event = asyncio.Event()
    task = asyncio.create_task(_consumer_loop(stop_event))
    _state["task"] = task
    logger.info("case_management_service_started")
    yield
    stop_event.set()
    task.cancel()
    await consumer.stop()


app = create_service_app(
    service_name=SERVICE_NAME,
    description="Postgres-backed case management, auto-clustering, timelines, RBAC.",
    lifespan=lifespan,
)


@app.post("/api/v1/cases", response_model=CaseOut, tags=["cases"])
async def create_case(req: CreateCaseRequest, _user=Depends(require_senior)) -> CaseOut:
    sessionmaker = _state["sessionmaker"]
    async with sessionmaker() as session:
        async with session.begin():
            case = await repository.create_case(session, req)
        return CaseOut.model_validate(case)


@app.get("/api/v1/cases", response_model=list[CaseOut], tags=["cases"])
async def list_cases(
    status: str | None = None,
    severity: str | None = None,
    assignee: str | None = None,
    text: str | None = None,
    tenant_id: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    _user=Depends(require_analyst),
) -> list[CaseOut]:
    sessionmaker = _state["sessionmaker"]
    params = CaseSearchParams(
        status=status, severity=severity, assignee=assignee, text=text, tenant_id=tenant_id, limit=limit, offset=offset
    )
    async with sessionmaker() as session:
        cases = await repository.search_cases(session, params)
        return [CaseOut.model_validate(c) for c in cases]


@app.get("/api/v1/cases/{case_id}", response_model=CaseOut, tags=["cases"])
async def get_case(case_id: str, _user=Depends(require_analyst)) -> CaseOut:
    sessionmaker = _state["sessionmaker"]
    async with sessionmaker() as session:
        case = await repository.get_case(session, case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="case_not_found")
        return CaseOut.model_validate(case)


@app.patch("/api/v1/cases/{case_id}/status", response_model=CaseOut, tags=["cases"])
async def patch_status(case_id: str, req: StatusUpdateRequest, _user=Depends(require_senior)) -> CaseOut:
    if req.status not in repository.VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"invalid_status; must be one of {sorted(repository.VALID_STATUSES)}")
    sessionmaker = _state["sessionmaker"]
    async with sessionmaker() as session:
        async with session.begin():
            case = await repository.update_status(session, case_id, req.status, req.note)
        if case is None:
            raise HTTPException(status_code=404, detail="case_not_found")
        return CaseOut.model_validate(case)


@app.post("/api/v1/cases/{case_id}/assign", response_model=CaseOut, tags=["cases"])
async def assign(case_id: str, req: AssignRequest, _user=Depends(require_senior)) -> CaseOut:
    sessionmaker = _state["sessionmaker"]
    async with sessionmaker() as session:
        async with session.begin():
            case = await repository.assign_case(session, case_id, req.assignee)
        if case is None:
            raise HTTPException(status_code=404, detail="case_not_found")
        return CaseOut.model_validate(case)


@app.post("/api/v1/cases/{case_id}/feedback", response_model=FeedbackOut, tags=["feedback"])
async def submit_feedback(case_id: str, req: FeedbackRequest, _user=Depends(require_analyst)) -> FeedbackOut:
    sessionmaker = _state["sessionmaker"]
    async with sessionmaker() as session:
        async with session.begin():
            feedback = await repository.record_feedback(session, case_id, req)
        if feedback is None:
            raise HTTPException(status_code=404, detail="case_not_found")
        return FeedbackOut.model_validate(feedback)


@app.get("/api/v1/cases/{case_id}/timeline", tags=["cases"])
async def timeline(case_id: str, _user=Depends(require_analyst)) -> list[dict]:
    sessionmaker = _state["sessionmaker"]
    async with sessionmaker() as session:
        return await repository.get_timeline(session, case_id)


@app.get("/api/v1/internal/cases/{case_id}/alerts", tags=["internal"])
async def internal_case_alerts(case_id: str) -> list[dict]:
    """Used by llm_triage's evidence-retrieval tool to fetch full alert payloads."""

    sessionmaker = _state["sessionmaker"]
    async with sessionmaker() as session:
        case = await repository.get_case(session, case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="case_not_found")
        records = await repository.get_alerts_for_case(session, case)
        return [r.payload for r in records]


@app.post("/api/v1/internal/cases/from-alert", response_model=CaseOut, tags=["internal"])
async def upsert_from_alert(alert: dict) -> CaseOut:
    """Internal, unauthenticated endpoint used by the detection consumer path
    and the sync-mode demo orchestrator to land an Alert into a case."""

    sessionmaker = _state["sessionmaker"]
    async with sessionmaker() as session:
        async with session.begin():
            case = await repository.upsert_case_from_alert(session, alert)
        return CaseOut.model_validate(case)


@app.get("/api/v1/stats", tags=["ops"])
async def stats() -> dict:
    consumer: AegisConsumer | None = _state.get("consumer")
    return {"consumer_lag": consumer.lag() if consumer else None}
