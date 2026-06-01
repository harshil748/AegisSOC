"""Builds a bounded, sanitized EvidenceItem list from retrieved case/alert/event/graph data.

Evidence scoping matters more than evidence volume: excessive context can
mislead the model, so retrieval results are deduplicated, ranked, and
capped at ``max_items`` before ever reaching the prompt.
"""

from __future__ import annotations

from typing import Any

from aegis_common.schema.events import EvidenceItem
from aegis_common.utils.helpers import stable_hash, utcnow

from triage_core.security import sanitize_text


def _mk_item(kind: str, summary: str, source: str | None, payload: dict, timestamp=None) -> tuple[EvidenceItem, bool]:
    clean_summary, flagged = sanitize_text(summary)
    item = EvidenceItem(
        evidence_id=f"{kind}-{stable_hash(clean_summary + str(payload)[:200])}",
        kind=kind,
        summary=clean_summary,
        timestamp=timestamp,
        source=source,
        payload=payload,
    )
    return item, flagged


def build_evidence(
    *,
    case: dict[str, Any] | None,
    alerts: list[dict[str, Any]],
    events_by_entity: dict[str, list[dict[str, Any]]],
    neighborhoods_by_entity: dict[str, dict[str, Any]],
    max_items: int,
) -> tuple[list[EvidenceItem], int]:
    items: list[EvidenceItem] = []
    injection_flags = 0

    if case:
        item, flagged = _mk_item(
            "case",
            f"Case '{case.get('title')}' status={case.get('status')} severity={case.get('severity')} "
            f"risk_score={case.get('risk_score')} techniques={case.get('technique_ids')}",
            source="case_management",
            payload={"case_id": case.get("case_id"), "technique_ids": case.get("technique_ids", [])},
        )
        items.append(item)
        injection_flags += int(flagged)

    for alert in alerts:
        risk = alert.get("risk", {})
        item, flagged = _mk_item(
            "alert",
            f"Alert '{alert.get('title')}' severity={alert.get('severity')} "
            f"calibrated_score={risk.get('calibrated_score')} description={alert.get('description', '')}",
            source="detection",
            payload={
                "alert_id": alert.get("alert_id"),
                "risk": risk,
                "technique_ids": alert.get("technique_ids", []),
            },
        )
        items.append(item)
        injection_flags += int(flagged)

    for entity_id, events in events_by_entity.items():
        for evt in events[-10:]:
            item, flagged = _mk_item(
                "event",
                f"[{entity_id}] {evt.get('event_type', 'observation')} at {evt.get('timestamp')} "
                f"source={evt.get('source')} severity={evt.get('severity')}",
                source=evt.get("source"),
                payload=evt,
                timestamp=evt.get("timestamp"),
            )
            items.append(item)
            injection_flags += int(flagged)

    for entity_id, neighborhood in neighborhoods_by_entity.items():
        edge_summary = ", ".join(
            f"{e.get('edge_type')}->{e.get('dst_id', '')[-8:]}" for e in neighborhood.get("edges", [])[:8]
        )
        if edge_summary:
            item, flagged = _mk_item(
                "node",
                f"Graph neighborhood of {entity_id}: {edge_summary}",
                source="graph_builder",
                payload={"entity_id": entity_id, "edge_count": len(neighborhood.get("edges", []))},
            )
            items.append(item)
            injection_flags += int(flagged)

    # Prioritize case/alert evidence, then most-recent events/graph context.
    kind_priority = {"case": 0, "alert": 1, "event": 2, "node": 3}
    items.sort(key=lambda i: kind_priority.get(i.kind, 9))
    return items[:max_items], injection_flags
