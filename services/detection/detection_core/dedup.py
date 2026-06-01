"""Alert deduplication and clustering.

New detections are merged into an existing open alert/cluster when they
share enough entities/techniques within a recency window (Jaccard overlap
on entity_ids ∪ technique_ids), otherwise a new alert+cluster is created.
This keeps a multi-stage attack chain as a single evolving alert instead of
one alert per matched rule per event -- the single biggest driver of alert
fatigue in real SOCs.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from aegis_common.schema.events import Alert, DetectionHit, RiskScores, Severity
from aegis_common.utils.helpers import utcnow

CLUSTER_WINDOW = timedelta(minutes=45)
OVERLAP_THRESHOLD = 0.15


@dataclass
class Cluster:
    cluster_id: str
    alert: Alert
    entity_ids: set[str] = field(default_factory=set)
    technique_ids: set[str] = field(default_factory=set)
    last_updated: datetime = field(default_factory=utcnow)


class AlertClusterStore:
    def __init__(self) -> None:
        self._clusters: dict[str, Cluster] = {}

    def _find_match(self, entity_ids: set[str], technique_ids: set[str], now: datetime) -> Cluster | None:
        combined = entity_ids | technique_ids
        best: Cluster | None = None
        best_score = 0.0
        for cluster in self._clusters.values():
            if now - cluster.last_updated > CLUSTER_WINDOW:
                continue
            existing = cluster.entity_ids | cluster.technique_ids
            if not existing or not combined:
                continue
            overlap = len(existing & combined) / len(existing | combined)
            if overlap >= OVERLAP_THRESHOLD and overlap > best_score:
                best = cluster
                best_score = overlap
        return best

    def assign(
        self,
        *,
        title: str,
        description: str,
        severity: Severity,
        risk: RiskScores,
        technique_ids: list[str],
        entity_ids: list[str],
        event_ids: list[str],
        detection_ids: list[str],
        tenant_id: str = "default",
        tags: list[str] | None = None,
    ) -> Alert:
        now = utcnow()
        entity_set, technique_set = set(entity_ids), set(technique_ids)
        cluster = self._find_match(entity_set, technique_set, now)

        if cluster is None:
            alert = Alert(
                tenant_id=tenant_id,
                title=title,
                description=description,
                severity=severity,
                risk=risk,
                technique_ids=technique_ids,
                entity_ids=entity_ids,
                event_ids=event_ids,
                detection_ids=detection_ids,
                cluster_id=str(uuid.uuid4()),
                created_at=now,
                updated_at=now,
                priority=int(risk.calibrated_score * 100),
                tags=tags or [],
            )
            cluster = Cluster(
                cluster_id=alert.cluster_id,
                alert=alert,
                entity_ids=entity_set,
                technique_ids=technique_set,
                last_updated=now,
            )
            self._clusters[cluster.cluster_id] = cluster
            return alert

        alert = cluster.alert
        alert.entity_ids = list(set(alert.entity_ids) | entity_set)
        alert.technique_ids = list(set(alert.technique_ids) | technique_set)
        alert.event_ids = list(set(alert.event_ids) | set(event_ids))
        alert.detection_ids = list(set(alert.detection_ids) | set(detection_ids))
        alert.updated_at = now
        if risk.calibrated_score > alert.risk.calibrated_score:
            alert.risk = risk
            alert.severity = severity
            alert.priority = int(risk.calibrated_score * 100)
        if description not in alert.description:
            alert.description = f"{alert.description}\n---\n{description}"
        cluster.entity_ids |= entity_set
        cluster.technique_ids |= technique_set
        cluster.last_updated = now
        return alert

    def get(self, cluster_id: str) -> Alert | None:
        cluster = self._clusters.get(cluster_id)
        return cluster.alert if cluster else None

    def all_alerts(self) -> list[Alert]:
        return [c.alert for c in self._clusters.values()]
