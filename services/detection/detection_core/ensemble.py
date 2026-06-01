"""Ensemble risk scorer: combines rule, heuristic, graph, intel, and ML scores."""

from __future__ import annotations

import math

from aegis_common.schema.events import RiskScores, Severity

SEVERITY_WEIGHT = {
    Severity.INFORMATIONAL: 0.1,
    Severity.LOW: 0.3,
    Severity.MEDIUM: 0.55,
    Severity.HIGH: 0.8,
    Severity.CRITICAL: 1.0,
}

WEIGHTS = {
    "rule": 0.35,
    "heuristic": 0.15,
    "graph": 0.20,
    "intel": 0.15,
    "ml": 0.15,
}


def rule_score_from_hits(matched_severities: list[Severity]) -> float:
    if not matched_severities:
        return 0.0
    return round(max(SEVERITY_WEIGHT[s] for s in matched_severities), 3)


def intel_score_from_matches(intel_hits: list[dict]) -> float:
    if not intel_hits:
        return 0.0
    return round(min(1.0, max(h.get("confidence", 0.5) for h in intel_hits) + 0.05 * (len(intel_hits) - 1)), 3)


def combine(
    *,
    rule_score: float,
    heuristic_score: float,
    graph_score: float,
    intel_score: float,
    ml_score: float,
    benign_context: bool = False,
) -> RiskScores:
    ensemble = (
        WEIGHTS["rule"] * rule_score
        + WEIGHTS["heuristic"] * heuristic_score
        + WEIGHTS["graph"] * graph_score
        + WEIGHTS["intel"] * intel_score
        + WEIGHTS["ml"] * ml_score
    )
    # Rule-only hits without intel/graph corroboration and with explicit
    # benign-admin context should not look like multi-stage attacks.
    if benign_context and intel_score < 0.1:
        ensemble *= 0.45
        ensemble = min(ensemble, 0.35)
    ensemble = round(min(ensemble, 1.0), 4)
    # Platt-style sigmoid recalibration to spread mid-range scores and keep
    # extremes stable; centered at 0.5 so a "coin flip" ensemble stays ~0.5.
    calibrated = round(1 / (1 + math.exp(-6 * (ensemble - 0.5))), 4)

    return RiskScores(
        rule_score=rule_score,
        heuristic_score=heuristic_score,
        graph_score=graph_score,
        intel_score=intel_score,
        ml_score=ml_score,
        ensemble_score=ensemble,
        calibrated_score=calibrated,
    )


def severity_from_score(score: float) -> Severity:
    if score >= 0.85:
        return Severity.CRITICAL
    if score >= 0.65:
        return Severity.HIGH
    if score >= 0.4:
        return Severity.MEDIUM
    if score >= 0.2:
        return Severity.LOW
    return Severity.INFORMATIONAL
