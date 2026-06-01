"""Detection pipeline orchestration: rules -> correlation -> graph/ML -> ensemble -> alert."""

from __future__ import annotations

import logging

from aegis_common.config import Settings
from aegis_common.graphstore import get_store
from aegis_common.graphstore.base import GraphStore
from aegis_common.schema.events import CanonicalEvent, DetectionHit, Severity

from detection_core import ensemble, heuristics, sigma
from detection_core.correlation import CorrelationEngine
from detection_core.dedup import AlertClusterStore
from detection_core.graph_features import compute_graph_features, graph_score_from_features
from detection_core.ml_scorer import score_from_features
from detection_core.temporal import TemporalFeatureTracker

logger = logging.getLogger("aegis.detection.pipeline")

MIN_ALERT_SCORE = 0.3


class DetectionState:
    """Holds all mutable pipeline state; one instance per process (or per demo run)."""

    def __init__(self) -> None:
        self.rules = sigma.load_rules()
        self.correlation_engine = CorrelationEngine()
        self.temporal_tracker = TemporalFeatureTracker()
        self.cluster_store = AlertClusterStore()
        self.graph_store: GraphStore | None = None

    async def ensure_graph_store(self, settings: Settings) -> GraphStore:
        if self.graph_store is None:
            self.graph_store = await get_store(
                settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password
            )
        return self.graph_store

    def reload_rules(self) -> int:
        self.rules = sigma.load_rules()
        return len(self.rules)


_default_state: DetectionState | None = None


def get_default_state() -> DetectionState:
    global _default_state
    if _default_state is None:
        _default_state = DetectionState()
    return _default_state


def new_detection_state() -> DetectionState:
    """Fresh pipeline state for isolated demo/scenario runs."""
    return DetectionState()


def reset_default_state() -> None:
    global _default_state
    _default_state = None


async def process_event(
    event: CanonicalEvent, state: DetectionState, settings: Settings
) -> tuple[list[DetectionHit], object | None]:
    """Run the full detection pipeline for one enriched event.

    Returns (detection_hits, alert_or_none).
    """

    hits: list[DetectionHit] = []
    matched_severities: list[Severity] = []

    for rule in state.rules:
        try:
            gate_matched, evidence = sigma.match_single(rule, event)
        except Exception:
            logger.exception("rule_evaluation_error rule=%s", rule.get("id"))
            continue
        if not gate_matched:
            continue

        event_ids = [event.event_id]
        if rule.get("correlation"):
            corr_matched, corr_evidence = state.correlation_engine.evaluate(rule, event)
            if not corr_matched:
                continue
            evidence = {**evidence, **corr_evidence}
            event_ids = corr_evidence.get("event_ids", event_ids)

        severity = Severity(rule.get("level") or rule.get("severity") or "medium")
        matched_severities.append(severity)
        hit = DetectionHit(
            rule_id=rule.get("id", "unknown"),
            rule_name=rule.get("title", rule.get("id", "unknown")),
            severity=severity,
            technique_ids=rule.get("technique_ids", []),
            event_ids=event_ids,
            entity_ids=[e.id for e in event.entities],
            score=ensemble.SEVERITY_WEIGHT.get(severity, 0.5),
            description=rule.get("description", ""),
            timestamp=event.timestamp,
            tenant_id=event.tenant_id,
            evidence=evidence,
        )
        hits.append(hit)

    heuristic_val, heuristic_reasons = heuristics.heuristic_score(event)
    temporal_features = state.temporal_tracker.observe(event)

    graph_store = await state.ensure_graph_store(settings)
    graph_features = await compute_graph_features(graph_store, event)
    graph_val = graph_score_from_features(graph_features)

    intel_hits = event.enrichment.get("intel_hits", []) if event.enrichment else []
    intel_val = ensemble.intel_score_from_matches(intel_hits)
    rule_val = ensemble.rule_score_from_hits(matched_severities)

    ml_val = score_from_features(
        {
            "asset_criticality": event.asset_criticality,
            "degree": graph_features.get("degree", 0),
            "rare_edge_score": graph_features.get("rare_edge_score", 0.5),
            "path_length_to_known_bad": graph_features.get("path_length_to_known_bad"),
            "intel_hit_count": len(event.intel_matches),
            "distinct_techniques_window": temporal_features["distinct_techniques_window"],
            "event_count_window": temporal_features["event_count_window"],
        }
    )

    benign_context = any(r.startswith("benign_admin_context:") for r in heuristic_reasons)
    risk = ensemble.combine(
        rule_score=rule_val,
        heuristic_score=heuristic_val,
        graph_score=graph_val,
        intel_score=intel_val,
        ml_score=ml_val,
        benign_context=benign_context,
    )

    alert = None
    if hits or risk.calibrated_score >= MIN_ALERT_SCORE:
        severity = ensemble.severity_from_score(risk.calibrated_score)
        title = hits[0].rule_name if hits else f"Anomalous activity on {event.host or event.user}"
        description = "; ".join(
            [h.description for h in hits] + heuristic_reasons + [f"graph_features={graph_features}"]
        )
        technique_ids = sorted(set(event.technique_ids) | {t for h in hits for t in h.technique_ids})
        alert = state.cluster_store.assign(
            title=title,
            description=description,
            severity=severity,
            risk=risk,
            technique_ids=technique_ids,
            entity_ids=[e.id for e in event.entities],
            event_ids=[event.event_id],
            detection_ids=[h.detection_id for h in hits],
            tenant_id=event.tenant_id,
            tags=list({event.source.value, *([h.rule_id for h in hits])}),
        )

    return hits, alert
