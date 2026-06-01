"""Case CRUD, search, timeline, and auto-case-creation-from-alerts logic."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_common.utils.helpers import utcnow

from case_core.models import AlertRecordORM, CaseFeedbackORM, CaseORM
from case_core.schemas import CaseSearchParams, CreateCaseRequest, FeedbackRequest

VALID_STATUSES = {"new", "triaging", "investigating", "contained", "resolved", "false_positive"}
SEVERITY_ORDER = {"informational": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


def _timeline_entry(kind: str, summary: str, **extra: Any) -> dict:
    return {"timestamp": utcnow().isoformat(), "kind": kind, "summary": summary, **extra}


async def create_case(session: AsyncSession, req: CreateCaseRequest) -> CaseORM:
    now = utcnow()
    case = CaseORM(
        case_id=str(uuid.uuid4()),
        tenant_id=req.tenant_id,
        title=req.title,
        status="new",
        severity=req.severity,
        risk_score=0.0,
        alert_ids=req.alert_ids,
        entity_ids=req.entity_ids,
        technique_ids=req.technique_ids,
        timeline=[_timeline_entry("case_created", f"Case created: {req.title}")],
        tags=req.tags,
        created_at=now,
        updated_at=now,
    )
    session.add(case)
    await session.flush()
    return case


async def get_case(session: AsyncSession, case_id: str) -> CaseORM | None:
    return await session.get(CaseORM, case_id)


async def get_case_by_cluster(session: AsyncSession, cluster_id: str) -> CaseORM | None:
    result = await session.execute(select(CaseORM).where(CaseORM.cluster_id == cluster_id))
    return result.scalar_one_or_none()


async def search_cases(session: AsyncSession, params: CaseSearchParams) -> list[CaseORM]:
    stmt = select(CaseORM)
    if params.tenant_id:
        stmt = stmt.where(CaseORM.tenant_id == params.tenant_id)
    if params.status:
        stmt = stmt.where(CaseORM.status == params.status)
    if params.severity:
        stmt = stmt.where(CaseORM.severity == params.severity)
    if params.assignee:
        stmt = stmt.where(CaseORM.assignee == params.assignee)
    if params.text:
        like = f"%{params.text}%"
        stmt = stmt.where(or_(CaseORM.title.ilike(like), CaseORM.attack_story.ilike(like)))
    stmt = stmt.order_by(CaseORM.updated_at.desc()).offset(params.offset).limit(params.limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_status(session: AsyncSession, case_id: str, status: str, note: str | None) -> CaseORM | None:
    case = await session.get(CaseORM, case_id)
    if case is None:
        return None
    case.status = status
    case.updated_at = utcnow()
    case.timeline = [*case.timeline, _timeline_entry("status_change", note or f"Status changed to {status}", status=status)]
    await session.flush()
    return case


async def assign_case(session: AsyncSession, case_id: str, assignee: str) -> CaseORM | None:
    case = await session.get(CaseORM, case_id)
    if case is None:
        return None
    case.assignee = assignee
    case.updated_at = utcnow()
    case.timeline = [*case.timeline, _timeline_entry("assignment", f"Assigned to {assignee}")]
    await session.flush()
    return case


async def record_feedback(session: AsyncSession, case_id: str, req: FeedbackRequest) -> CaseFeedbackORM | None:
    case = await session.get(CaseORM, case_id)
    if case is None:
        return None
    feedback = CaseFeedbackORM(
        feedback_id=str(uuid.uuid4()),
        case_id=case_id,
        analyst=req.analyst,
        verdict=req.verdict,
        comment=req.comment,
        created_at=utcnow(),
    )
    session.add(feedback)
    case.timeline = [
        *case.timeline,
        _timeline_entry("analyst_feedback", f"{req.analyst} marked as {req.verdict}", verdict=req.verdict),
    ]
    if req.verdict == "false_positive":
        case.status = "false_positive"
    case.updated_at = utcnow()
    await session.flush()
    return feedback


async def upsert_case_from_alert(session: AsyncSession, alert: dict[str, Any]) -> CaseORM:
    """Auto case creation/merge from an incoming Alert (cluster_id keyed)."""

    cluster_id = alert.get("cluster_id")
    now = utcnow()

    landed = await session.get(AlertRecordORM, alert["alert_id"])
    if landed is None:
        landed = AlertRecordORM(
            alert_id=alert["alert_id"],
            tenant_id=alert.get("tenant_id", "default"),
            cluster_id=cluster_id,
            title=alert.get("title", "Untitled alert"),
            severity=alert.get("severity", "medium"),
            calibrated_score=alert.get("risk", {}).get("calibrated_score", 0.0),
            payload=alert,
            created_at=now,
            updated_at=now,
        )
        session.add(landed)
    else:
        landed.severity = alert.get("severity", landed.severity)
        landed.calibrated_score = alert.get("risk", {}).get("calibrated_score", landed.calibrated_score)
        landed.payload = alert
        landed.updated_at = now

    case = await get_case_by_cluster(session, cluster_id) if cluster_id else None

    if case is None:
        case = CaseORM(
            case_id=str(uuid.uuid4()),
            tenant_id=alert.get("tenant_id", "default"),
            title=f"Auto-case: {alert.get('title', 'Untitled alert')}",
            status="new",
            severity=alert.get("severity", "medium"),
            risk_score=alert.get("risk", {}).get("calibrated_score", 0.0),
            alert_ids=[alert["alert_id"]],
            entity_ids=alert.get("entity_ids", []),
            technique_ids=alert.get("technique_ids", []),
            timeline=[
                _timeline_entry(
                    "auto_case_created",
                    f"Case auto-created from alert cluster {cluster_id}",
                    alert_id=alert["alert_id"],
                )
            ],
            tags=alert.get("tags", []),
            cluster_id=cluster_id,
            created_at=now,
            updated_at=now,
        )
        session.add(case)
    else:
        case.alert_ids = sorted(set(case.alert_ids) | {alert["alert_id"]})
        case.entity_ids = sorted(set(case.entity_ids) | set(alert.get("entity_ids", [])))
        case.technique_ids = sorted(set(case.technique_ids) | set(alert.get("technique_ids", [])))
        new_score = alert.get("risk", {}).get("calibrated_score", 0.0)
        if new_score > case.risk_score:
            case.risk_score = new_score
        if SEVERITY_ORDER.get(alert.get("severity", "medium"), 2) > SEVERITY_ORDER.get(case.severity, 2):
            case.severity = alert.get("severity", case.severity)
        case.timeline = [
            *case.timeline,
            _timeline_entry(
                "alert_merged", f"Alert {alert['alert_id']} merged into case", alert_id=alert["alert_id"]
            ),
        ]
        case.updated_at = now

    await session.flush()
    landed.case_id = case.case_id
    await session.flush()
    return case


async def get_alert_record(session: AsyncSession, alert_id: str) -> AlertRecordORM | None:
    return await session.get(AlertRecordORM, alert_id)


async def get_alerts_for_case(session: AsyncSession, case: CaseORM) -> list[AlertRecordORM]:
    if not case.alert_ids:
        return []
    result = await session.execute(select(AlertRecordORM).where(AlertRecordORM.alert_id.in_(case.alert_ids)))
    return list(result.scalars().all())


async def get_timeline(session: AsyncSession, case_id: str) -> list[dict]:
    case = await session.get(CaseORM, case_id)
    if case is None:
        return []
    return sorted(case.timeline, key=lambda e: e.get("timestamp", ""))
