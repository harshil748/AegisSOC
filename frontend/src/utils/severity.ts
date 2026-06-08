import type { ActionStatus, AlertStatus, CaseStatus, Severity } from "../types/domain";

export function severityBadgeClass(severity: Severity): string {
  return `badge badge-${severity}`;
}

export function severityColor(severity: Severity): string {
  switch (severity) {
    case "critical":
      return "var(--sev-critical)";
    case "high":
      return "var(--sev-high)";
    case "medium":
      return "var(--sev-medium)";
    case "low":
      return "var(--sev-low)";
    default:
      return "var(--sev-info)";
  }
}

export function alertStatusBadgeClass(status: AlertStatus): string {
  switch (status) {
    case "open":
      return "badge badge-info";
    case "investigating":
      return "badge badge-warning";
    case "escalated":
      return "badge badge-danger";
    case "closed":
      return "badge badge-neutral";
    case "false_positive":
      return "badge badge-outline";
    default:
      return "badge badge-neutral";
  }
}

export function caseStatusBadgeClass(status: CaseStatus): string {
  switch (status) {
    case "new":
      return "badge badge-info";
    case "triaging":
      return "badge badge-warning";
    case "investigating":
      return "badge badge-warning";
    case "contained":
      return "badge badge-danger";
    case "resolved":
      return "badge badge-success";
    case "false_positive":
      return "badge badge-outline";
    default:
      return "badge badge-neutral";
  }
}

export function actionStatusBadgeClass(status: ActionStatus): string {
  switch (status) {
    case "pending":
      return "badge badge-warning";
    case "approved":
      return "badge badge-success";
    case "executed":
      return "badge badge-info";
    case "rejected":
      return "badge badge-danger";
    case "rolled_back":
      return "badge badge-outline";
    default:
      return "badge badge-neutral";
  }
}
