/**
 * Domain types mirroring the canonical schema in
 * packages/common/aegis_common/schema/events.py
 *
 * Field names intentionally match the backend JSON payloads (snake_case)
 * to avoid a transformation layer between the gateway and the UI.
 */

export type Severity =
  | "informational"
  | "low"
  | "medium"
  | "high"
  | "critical";

export const SEVERITY_ORDER: Severity[] = [
  "critical",
  "high",
  "medium",
  "low",
  "informational",
];

export type AlertStatus =
  | "open"
  | "investigating"
  | "escalated"
  | "closed"
  | "false_positive";

export type CaseStatus =
  | "new"
  | "triaging"
  | "investigating"
  | "contained"
  | "resolved"
  | "false_positive";

export type NodeType =
  | "User"
  | "Host"
  | "Process"
  | "File"
  | "IP"
  | "Domain"
  | "URL"
  | "Hash"
  | "RegistryKey"
  | "Alert"
  | "DetectionRule"
  | "Email"
  | "CloudResource"
  | "K8sWorkload"
  | "AttackTechnique"
  | "Incident";

export type EdgeType =
  | "logged_in_to"
  | "spawned"
  | "executed"
  | "connected_to"
  | "resolved_to"
  | "downloaded"
  | "modified"
  | "authenticated_to"
  | "created"
  | "accessed"
  | "emailed"
  | "triggered"
  | "related_to"
  | "observed_in"
  | "mapped_to_technique";

export type ActionClass =
  | "notify"
  | "collect_data"
  | "create_ticket"
  | "quarantine_recommend"
  | "disable_account_recommend"
  | "isolate_host_recommend"
  | "block_ioc_recommend"
  | "ignore"
  | "enrich"
  | "escalate";

export type ActionStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "executed"
  | "rolled_back"
  | "auto_applied_dry_run";

export type UserRole = "analyst" | "admin";

export interface AuthUser {
  username: string;
  role: UserRole;
  display_name?: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in?: number;
  user: AuthUser;
}

export interface RiskScores {
  rule_score: number;
  heuristic_score: number;
  graph_score: number;
  intel_score: number;
  ml_score: number;
  ensemble_score: number;
  calibrated_score: number;
}

export interface Alert {
  alert_id: string;
  tenant_id: string;
  title: string;
  description: string;
  severity: Severity;
  status: AlertStatus;
  risk: RiskScores;
  technique_ids: string[];
  entity_ids: string[];
  event_ids: string[];
  detection_ids: string[];
  cluster_id?: string | null;
  case_id?: string | null;
  created_at: string;
  updated_at: string;
  priority: number;
  tags: string[];
  provenance: string[];
}

export interface AlertListResponse {
  items: Alert[];
  total: number;
}

export interface Case {
  case_id: string;
  tenant_id: string;
  title: string;
  status: CaseStatus;
  severity: Severity;
  risk_score: number;
  alert_ids: string[];
  entity_ids: string[];
  technique_ids: string[];
  attack_story?: string | null;
  assignee?: string | null;
  created_at: string;
  updated_at: string;
  tags: string[];
}

export interface CaseListResponse {
  items: Case[];
  total: number;
}

export interface GraphNode {
  node_id: string;
  node_type: NodeType;
  labels: string[];
  properties: Record<string, unknown>;
  first_seen: string;
  last_seen: string;
  count: number;
  confidence: number;
  sources: string[];
  display_name?: string;
}

export interface GraphEdge {
  edge_id: string;
  edge_type: EdgeType;
  src_id: string;
  dst_id: string;
  first_seen: string;
  last_seen: string;
  count: number;
  confidence: number;
  properties: Record<string, unknown>;
}

export interface CaseGraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface TimelineEvent {
  event_id: string;
  timestamp: string;
  title: string;
  description: string;
  category: string;
  severity?: Severity;
  source?: string;
  entity_refs?: string[];
  technique_ids?: string[];
}

export interface CaseTimelineResponse {
  items: TimelineEvent[];
}

export interface EvidenceItem {
  evidence_id: string;
  kind: "event" | "node" | "edge" | "detection" | "intel" | string;
  summary: string;
  timestamp?: string | null;
  source?: string | null;
  payload: Record<string, unknown>;
}

export interface AttackMappingEntry {
  technique_id: string;
  technique_name?: string;
  tactic?: string;
  rationale?: string;
}

export interface TriageReport {
  report_id: string;
  case_id: string;
  alert_ids: string[];
  summary: string;
  likely_objective: string;
  attack_mapping: AttackMappingEntry[];
  investigation_queries: string[];
  containment_recommendation: string;
  confidence_explanation: string;
  groundedness_score: number;
  evidence_cited: string[];
  unsupported_claims: string[];
  model_id: string;
  created_at: string;
  analyst_feedback?: string | null;
}

export interface ActionRecommendation {
  action_id: string;
  case_id: string;
  action_class: ActionClass;
  title: string;
  description: string;
  impact_summary: string;
  risk_if_executed: Severity;
  disruptive: boolean;
  dry_run_default: boolean;
  playbook_id?: string | null;
  parameters: Record<string, unknown>;
  evidence_refs: string[];
  confidence: number;
  created_at: string;
  status: ActionStatus;
}

export interface ApprovalRequest {
  action_id: string;
  case_id: string;
  decision: "approved" | "rejected";
  rationale: string;
  dry_run: boolean;
}

export interface ApprovalDecision {
  approval_id: string;
  action_id: string;
  case_id: string;
  decided_by: string;
  decision: "approved" | "rejected";
  rationale: string;
  decided_at: string;
  dry_run: boolean;
}

export interface AuditEvent {
  audit_id: string;
  tenant_id: string;
  actor: string;
  actor_type: "user" | "system" | "llm" | "service" | string;
  action: string;
  resource_type: string;
  resource_id: string;
  timestamp: string;
  details: Record<string, unknown>;
  prompt_hash?: string | null;
  evidence_refs: string[];
}

export interface AuditListResponse {
  items: AuditEvent[];
  total: number;
}

export interface MetricsSnapshot {
  generated_at: string;
  ingestion: {
    events_per_sec: number;
    events_today: number;
    queue_lag_ms: number;
    dlq_count: number;
  };
  detection: {
    alerts_today: number;
    open_alerts: number;
    precision: number;
    recall: number;
    avg_time_to_triage_minutes: number;
  };
  cases: {
    open: number;
    investigating: number;
    resolved_today: number;
    false_positive_rate: number;
  };
  llm: {
    avg_latency_ms: number;
    requests_today: number;
    cost_today_usd: number;
    groundedness_avg: number;
  };
  response: {
    pending_approvals: number;
    approved_today: number;
    rejected_today: number;
    executed_today: number;
  };
}

export interface DemoScenario {
  scenario_id: string;
  title: string;
  description: string;
  expected_outcome?: string | null;
  event_count?: number;
  tags?: string[];
}

export interface DemoPipelineStage {
  id: string;
  label: string;
  detail: string;
}

export interface DemoRunResponse {
  status: string;
  message?: string;
  scenario_id: string;
  case_id?: string | null;
  run_id?: string | null;
  title?: string;
  elapsed_ms?: number;
  events_processed?: number;
  events_total?: number;
  alerts?: unknown[];
  cases?: unknown[];
  pipeline_stages?: string[];
}
