import type { EdgeType, NodeType } from "../types/domain";

export const NODE_TYPE_COLORS: Record<NodeType, string> = {
  User: "#4f8fd1",
  Host: "#3fb97f",
  Process: "#e8c34a",
  File: "#8fb8e0",
  IP: "#f0883e",
  Domain: "#5eead4",
  URL: "#38bdf8",
  Hash: "#94a3b8",
  RegistryKey: "#fbbf24",
  Alert: "#e5484d",
  DetectionRule: "#d97786",
  Email: "#60a5fa",
  CloudResource: "#22d3ee",
  K8sWorkload: "#34d399",
  AttackTechnique: "#f87171",
  Incident: "#eab308",
};

export const NODE_TYPE_ORDER: NodeType[] = [
  "Incident",
  "Alert",
  "AttackTechnique",
  "DetectionRule",
  "User",
  "Host",
  "Process",
  "File",
  "Hash",
  "RegistryKey",
  "IP",
  "Domain",
  "URL",
  "Email",
  "CloudResource",
  "K8sWorkload",
];

export function nodeColor(type: NodeType): string {
  return NODE_TYPE_COLORS[type] ?? "#7c8ba1";
}

export const EDGE_TYPE_COLORS: Partial<Record<EdgeType, string>> = {
  spawned: "#e8c34a",
  executed: "#e8c34a",
  connected_to: "#f0883e",
  resolved_to: "#5eead4",
  downloaded: "#f87171",
  modified: "#d97786",
  logged_in_to: "#4f8fd1",
  authenticated_to: "#4f8fd1",
  created: "#94a3b8",
  accessed: "#94a3b8",
  emailed: "#60a5fa",
  triggered: "#e5484d",
  related_to: "#7c8ba1",
  observed_in: "#7c8ba1",
  mapped_to_technique: "#f87171",
};

export function edgeColor(type: EdgeType): string {
  return EDGE_TYPE_COLORS[type] ?? "#556277";
}
