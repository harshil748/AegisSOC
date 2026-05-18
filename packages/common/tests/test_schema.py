"""Unit tests for the canonical schema and helper utilities."""

from __future__ import annotations

from datetime import datetime, timezone

from aegis_common.schema.events import (
    Alert,
    CanonicalEvent,
    RiskScores,
    Severity,
    TelemetrySource,
)
from aegis_common.utils.helpers import entity_id, redact_pii, stable_hash


def test_canonical_event_defaults() -> None:
    event = CanonicalEvent(
        timestamp=datetime.now(timezone.utc),
        source=TelemetrySource.SYSMON,
        event_type="process_creation",
    )
    assert event.tenant_id == "default"
    assert event.severity == Severity.INFORMATIONAL
    assert 0.0 <= event.source_confidence <= 1.0


def test_alert_risk_scores_default_zero() -> None:
    alert = Alert(
        title="Test alert",
        description="unit test",
        severity=Severity.HIGH,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    assert isinstance(alert.risk, RiskScores)
    assert alert.risk.ensemble_score == 0.0


def test_entity_id_is_deterministic_and_tenant_scoped() -> None:
    id_a = entity_id("Host", "WIN-JSMITH-01", tenant_id="tenant-a")
    id_b = entity_id("Host", "win-jsmith-01", tenant_id="tenant-a")  # case-insensitive
    id_c = entity_id("Host", "WIN-JSMITH-01", tenant_id="tenant-b")

    assert id_a == id_b, "entity_id should normalize case/whitespace"
    assert id_a != id_c, "entity_id must be tenant-scoped to prevent cross-tenant collisions"


def test_stable_hash_is_deterministic() -> None:
    assert stable_hash("abc") == stable_hash("abc")
    assert stable_hash("abc") != stable_hash("abd")


def test_redact_pii_masks_email_and_ip() -> None:
    text = "Contact jsmith@corp.local from 192.168.1.42"
    redacted = redact_pii(text)
    assert "jsmith@corp.local" not in redacted
    assert "[REDACTED_EMAIL]" in redacted
    assert "192.168.1.xxx" in redacted
