"""In-process sync-mode demo pipeline.

Runs a full scenario through every stage of the AegisSOC pipeline --
``ingest -> normalize -> enrich -> graph -> detect -> case -> triage ->
recommend`` -- in a single process, by calling each service's core
business-logic package directly rather than going over HTTP/Kafka. This is
what makes the platform demoable with zero external infrastructure
(no Kafka, no Postgres, no Neo4j) when ``AEGIS_SYNC_MODE=true``: every shared
singleton (the in-memory graph store, the detection engine's rule/cluster
state) and every per-service SQLite-backed store is the *same* code path a
fully deployed docker-compose stack would use, just invoked in-process.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from aegis_common.config import Settings
from aegis_common.schema.events import resolve_telemetry_source
from aegis_common.utils.helpers import utcnow

from gateway_core import metrics_state
from gateway_core.inprocess import ensure_db, get_modules

logger = logging.getLogger("aegis.gateway.demo_pipeline")

settings = Settings()


class ScenarioNotFound(Exception):
    pass


def available_scenarios() -> list[dict[str, Any]]:
    return get_modules().list_scenarios()


async def run_scenario(scenario_id: str, tenant_id: str = "default") -> dict[str, Any]:
    """Execute the full pipeline for one demo scenario and return a rich,
    UI-ready summary of everything that happened at each stage."""

    mods = get_modules()
    await ensure_db("case_management", mods.case_init_db, settings.postgres_dsn)

    try:
        scenario = mods.load_scenario(scenario_id)
    except FileNotFoundError as exc:
        raise ScenarioNotFound(str(exc)) from exc

    started_at = time.monotonic()
    # Isolate each demo/scenario run so graph memory and alert clusters from a
    # prior phishing chain cannot inflate a benign false-positive score.
    from aegis_common.graphstore import reset_store_for_tests
    from detection_core.pipeline import new_detection_state

    reset_store_for_tests()
    detection_state = new_detection_state()
    graph_store = await detection_state.ensure_graph_store(settings)
    sessionmaker = mods.case_sessionmaker_for(settings.postgres_dsn)

    raw_events = sorted(scenario.get("events", []), key=lambda e: str(e.get("timestamp", "")))

    stage_errors: list[dict[str, Any]] = []
    canonical_events: list[dict[str, Any]] = []
    detection_hits: list[dict[str, Any]] = []
    alerts_by_id: dict[str, dict[str, Any]] = {}
    case_ids_touched: list[str] = []
    event_criticality: dict[str, float] = {}
    graph_updates_applied = {"nodes": 0, "edges": 0}

    for raw_event in raw_events:
        source_raw = raw_event.get("source")
        payload = raw_event.get("raw") or raw_event.get("payload") or {}
        try:
            envelope = mods.RawEnvelope(
                tenant_id=tenant_id,
                source=resolve_telemetry_source(source_raw),
                timestamp=raw_event.get("timestamp"),
                payload=payload,
            )
        except Exception as exc:
            stage_errors.append({"stage": "ingest", "source": source_raw, "reason": str(exc)})
            continue

        try:
            event = mods.normalize_raw_message(envelope.model_dump())
        except mods.NormalizationError as exc:
            stage_errors.append({"stage": "normalize", "source": source_raw, "reason": exc.reason})
            continue

        event = mods.enrich_event(event)
        event_criticality[event.event_id] = event.asset_criticality
        metrics_state.record_ingested_events(1)

        nodes, edges = mods.derive_graph_updates(event)
        observation = mods.observation_for(event)
        for node in nodes:
            await graph_store.upsert_node(node, observation=observation)
            graph_updates_applied["nodes"] += 1
        for edge in edges:
            await graph_store.upsert_edge(edge, observation=observation)
            graph_updates_applied["edges"] += 1

        hits, alert = await mods.process_event(event, detection_state, settings)
        for hit in hits:
            detection_hits.append(hit.model_dump(mode="json"))

        canonical_events.append(
            {
                "event_id": event.event_id,
                "timestamp": event.timestamp.isoformat(),
                "source": event.source.value,
                "event_type": event.event_type,
                "severity": event.severity.value,
                "host": event.host,
                "user": event.user,
                "technique_ids": event.technique_ids,
                "intel_matches": event.intel_matches,
                "asset_criticality": event.asset_criticality,
                "entity_count": len(event.entities),
                "detection_hit_count": len(hits),
            }
        )

        if alert is not None:
            alert_dict = alert.model_dump(mode="json")
            alerts_by_id[alert.alert_id] = alert_dict
            async with sessionmaker() as session:
                async with session.begin():
                    case = await mods.case_repository.upsert_case_from_alert(session, alert_dict)
                case_id = case.case_id
            if case_id not in case_ids_touched:
                case_ids_touched.append(case_id)

    cases_out: list[dict[str, Any]] = []
    triage_reports: dict[str, Any] = {}
    recommendations: dict[str, Any] = {}

    for case_id in case_ids_touched:
        async with sessionmaker() as session:
            case_orm = await mods.case_repository.get_case(session, case_id)
            if case_orm is None:
                continue
            case_out = mods.CaseOut.model_validate(case_orm).model_dump(mode="json")
            alert_records = await mods.case_repository.get_alerts_for_case(session, case_orm)
            alert_payloads = [r.payload for r in alert_records]
        cases_out.append(case_out)

        tools = mods.InProcessEvidenceTools(case=case_out, alerts=alert_payloads, graph_store=graph_store)
        triage_started = time.monotonic()
        try:
            report = await mods.generate_triage_report(
                case_id=case_id,
                tools=tools,
                llm_enabled=settings.llm_enabled,
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                model=settings.llm_model,
                max_evidence_items=settings.llm_max_evidence_items,
            )
        except Exception:
            logger.exception("triage_generation_failed case_id=%s", case_id)
            continue
        metrics_state.record_triage_report(
            latency_ms=(time.monotonic() - triage_started) * 1000,
            groundedness_score=report.groundedness_score,
        )
        triage_reports[case_id] = report.model_dump(mode="json")

        criticality = max(
            (event_criticality.get(eid, 0.5) for a in alert_payloads for eid in a.get("event_ids", [])),
            default=case_out.get("risk_score", 0.5),
        )
        try:
            recommendation = mods.recommend_action(
                case_id=case_id,
                risk_score=case_out.get("risk_score", 0.5),
                asset_criticality=criticality,
                likely_objective=report.likely_objective,
            )
        except Exception:
            logger.exception("recommendation_failed case_id=%s", case_id)
            continue
        recommendations[case_id] = recommendation.model_dump(mode="json")

    graph_stats = await graph_store.stats()
    elapsed_ms = round((time.monotonic() - started_at) * 1000, 1)

    top_case_id = cases_out[0]["case_id"] if cases_out else None
    top_severity = max((c.get("severity") for c in cases_out), default=None, key=lambda s: _SEVERITY_ORDER.get(s, 0))

    return {
        "status": "completed",
        "message": (
            f"Replayed {len(canonical_events)}/{len(raw_events)} events -> "
            f"{len(alerts_by_id)} alert(s), {len(cases_out)} case(s)"
            + (f", top severity={top_severity}" if top_severity else "")
        ),
        "scenario_id": scenario.get("scenario_id", scenario_id),
        "case_id": top_case_id,
        "run_id": f"{scenario.get('scenario_id', scenario_id)}-{int(started_at * 1000) % 1_000_000}",
        "title": scenario.get("title", scenario_id),
        "description": scenario.get("description"),
        "expected_outcome": scenario.get("expected_outcome"),
        "tenant_id": tenant_id,
        "run_at": utcnow().isoformat(),
        "elapsed_ms": elapsed_ms,
        "pipeline_stages": ["ingest", "normalize", "enrich", "graph", "detect", "case", "triage", "recommend"],
        "events_total": len(raw_events),
        "events_processed": len(canonical_events),
        "stage_errors": stage_errors,
        "canonical_events": canonical_events,
        "detection_hits": detection_hits,
        "alerts": list(alerts_by_id.values()),
        "cases": cases_out,
        "triage_reports": triage_reports,
        "recommendations": recommendations,
        "graph_updates_applied": graph_updates_applied,
        "graph_stats": graph_stats,
    }


_SEVERITY_ORDER = {"informational": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
