"""Canonical security event schema and graph ontology for AegisSOC."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class TelemetrySource(str, Enum):
    SYSMON = "sysmon"
    WINDOWS = "windows"
    ZEEK = "zeek"
    SURICATA = "suricata"
    FIREWALL = "firewall"
    DNS = "dns"
    EDR = "edr"
    ACTIVE_DIRECTORY = "active_directory"
    CLOUDTRAIL = "cloudtrail"
    KUBERNETES = "kubernetes"
    EMAIL = "email"
    THREAT_INTEL = "threat_intel"
    SYNTHETIC = "synthetic"


TELEMETRY_SOURCE_ALIASES: dict[str, str] = {
    "ad_auth": "active_directory",
    "ad": "active_directory",
    "windows_security": "windows",
    "firewall_dns": "dns",
    "network_firewall": "firewall",
}


def resolve_telemetry_source(value: str) -> "TelemetrySource":
    """Maps loosely-named/legacy source strings (as seen in some scenario
    fixtures and third-party log shippers) onto the canonical
    ``TelemetrySource`` vocabulary, falling back to ``SYNTHETIC`` for
    anything unrecognized rather than raising."""

    normalized = TELEMETRY_SOURCE_ALIASES.get(value, value)
    try:
        return TelemetrySource(normalized)
    except ValueError:
        return TelemetrySource.SYNTHETIC


class Severity(str, Enum):
    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NodeType(str, Enum):
    USER = "User"
    HOST = "Host"
    PROCESS = "Process"
    FILE = "File"
    IP = "IP"
    DOMAIN = "Domain"
    URL = "URL"
    HASH = "Hash"
    REGISTRY_KEY = "RegistryKey"
    ALERT = "Alert"
    DETECTION_RULE = "DetectionRule"
    EMAIL = "Email"
    CLOUD_RESOURCE = "CloudResource"
    K8S_WORKLOAD = "K8sWorkload"
    ATTACK_TECHNIQUE = "AttackTechnique"
    INCIDENT = "Incident"


class EdgeType(str, Enum):
    LOGGED_IN_TO = "logged_in_to"
    SPAWNED = "spawned"
    EXECUTED = "executed"
    CONNECTED_TO = "connected_to"
    RESOLVED_TO = "resolved_to"
    DOWNLOADED = "downloaded"
    MODIFIED = "modified"
    AUTHENTICATED_TO = "authenticated_to"
    CREATED = "created"
    ACCESSED = "accessed"
    EMAILED = "emailed"
    TRIGGERED = "triggered"
    RELATED_TO = "related_to"
    OBSERVED_IN = "observed_in"
    MAPPED_TO_TECHNIQUE = "mapped_to_technique"


class Provenance(BaseModel):
    raw_event_id: str
    topic: str | None = None
    offset: int | None = None
    source: TelemetrySource
    ingested_at: datetime


class EntityRef(BaseModel):
    type: NodeType
    id: str
    display_name: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class CanonicalEvent(BaseModel):
    """Normalized cross-source security event."""

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str = "default"
    timestamp: datetime
    ingested_at: datetime | None = None
    source: TelemetrySource
    source_confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    event_type: str
    severity: Severity = Severity.INFORMATIONAL
    host: str | None = None
    user: str | None = None
    process: str | None = None
    process_id: int | None = None
    parent_process: str | None = None
    parent_process_id: int | None = None
    command_line: str | None = None
    file_path: str | None = None
    file_hash: str | None = None
    src_ip: str | None = None
    dst_ip: str | None = None
    src_port: int | None = None
    dst_port: int | None = None
    domain: str | None = None
    url: str | None = None
    email_from: str | None = None
    email_to: str | None = None
    email_subject: str | None = None
    cloud_account: str | None = None
    cloud_resource: str | None = None
    k8s_namespace: str | None = None
    k8s_pod: str | None = None
    registry_key: str | None = None
    technique_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)
    entities: list[EntityRef] = Field(default_factory=list)
    provenance: Provenance | None = None
    asset_criticality: float = Field(ge=0.0, le=1.0, default=0.5)
    intel_matches: list[str] = Field(default_factory=list)
    enrichment: dict[str, Any] = Field(default_factory=dict)


class GraphNode(BaseModel):
    node_id: str
    node_type: NodeType
    tenant_id: str = "default"
    labels: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    first_seen: datetime
    last_seen: datetime
    count: int = 1
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    sources: list[TelemetrySource] = Field(default_factory=list)
    provenance_ids: list[str] = Field(default_factory=list)


class GraphEdge(BaseModel):
    edge_id: str = Field(default_factory=lambda: str(uuid4()))
    edge_type: EdgeType
    src_id: str
    dst_id: str
    tenant_id: str = "default"
    first_seen: datetime
    last_seen: datetime
    count: int = 1
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    sources: list[TelemetrySource] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    provenance_ids: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)


class DetectionHit(BaseModel):
    detection_id: str = Field(default_factory=lambda: str(uuid4()))
    rule_id: str
    rule_name: str
    severity: Severity
    technique_ids: list[str] = Field(default_factory=list)
    event_ids: list[str] = Field(default_factory=list)
    entity_ids: list[str] = Field(default_factory=list)
    score: float = Field(ge=0.0, le=1.0)
    description: str
    tenant_id: str = "default"
    timestamp: datetime
    evidence: dict[str, Any] = Field(default_factory=dict)


class RiskScores(BaseModel):
    rule_score: float = 0.0
    heuristic_score: float = 0.0
    graph_score: float = 0.0
    intel_score: float = 0.0
    ml_score: float = 0.0
    ensemble_score: float = 0.0
    calibrated_score: float = 0.0


class Alert(BaseModel):
    alert_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str = "default"
    title: str
    description: str
    severity: Severity
    status: str = "open"  # open | investigating | escalated | closed | false_positive
    risk: RiskScores = Field(default_factory=RiskScores)
    technique_ids: list[str] = Field(default_factory=list)
    entity_ids: list[str] = Field(default_factory=list)
    event_ids: list[str] = Field(default_factory=list)
    detection_ids: list[str] = Field(default_factory=list)
    cluster_id: str | None = None
    case_id: str | None = None
    created_at: datetime
    updated_at: datetime
    priority: int = 50
    tags: list[str] = Field(default_factory=list)
    provenance: list[str] = Field(default_factory=list)


class CaseStatus(str, Enum):
    NEW = "new"
    TRIAGING = "triaging"
    INVESTIGATING = "investigating"
    CONTAINED = "contained"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


class Case(BaseModel):
    case_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str = "default"
    title: str
    status: CaseStatus = CaseStatus.NEW
    severity: Severity
    risk_score: float = 0.0
    alert_ids: list[str] = Field(default_factory=list)
    entity_ids: list[str] = Field(default_factory=list)
    technique_ids: list[str] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    attack_story: str | None = None
    assignee: str | None = None
    created_at: datetime
    updated_at: datetime
    tags: list[str] = Field(default_factory=list)


class ActionClass(str, Enum):
    NOTIFY = "notify"
    COLLECT_DATA = "collect_data"
    CREATE_TICKET = "create_ticket"
    QUARANTINE_RECOMMEND = "quarantine_recommend"
    DISABLE_ACCOUNT_RECOMMEND = "disable_account_recommend"
    ISOLATE_HOST_RECOMMEND = "isolate_host_recommend"
    BLOCK_IOC_RECOMMEND = "block_ioc_recommend"
    IGNORE = "ignore"
    ENRICH = "enrich"
    ESCALATE = "escalate"


class ActionRecommendation(BaseModel):
    action_id: str = Field(default_factory=lambda: str(uuid4()))
    case_id: str
    action_class: ActionClass
    title: str
    description: str
    impact_summary: str
    risk_if_executed: Severity
    disruptive: bool
    dry_run_default: bool = True
    playbook_id: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.7)
    created_at: datetime
    status: str = "pending"  # pending | approved | rejected | executed | rolled_back


class ApprovalDecision(BaseModel):
    approval_id: str = Field(default_factory=lambda: str(uuid4()))
    action_id: str
    case_id: str
    decided_by: str
    decision: str  # approved | rejected
    rationale: str
    decided_at: datetime
    dry_run: bool = True


class AuditEvent(BaseModel):
    audit_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str = "default"
    actor: str
    actor_type: str  # user | system | llm | service
    action: str
    resource_type: str
    resource_id: str
    timestamp: datetime
    details: dict[str, Any] = Field(default_factory=dict)
    prompt_hash: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    evidence_id: str
    kind: str  # event | node | edge | detection | intel
    summary: str
    timestamp: datetime | None = None
    source: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class TriageReport(BaseModel):
    report_id: str = Field(default_factory=lambda: str(uuid4()))
    case_id: str
    alert_ids: list[str] = Field(default_factory=list)
    summary: str
    likely_objective: str
    attack_mapping: list[dict[str, str]] = Field(default_factory=list)
    investigation_queries: list[str] = Field(default_factory=list)
    containment_recommendation: str
    confidence_explanation: str
    groundedness_score: float = Field(ge=0.0, le=1.0)
    evidence_cited: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    model_id: str
    created_at: datetime
    analyst_feedback: str | None = None
