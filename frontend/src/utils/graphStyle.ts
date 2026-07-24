import type { EdgeType, NodeType } from "../types/domain";

/** Node colors tuned for true-black + orange UI (no AI blue/cyan). */
export const NODE_TYPE_COLORS: Record<NodeType, string> = {
  User: "#FF6A00",
  Host: "#3fb97f",
  Process: "#e8c34a",
  File: "#a8a8a3",
  IP: "#d97706",
  Domain: "#8fbc8f",
  URL: "#c4a574",
  Hash: "#6e6e69",
  RegistryKey: "#e8c34a",
  Alert: "#e5484d",
  DetectionRule: "#d97786",
  Email: "#ff9440",
  CloudResource: "#7a9e7e",
  K8sWorkload: "#5fad7a",
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
  return NODE_TYPE_COLORS[type] ?? "#6e6e69";
}

export const EDGE_TYPE_COLORS: Partial<Record<EdgeType, string>> = {
  spawned: "#e8c34a",
  executed: "#e8c34a",
  connected_to: "#d97706",
  resolved_to: "#8fbc8f",
  downloaded: "#f87171",
  modified: "#d97786",
  logged_in_to: "#FF6A00",
  authenticated_to: "#FF6A00",
  created: "#6e6e69",
  accessed: "#6e6e69",
  emailed: "#ff9440",
  triggered: "#e5484d",
  related_to: "#6e6e69",
  observed_in: "#6e6e69",
  mapped_to_technique: "#f87171",
};

export function edgeColor(type: EdgeType): string {
  return EDGE_TYPE_COLORS[type] ?? "#3a3a3a";
}
