"""End-to-end grounded triage pipeline: retrieve -> sanitize -> prompt -> validate."""

from __future__ import annotations

import logging

from aegis_common.schema.events import EvidenceItem, TriageReport
from aegis_common.utils.helpers import utcnow

from triage_core import llm_client
from triage_core.evidence import build_evidence
from triage_core.tools import EvidenceTools
from triage_core.validation import validate_and_ground

logger = logging.getLogger("aegis.llm_triage.pipeline")

MAX_ENTITIES_EXPANDED = 6


async def gather_evidence(
    *, case_id: str, tools: EvidenceTools, max_evidence_items: int
) -> tuple[list[EvidenceItem], list[dict], int]:
    """Runs the retrieval half of the triage pipeline (case/alerts/events/
    graph neighborhood -> ranked, capped EvidenceItem list) without invoking
    the LLM. Used both by ``generate_triage_report`` and by the
    evidence-only inspection endpoint the analyst UI uses to show "what did
    the model actually see" independent of any generated report."""

    case = await tools.get_case(case_id)
    alerts = await tools.get_alerts(case_id)

    entity_ids = (case or {}).get("entity_ids", [])[:MAX_ENTITIES_EXPANDED]
    events_by_entity: dict[str, list[dict]] = {}
    neighborhoods_by_entity: dict[str, dict] = {}
    for entity_id in entity_ids:
        events_by_entity[entity_id] = await tools.get_events(entity_id)
        neighborhoods_by_entity[entity_id] = await tools.get_graph_neighborhood(entity_id)

    evidence, injection_flags = build_evidence(
        case=case,
        alerts=alerts,
        events_by_entity=events_by_entity,
        neighborhoods_by_entity=neighborhoods_by_entity,
        max_items=max_evidence_items,
    )
    if injection_flags:
        logger.warning("prompt_injection_markers_neutralized case_id=%s count=%d", case_id, injection_flags)
    return evidence, alerts, injection_flags


async def generate_triage_report(
    *,
    case_id: str,
    tools: EvidenceTools,
    llm_enabled: bool,
    api_key: str | None,
    base_url: str | None,
    model: str,
    max_evidence_items: int,
) -> TriageReport:
    evidence, alerts, _ = await gather_evidence(
        case_id=case_id, tools=tools, max_evidence_items=max_evidence_items
    )

    raw, used_mock = await llm_client.generate(
        case_id=case_id,
        evidence=evidence,
        llm_enabled=llm_enabled,
        api_key=api_key,
        base_url=base_url,
        model=model,
    )
    validated = validate_and_ground(raw, evidence)

    return TriageReport(
        case_id=case_id,
        alert_ids=[a.get("alert_id") for a in alerts if a.get("alert_id")],
        summary=validated.get("summary", ""),
        likely_objective=validated.get("likely_objective", "unknown"),
        attack_mapping=validated.get("attack_mapping", []),
        investigation_queries=validated.get("investigation_queries", []),
        containment_recommendation=validated.get("containment_recommendation", ""),
        confidence_explanation=validated.get("confidence_explanation", ""),
        groundedness_score=validated.get("groundedness_score", 0.0),
        evidence_cited=validated.get("evidence_cited", []),
        unsupported_claims=validated.get("unsupported_claims", []),
        model_id="mock-template-v1" if used_mock else model,
        created_at=utcnow(),
    )
