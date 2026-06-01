"""Real (OpenAI-compatible) LLM call with a deterministic mock fallback.

The mock path is not a lesser citizen: it runs the exact same grounding and
validation pipeline as the real path, just using a template instead of a
model call, so the whole platform is demoable with zero API keys and CI
never depends on a live LLM.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from aegis_common.schema.events import EvidenceItem

from triage_core.prompt_templates import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger("aegis.llm_triage.client")

# Ordered worst-stage-wins: the mock fallback picks the *most advanced*
# kill-chain stage present in the cited alerts' technique_ids so a
# multi-stage case (e.g. phishing -> credential access -> lateral movement)
# is labeled by its most severe confirmed stage rather than a generic
# constant, and a low-risk cluster with only reconnaissance/defense-evasion
# style techniques doesn't get over-labeled as "lateral movement".
_TECHNIQUE_OBJECTIVES: list[tuple[str, str]] = [
    ("T1486", "ransomware_deployment"),
    ("T1490", "ransomware_deployment"),
    ("T1489", "impact_service_disruption"),
    ("T1021", "credential_access_and_lateral_movement"),
    ("T1570", "credential_access_and_lateral_movement"),
    ("T1003", "credential_access_and_lateral_movement"),
    ("T1078", "credential_access_and_lateral_movement"),
    ("T1110", "credential_access_and_lateral_movement"),
    ("T1566", "initial_access_phishing"),
    ("T1204", "initial_access_phishing"),
    ("T1071", "command_and_control"),
    ("T1573", "command_and_control"),
    ("T1583", "infrastructure_reconnaissance"),
    ("T1059", "suspicious_scripting_or_execution"),
    ("T1027", "defense_evasion"),
    ("T1055", "defense_evasion"),
]
# Below this calibrated ensemble risk score, the mock summarizer prefers a
# "likely benign" framing over a specific attack-objective label even if a
# rule matched -- this is what lets the benign_admin_false_positive demo
# scenario actually read as a down-weighted false positive end to end
# (see README "Demo scenario walkthrough" #2) instead of always describing
# every case the same way.
_LIKELY_BENIGN_THRESHOLD = 0.45


async def call_real_llm(
    *, case_id: str, evidence: list[EvidenceItem], api_key: str, base_url: str | None, model: str
) -> dict[str, Any]:
    from openai import AsyncOpenAI  # lazy import: optional dependency

    client = AsyncOpenAI(api_key=api_key, base_url=base_url or None)
    response = await client.chat.completions.create(
        model=model,
        temperature=0.1,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(case_id, evidence)},
        ],
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    return json.loads(content)


def _infer_likely_objective(technique_ids: set[str], highest_calibrated_score: float, has_alerts: bool) -> str:
    if not has_alerts:
        return "insufficient_evidence"
    for prefix, objective in _TECHNIQUE_OBJECTIVES:
        if any(tid.startswith(prefix) for tid in technique_ids):
            if highest_calibrated_score < _LIKELY_BENIGN_THRESHOLD:
                return f"likely_benign_activity_resembling_{objective}"
            return objective
    return "likely_benign_activity" if highest_calibrated_score < _LIKELY_BENIGN_THRESHOLD else "suspicious_activity_requires_review"


def mock_grounded_summary(case_id: str, evidence: list[EvidenceItem]) -> dict[str, Any]:
    """Template-based grounded summarizer used when no LLM API key is configured.

    Deterministically derives a summary purely from the retrieved evidence
    (never inventing facts), citing evidence_ids exactly like the real LLM
    path is instructed to.
    """

    by_kind: dict[str, list[EvidenceItem]] = {}
    for item in evidence:
        by_kind.setdefault(item.kind, []).append(item)

    case_items = by_kind.get("case", [])
    alert_items = by_kind.get("alert", [])
    event_items = by_kind.get("event", [])
    node_items = by_kind.get("node", [])

    summary_parts = []
    if case_items:
        c = case_items[0]
        summary_parts.append(f"{c.summary} [{c.evidence_id}]")
    for a in alert_items[:3]:
        summary_parts.append(f"{a.summary} [{a.evidence_id}]")
    for e in event_items[:3]:
        summary_parts.append(f"{e.summary} [{e.evidence_id}]")
    summary = " ".join(summary_parts) if summary_parts else "No evidence was retrieved for this case."

    technique_ids: set[str] = set()
    attack_mapping = []
    for item in evidence:
        for tid in item.payload.get("technique_ids", []) if isinstance(item.payload, dict) else []:
            if tid not in technique_ids:
                technique_ids.add(tid)
                attack_mapping.append({"technique_id": tid, "name": tid, "evidence_id": item.evidence_id})

    investigation_queries = []
    if event_items:
        investigation_queries.append(
            f"Pull the full process/network timeline for the entities referenced in {event_items[0].evidence_id}"
        )
    if node_items:
        investigation_queries.append(
            f"Expand the graph neighborhood referenced in {node_items[0].evidence_id} to depth 2 for lateral-movement evidence"
        )
    if not investigation_queries:
        investigation_queries.append("Retrieve additional host/user telemetry; current evidence volume is low")

    highest_severity_alert = max(
        (a.payload.get("risk", {}).get("calibrated_score", 0.0) for a in alert_items), default=0.0
    )
    containment = (
        "No corroborating alert evidence was found; recommend continued monitoring rather than containment."
        if not alert_items
        else (
            f"Given calibrated risk score {highest_severity_alert:.2f} across {len(alert_items)} alert(s) "
            f"[{', '.join(a.evidence_id for a in alert_items[:3])}], recommend an analyst review isolate-host "
            "or disable-account playbooks via the response_policy service; no action is auto-executed."
        )
    )

    return {
        "summary": summary,
        "likely_objective": _infer_likely_objective(
            technique_ids, highest_severity_alert, has_alerts=bool(alert_items)
        ),
        "attack_mapping": attack_mapping,
        "investigation_queries": investigation_queries,
        "containment_recommendation": containment,
        "confidence_explanation": (
            f"Derived from {len(evidence)} retrieved evidence item(s) "
            f"({len(case_items)} case, {len(alert_items)} alert, {len(event_items)} event, {len(node_items)} graph); "
            "this is a template-based fallback summary (no LLM API key configured), not a model judgment."
        ),
        "unsupported_claims": [],
    }


async def generate(
    *,
    case_id: str,
    evidence: list[EvidenceItem],
    llm_enabled: bool,
    api_key: str | None,
    base_url: str | None,
    model: str,
) -> tuple[dict[str, Any], bool]:
    """Returns (result_dict, used_mock)."""

    if llm_enabled and api_key:
        try:
            result = await call_real_llm(
                case_id=case_id, evidence=evidence, api_key=api_key, base_url=base_url, model=model
            )
            return result, False
        except Exception:
            logger.exception("real_llm_call_failed_falling_back_to_mock")
    return mock_grounded_summary(case_id, evidence), True
