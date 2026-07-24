"""BFF read/composition logic backing the frontend's ``/api/*`` contract
(``frontend/src/types/domain.ts``).

Every function here is dual-mode:

* **sync mode** (``AEGIS_SYNC_MODE=true``, the "all-in-one" demo path) --
  reads come straight from the same in-process singletons/SQLite stores the
  gateway's own demo pipeline writes into (``gateway_core.inprocess``), so
  data produced by ``POST /api/demo/run-scenario`` is immediately visible
  with no network hop and no risk of talking to a different process's
  in-memory state.
* **async mode** (full docker-compose stack, Kafka-driven) -- reads proxy
  over HTTP to the real standalone services and reshape their responses
  into the frontend's expected shape.
"""

from __future__ import annotations

import time
from typing import Any

from aegis_common.auth.jwt import TokenPayload
from aegis_common.auth.rbac import Role, role_satisfies
from aegis_common.config import Settings, is_sync_mode

from gateway_core import metrics_state
from gateway_core.inprocess import ensure_db, get_modules
from gateway_core.proxy import fetch_json, post_json

settings = Settings()


def _lift_display_name(node: dict[str, Any]) -> dict[str, Any]:
    props = node.get("properties") if isinstance(node.get("properties"), dict) else {}
    display = node.get("display_name") or props.get("display_name") or props.get("name") or node.get("node_id")
    return {**node, "display_name": display}


def _edge_key(edge: dict[str, Any]) -> str:
    if edge.get("edge_id"):
        return str(edge["edge_id"])
    return f"{edge.get('src_id')}|{edge.get('edge_type')}|{edge.get('dst_id')}"


async def _alert_id_to_case_id(case_management_url: str) -> dict[str, str]:
    """Map alert_id -> case_id from case management (source of truth for linkage)."""
    mapping: dict[str, str] = {}
    cases_result = await list_cases(case_management_url, limit=10_000)
    for case in cases_result.get("items", []):
        case_id = case.get("case_id")
        if not case_id:
            continue
        for alert_id in case.get("alert_ids") or []:
            mapping[str(alert_id)] = str(case_id)
    return mapping


# --------------------------------------------------------------------------- alerts


