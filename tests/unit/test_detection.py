"""Unit tests for detection ensemble, Sigma matching, and heuristics."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "common"))
sys.path.insert(0, str(ROOT / "services" / "detection"))

from aegis_common.schema.events import CanonicalEvent, Severity, TelemetrySource  # noqa: E402
from detection_core.ensemble import combine, rule_score_from_hits, severity_from_score  # noqa: E402
from detection_core.heuristics import heuristic_score  # noqa: E402
from detection_core.sigma import load_rules, match_single  # noqa: E402


def test_load_sigma_rules() -> None:
    rules = load_rules()
    assert len(rules) >= 15
    assert all("id" in r and "title" in r for r in rules)


def test_ensemble_weights_produce_calibrated_score() -> None:
    scores = combine(
        rule_score=0.9,
        heuristic_score=0.5,
        graph_score=0.7,
        intel_score=0.8,
        ml_score=0.6,
    )
    assert 0.0 < scores.ensemble_score <= 1.0
    assert 0.0 < scores.calibrated_score <= 1.0
    assert scores.rule_score == 0.9


def test_rule_score_escalates_with_critical_hits() -> None:
    low = rule_score_from_hits([Severity.LOW])
    critical = rule_score_from_hits([Severity.CRITICAL, Severity.HIGH])
    assert critical > low


def test_severity_from_score_thresholds() -> None:
    assert severity_from_score(0.95) == Severity.CRITICAL
    assert severity_from_score(0.1) in {Severity.INFORMATIONAL, Severity.LOW}


def test_encoded_powershell_heuristic() -> None:
    event = CanonicalEvent(
        timestamp=datetime.now(timezone.utc),
        source=TelemetrySource.SYSMON,
        event_type="process_creation",
        process="powershell.exe",
        command_line="powershell -enc SQBFAFgA...",
    )
    score, reasons = heuristic_score(event)
    assert score > 0.0
    assert reasons


def test_sigma_matches_suspicious_powershell() -> None:
    rules = load_rules()
    event = CanonicalEvent(
        timestamp=datetime.now(timezone.utc),
        source=TelemetrySource.SYSMON,
        event_type="process_creation",
        process="powershell.exe",
        command_line="powershell.exe -EncodedCommand JABzAD0A...",
        parent_process="WINWORD.EXE",
        raw={
            "Image": "C:\\\\Windows\\\\System32\\\\WindowsPowerShell\\\\v1.0\\\\powershell.exe",
            "CommandLine": "powershell.exe -EncodedCommand JABzAD0A...",
            "ParentImage": "C:\\\\Program Files\\\\Microsoft Office\\\\WINWORD.EXE",
        },
    )
    matched = [r["id"] for r in rules if match_single(r, event)[0]]
    # At least one of the PowerShell / Office-spawn rules should fire
    assert matched, "expected at least one Sigma rule to match encoded PowerShell from Office"
