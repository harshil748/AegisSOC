"""Integration test: full in-process demo pipeline for all canonical scenarios."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for rel in [
    "packages/common",
    "services/frontend_gateway",
    "services/normalization",
    "services/enrichment",
    "services/graph_builder",
    "services/detection",
    "services/case_management",
    "services/llm_triage",
    "services/response_policy",
    "services/ingestion",
    "services/approval",
    "services/audit",
]:
    sys.path.insert(0, str(ROOT / rel))

os.environ["AEGIS_SYNC_MODE"] = "true"

from gateway_core.demo_pipeline import available_scenarios, run_scenario  # noqa: E402
from gateway_core.inprocess import reset_for_tests  # noqa: E402


@pytest.fixture(autouse=True)
def _reset():
    reset_for_tests()
    yield
    reset_for_tests()


@pytest.mark.asyncio
async def test_available_scenarios_include_three_demos() -> None:
    ids = {s["scenario_id"] for s in available_scenarios()}
    assert "phishing_ransomware_chain" in ids
    assert "benign_admin_false_positive" in ids
    assert "repeat_attacker_infra" in ids


@pytest.mark.asyncio
async def test_phishing_chain_produces_high_risk_case() -> None:
    result = await run_scenario("phishing_ransomware_chain")
    assert result["status"] == "completed"
    assert result["stage_errors"] == []
    assert result["events_processed"] == result["events_total"]
    assert result["case_id"]
    assert len(result["alerts"]) >= 1
    assert len(result["detection_hits"]) >= 1
    assert len(result["recommendations"]) >= 1
    assert len(result["triage_reports"]) >= 1
    max_risk = max(
        (a.get("risk") or {}).get("calibrated_score")
        or (a.get("risk") or {}).get("ensemble_score")
        or 0.0
        for a in result["alerts"]
    )
    assert max_risk >= 0.5


@pytest.mark.asyncio
async def test_benign_admin_scores_lower_than_attack() -> None:
    attack = await run_scenario("phishing_ransomware_chain")
    reset_for_tests()
    benign = await run_scenario("benign_admin_false_positive")

    def _max_risk(r: dict) -> float:
        alerts = r.get("alerts") or []
        if not alerts:
            return 0.0
        return max(
            (a.get("risk") or {}).get("calibrated_score")
            or (a.get("risk") or {}).get("ensemble_score")
            or 0.0
            for a in alerts
        )

    assert _max_risk(benign) < _max_risk(attack)
    assert _max_risk(benign) < 0.55
    reports = benign.get("triage_reports") or {}
    if isinstance(reports, dict):
        reports = list(reports.values())
    assert reports
    objective = (reports[0].get("likely_objective") or "").lower()
    assert "benign" in objective or _max_risk(benign) < 0.45


@pytest.mark.asyncio
async def test_repeat_attacker_completes_with_graph_memory() -> None:
    result = await run_scenario("repeat_attacker_infra")
    assert result["status"] == "completed"
    assert result["stage_errors"] == []
    assert result["graph_updates_applied"]["nodes"] > 0
    assert result["graph_updates_applied"]["edges"] > 0
    assert result["case_id"]