async def list_alerts(
    detection_url: str,
    case_management_url: str | None = None,
    *,
    severity: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    if is_sync_mode():
        mods = get_modules()
        state = mods.get_default_state()
        alerts = [a.model_dump(mode="json") for a in state.cluster_store.all_alerts()]
    else:
        alerts = await fetch_json(detection_url, "/api/v1/alerts") or []

    if case_management_url:
        try:
            alert_cases = await _alert_id_to_case_id(case_management_url)
            for alert in alerts:
                if not alert.get("case_id"):
                    linked = alert_cases.get(str(alert.get("alert_id", "")))
                    if linked:
                        alert["case_id"] = linked
        except Exception:
            pass

    if severity:
        alerts = [a for a in alerts if a.get("severity") == severity]
    if status:
        alerts = [a for a in alerts if a.get("status") == status]
    if q:
        ql = q.lower()
        alerts = [
            a for a in alerts
            if ql in (a.get("title", "") + " " + a.get("description", "")).lower()
        ]
    alerts.sort(key=lambda a: a.get("updated_at", ""), reverse=True)
    total = len(alerts)
    return {"items": alerts[offset : offset + limit], "total": total}


async def get_alert(
    detection_url: str, alert_id: str, case_management_url: str | None = None
) -> dict[str, Any] | None:
    result = await list_alerts(detection_url, case_management_url, limit=10_000)
    for alert in result["items"]:
        if alert.get("alert_id") == alert_id:
            return alert
    return None


# --------------------------------------------------------------------------- cases


async def list_cases(
    case_management_url: str,
    *,
    status: str | None = None,
    severity: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    if is_sync_mode():
        mods = get_modules()
        await ensure_db("case_management", mods.case_init_db, settings.postgres_dsn)
        sessionmaker = mods.case_sessionmaker_for(settings.postgres_dsn)
        params = mods.CaseSearchParams(
            status=status, severity=severity, text=q, limit=limit, offset=offset
        )
        async with sessionmaker() as session:
            cases = await mods.case_repository.search_cases(session, params)
            items = [mods.CaseOut.model_validate(c).model_dump(mode="json") for c in cases]
        return {"items": items, "total": len(items)}

    items = (
        await fetch_json(
            case_management_url,
            "/api/v1/cases",
            params={
                "status": status,
                "severity": severity,
                "text": q,
                "limit": limit,
                "offset": offset,
            },
        )
        or []
    )
    return {"items": items, "total": len(items)}


async def get_case(case_management_url: str, case_id: str) -> dict[str, Any] | None:
    if is_sync_mode():
        mods = get_modules()
        await ensure_db("case_management", mods.case_init_db, settings.postgres_dsn)
        sessionmaker = mods.case_sessionmaker_for(settings.postgres_dsn)
        async with sessionmaker() as session:
            case = await mods.case_repository.get_case(session, case_id)
            if case is None:
                return None
            return mods.CaseOut.model_validate(case).model_dump(mode="json")
    return await fetch_json(case_management_url, f"/api/v1/cases/{case_id}")


async def _case_alert_payloads(case_management_url: str, case: dict[str, Any]) -> list[dict[str, Any]]:
    if is_sync_mode():
        mods = get_modules()
        sessionmaker = mods.case_sessionmaker_for(settings.postgres_dsn)
        async with sessionmaker() as session:
            case_orm = await mods.case_repository.get_case(session, case["case_id"])
            if case_orm is None:
                return []
            records = await mods.case_repository.get_alerts_for_case(session, case_orm)
            return [r.payload for r in records]
    return (
        await fetch_json(case_management_url, f"/api/v1/internal/cases/{case['case_id']}/alerts")
        or []
    )


async def get_case_graph(
    graph_builder_url: str, case_management_url: str, case_id: str, *, depth: int = 1
) -> dict[str, Any] | None:
    case = await get_case(case_management_url, case_id)
    if case is None:
        return None

    entity_ids = (case.get("entity_ids") or [])[:10]
    nodes_by_id: dict[str, dict[str, Any]] = {}
    edges_by_id: dict[str, dict[str, Any]] = {}

    for entity_id in entity_ids:
        if is_sync_mode():
            mods = get_modules()
            state = mods.get_default_state()
            graph_store = await state.ensure_graph_store(settings)
            neighborhood = await graph_store.neighborhood(entity_id, depth=depth)
        else:
            neighborhood = await fetch_json(
                graph_builder_url, f"/api/v1/graph/neighborhood/{entity_id}", params={"depth": depth}
            )
        if not neighborhood:
            continue
        for node in neighborhood.get("nodes", []):
            node_id = node.get("node_id")
            if not node_id:
                continue
            nodes_by_id[node_id] = _lift_display_name(node)
        for edge in neighborhood.get("edges", []):
            edges_by_id[_edge_key(edge)] = edge

    return {"nodes": list(nodes_by_id.values()), "edges": list(edges_by_id.values())}


def _timeline_entry_to_event(case_id: str, idx: int, entry: dict[str, Any]) -> dict[str, Any]:
    kind = entry.get("kind", "event")
    return {
        "event_id": f"{case_id}-tl-{idx}",
        "timestamp": entry.get("timestamp"),
        "title": kind.replace("_", " ").title(),
        "description": entry.get("summary", ""),
        "category": kind,
        "severity": entry.get("severity"),
        "source": entry.get("source"),
        "entity_refs": entry.get("entity_refs"),
        "technique_ids": entry.get("technique_ids"),
    }


async def get_case_timeline(case_management_url: str, case_id: str) -> dict[str, Any] | None:
    if is_sync_mode():
        mods = get_modules()
        sessionmaker = mods.case_sessionmaker_for(settings.postgres_dsn)
        async with sessionmaker() as session:
            case = await mods.case_repository.get_case(session, case_id)
            if case is None:
                return None
            entries = await mods.case_repository.get_timeline(session, case_id)
    else:
        entries = await fetch_json(case_management_url, f"/api/v1/cases/{case_id}/timeline")
        if entries is None:
            return None
    items = [_timeline_entry_to_event(case_id, i, e) for i, e in enumerate(entries)]
    return {"items": items}


async def get_case_triage(
    llm_triage_url: str, case_management_url: str, graph_builder_url: str, case_id: str
) -> dict[str, Any] | None:
    if is_sync_mode():
        mods = get_modules()
        case = await get_case(case_management_url, case_id)
        if case is None:
            return None
        alerts = await _case_alert_payloads(case_management_url, case)
        state = mods.get_default_state()
        graph_store = await state.ensure_graph_store(settings)
        tools = mods.InProcessEvidenceTools(case=case, alerts=alerts, graph_store=graph_store)
        started = time.monotonic()
        report = await mods.generate_triage_report(
            case_id=case_id,
            tools=tools,
            llm_enabled=settings.llm_enabled,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.llm_model,
            max_evidence_items=settings.llm_max_evidence_items,
        )
        metrics_state.record_triage_report(
            latency_ms=(time.monotonic() - started) * 1000,
            groundedness_score=report.groundedness_score,
        )
        return report.model_dump(mode="json")

    status, body = await post_json(llm_triage_url, f"/api/v1/triage/{case_id}")
    return body if status < 400 else None


async def get_case_evidence(
    llm_triage_url: str, case_management_url: str, case_id: str
) -> dict[str, Any] | None:
    if is_sync_mode():
        mods = get_modules()
        case = await get_case(case_management_url, case_id)
        if case is None:
            return None
        alerts = await _case_alert_payloads(case_management_url, case)
        state = mods.get_default_state()
        graph_store = await state.ensure_graph_store(settings)
        tools = mods.InProcessEvidenceTools(case=case, alerts=alerts, graph_store=graph_store)
        items, _alerts, _flags = await mods.gather_evidence(
            case_id=case_id, tools=tools, max_evidence_items=settings.llm_max_evidence_items
        )
        return {"items": [i.model_dump(mode="json") for i in items]}

    return await fetch_json(llm_triage_url, f"/api/v1/evidence/{case_id}")


# --------------------------------------------------------------------------- actions / approvals


async def list_actions(
    response_policy_url: str, *, case_id: str | None = None, status: str | None = None
) -> list[dict[str, Any]]:
    if is_sync_mode():
        mods = get_modules()
        return [
            a.model_dump(mode="json")
            for a in mods.policy_store.list_all(case_id=case_id, status=status)
        ]
    return (
        await fetch_json(
            response_policy_url, "/api/v1/recommendations", params={"case_id": case_id, "status": status}
        )
        or []
    )


async def submit_approval(
    approval_url: str,
    response_policy_url: str,
    audit_url: str,
    *,
    action_id: str,
    case_id: str,
    decision: str,
    rationale: str,
    dry_run: bool,
    decided_by: str,
    decided_by_role: str,
) -> tuple[int, dict[str, Any] | None]:
    """Composes response_policy's recommendation lookup with approval's
    create+decide workflow, since the frontend submits a decision directly
    against an ``action_id`` without an intermediate "create approval
    request" step.

    Mirrors the standalone approval service's own escalation rule: any
    analyst may decide a non-disruptive action, but approving a disruptive
    one requires senior_analyst or admin (see ``services/approval/app/main.py``).
    """

    if is_sync_mode():
        mods = get_modules()
        action = mods.policy_store.get(action_id)
        if action is None:
            return 404, {"detail": "recommendation_not_found"}
        if (
            decision == "approved"
            and action.disruptive
            and not role_satisfies(decided_by_role, Role.SENIOR_ANALYST.value)
        ):
            return 403, {"detail": "requires_role>=senior_analyst to approve a disruptive action"}

        await ensure_db("approval", mods.approval_init_db, settings.postgres_dsn)
        sessionmaker = mods.approval_sessionmaker_for(settings.postgres_dsn)

        async def _audit_callback(event: dict[str, Any]) -> None:
            audit_mods = get_modules()
            await ensure_db("audit", audit_mods.audit_init_db, settings.postgres_dsn)
            audit_sessionmaker = audit_mods.audit_sessionmaker_for(settings.postgres_dsn)
            async with audit_sessionmaker() as audit_session:
                async with audit_session.begin():
                    await audit_mods.audit_repository.append_event(
                        audit_session, audit_mods.AuditEventIn(**event)
                    )

        audit_sink = mods.InProcessAuditSink(_audit_callback)

        async with sessionmaker() as session:
            async with session.begin():
                existing = None
                approvals = await mods.approval_repository.list_approvals(session, case_id=case_id, limit=200)
                existing = next((a for a in approvals if a.action_id == action_id), None)
                if existing is None:
                    create_req = mods.CreateApprovalRequest(
                        action_id=action_id,
                        case_id=case_id,
                        action_class=action.action_class.value,
                        title=action.title,
                        description=action.description,
                        disruptive=action.disruptive,
                        dry_run=dry_run,
                        requested_by=decided_by,
                        payload={"parameters": action.parameters},
                    )
                    existing = await mods.approval_repository.create_approval(session, create_req, audit_sink)
                if existing.status != "pending":
                    approval_out = mods.ApprovalOut.model_validate(existing).model_dump(mode="json")
                    return 200, _to_approval_decision(approval_out)
                decided = await mods.approval_repository.decide_approval(
                    session, existing.approval_id, decided_by, decision, rationale, audit_sink
                )
            approval_out = mods.ApprovalOut.model_validate(decided).model_dump(mode="json")
        mods.policy_store.mark_status(action_id, decision)
        return 200, _to_approval_decision(approval_out)

    action = await fetch_json(response_policy_url, f"/api/v1/recommendations/{action_id}")
    if action is None:
        return 404, {"detail": "recommendation_not_found"}
    status, created = await post_json(
        approval_url,
        "/api/v1/approvals",
        json_body={
            "action_id": action_id,
            "case_id": case_id,
            "action_class": action.get("action_class"),
            "title": action.get("title", ""),
            "description": action.get("description", ""),
            "disruptive": action.get("disruptive", True),
            "dry_run": dry_run,
            "requested_by": decided_by,
            "payload": {"parameters": action.get("parameters", {})},
        },
    )
    approval_id = (created or {}).get("approval_id") if status < 400 else None
    if approval_id is None:
        return status, created
    status, decided = await post_json(
        approval_url,
        f"/api/v1/approvals/{approval_id}/decide",
        json_body={"decision": decision, "rationale": rationale},
    )
    if decided:
        return status, _to_approval_decision(decided)
    return status, decided


def _to_approval_decision(approval_out: dict[str, Any]) -> dict[str, Any]:
    return {
        "approval_id": approval_out["approval_id"],
        "action_id": approval_out["action_id"],
        "case_id": approval_out["case_id"],
        "decided_by": approval_out.get("decided_by"),
        "decision": approval_out.get("decision"),
        "rationale": approval_out.get("rationale"),
        "decided_at": approval_out.get("decided_at"),
        "dry_run": approval_out.get("dry_run"),
    }


# --------------------------------------------------------------------------- audit


async def list_audit(
    audit_url: str,
    user: TokenPayload,
    *,
    q: str | None = None,
    actor: str | None = None,
    actor_type: str | None = None,
    resource_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    if is_sync_mode():
        mods = get_modules()
        await ensure_db("audit", mods.audit_init_db, settings.postgres_dsn)
        sessionmaker = mods.audit_sessionmaker_for(settings.postgres_dsn)
        async with sessionmaker() as session:
            records = await mods.audit_repository.query_events(
                session,
                actor=actor,
                actor_type=actor_type,
                resource_type=resource_type,
                limit=limit + offset,
            )
        items = [mods.AuditEventOut.model_validate(r).model_dump(mode="json") for r in records]
    else:
        items = (
            await fetch_json(
                audit_url,
                "/api/v1/audit",
                params={
                    "actor": actor,
                    "actor_type": actor_type,
                    "resource_type": resource_type,
                    "limit": limit + offset,
                },
            )
            or []
        )
    if q:
        ql = q.lower()
        items = [i for i in items if ql in str(i).lower()]
    total = len(items)
    return {"items": items[offset : offset + limit], "total": total}


# --------------------------------------------------------------------------- metrics


async def get_metrics_snapshot(
    ingestion_url: str,
    detection_url: str,
    case_management_url: str,
    response_policy_url: str,
    approval_url: str,
) -> dict[str, Any]:
    from datetime import datetime, timezone

    today = datetime.now(timezone.utc).date().isoformat()
    counters = metrics_state.snapshot()

    alerts_result = await list_alerts(detection_url, case_management_url, limit=10_000)
    alerts = alerts_result["items"]
    alerts_today = sum(1 for a in alerts if str(a.get("created_at", "")).startswith(today))
    open_alerts = sum(1 for a in alerts if a.get("status") == "open")

    cases_result = await list_cases(case_management_url, limit=10_000)
    cases = cases_result["items"]
    open_cases = sum(1 for c in cases if c.get("status") in {"new", "triaging"})
    investigating_cases = sum(1 for c in cases if c.get("status") == "investigating")
    resolved_today = sum(
        1 for c in cases if c.get("status") == "resolved" and str(c.get("updated_at", "")).startswith(today)
    )
    fp_count = sum(1 for c in cases if c.get("status") == "false_positive")
    fp_rate = (fp_count / len(cases)) if cases else 0.0

    actions = await list_actions(response_policy_url)
    pending_approvals = sum(1 for a in actions if a.get("status") == "pending")
    approved_today = sum(
        1 for a in actions if a.get("status") == "approved" and str(a.get("created_at", "")).startswith(today)
    )
    rejected_today = sum(
        1 for a in actions if a.get("status") == "rejected" and str(a.get("created_at", "")).startswith(today)
    )
    executed_today = sum(
        1 for a in actions if a.get("status") == "executed" and str(a.get("created_at", "")).startswith(today)
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ingestion": {
            "events_per_sec": 0.0,
            "events_today": counters["ingestion_events_total"],
            "queue_lag_ms": 0.0,
            "dlq_count": 0,
        },
        "detection": {
            "alerts_today": alerts_today,
            "open_alerts": open_alerts,
            "precision": 0.0,
            "recall": 0.0,
            "avg_time_to_triage_minutes": 0.0,
        },
        "cases": {
            "open": open_cases,
            "investigating": investigating_cases,
            "resolved_today": resolved_today,
            "false_positive_rate": round(fp_rate, 3),
        },
        "llm": {
            "avg_latency_ms": round(counters["llm_avg_latency_ms"], 1),
            "requests_today": counters["llm_requests_total"],
            "cost_today_usd": 0.0,
            "groundedness_avg": round(counters["llm_groundedness_avg"], 3),
        },
        "response": {
            "pending_approvals": pending_approvals,
            "approved_today": approved_today,
            "rejected_today": rejected_today,
            "executed_today": executed_today,
        },
    }
