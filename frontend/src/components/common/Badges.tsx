import type { ActionStatus, AlertStatus, CaseStatus, Severity } from "../../types/domain";
import {
  actionStatusBadgeClass,
  alertStatusBadgeClass,
  caseStatusBadgeClass,
  severityBadgeClass,
} from "../../utils/severity";
import { titleCase } from "../../utils/format";

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className={severityBadgeClass(severity)}>
      <span className="badge-dot" />
      {severity}
    </span>
  );
}

export function AlertStatusBadge({ status }: { status: AlertStatus }) {
  return <span className={alertStatusBadgeClass(status)}>{titleCase(status)}</span>;
}

export function CaseStatusBadge({ status }: { status: CaseStatus }) {
  return <span className={caseStatusBadgeClass(status)}>{titleCase(status)}</span>;
}

export function ActionStatusBadge({ status }: { status: ActionStatus }) {
  return <span className={actionStatusBadgeClass(status)}>{titleCase(status)}</span>;
}

export function TagChip({ label }: { label: string }) {
  return <span className="tag-chip">{label}</span>;
}
