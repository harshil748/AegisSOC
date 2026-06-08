import type { ActionRecommendation } from "../../types/domain";
import { formatDateTime, formatPercent } from "../../utils/format";
import { ActionStatusBadge } from "../common/Badges";
import { ConfidenceMeter } from "../common/ConfidenceMeter";
import { AlertTriangleIcon } from "../icons";

const ACTION_CLASS_LABELS: Record<string, string> = {
  notify: "Notify",
  collect_data: "Collect Data",
  create_ticket: "Create Ticket",
  quarantine_recommend: "Quarantine (Recommended)",
  disable_account_recommend: "Disable Account (Recommended)",
  isolate_host_recommend: "Isolate Host (Recommended)",
  block_ioc_recommend: "Block IOC (Recommended)",
  ignore: "Ignore",
  enrich: "Enrich",
  escalate: "Escalate",
};

export function RecommendationCard({
  action,
  onApprove,
  onReject,
  readOnly,
}: {
  action: ActionRecommendation;
  onApprove: (action: ActionRecommendation) => void;
  onReject?: (action: ActionRecommendation) => void;
  readOnly?: boolean;
}) {
  return (
    <div className="card flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2 wrap" style={{ marginBottom: 4 }}>
            <span className="badge badge-outline">{ACTION_CLASS_LABELS[action.action_class] ?? action.action_class}</span>
            {action.disruptive && (
              <span className="badge badge-warning">
                <AlertTriangleIcon size={10} /> Disruptive
              </span>
            )}
            <ActionStatusBadge status={action.status} />
          </div>
          <div style={{ fontWeight: 600, fontSize: 13.5 }}>{action.title}</div>
        </div>
        <span className="text-tertiary" style={{ fontSize: 11, whiteSpace: "nowrap" }}>
          {formatDateTime(action.created_at)}
        </span>
      </div>

      <p style={{ fontSize: 12.5, color: "var(--text-secondary)", margin: 0 }}>{action.description}</p>

      <div
        style={{
          fontSize: 12,
          background: "var(--bg-inset)",
          border: "1px solid var(--border-subtle)",
          borderRadius: "var(--radius-md)",
          padding: "var(--sp-2) var(--sp-3)",
        }}
      >
        <strong style={{ color: "var(--text-secondary)" }}>Impact: </strong>
        {action.impact_summary}
      </div>

      <div className="flex items-center gap-4 wrap">
        <div style={{ minWidth: 140, flex: 1 }}>
          <ConfidenceMeter value={action.confidence} label="Recommendation confidence" />
        </div>
        <span className="badge badge-outline">Risk if executed: {action.risk_if_executed}</span>
        <span className="text-tertiary" style={{ fontSize: 11 }}>
          Case <span className="text-mono">{action.case_id}</span>
        </span>
      </div>

      {!readOnly && action.status === "pending" && (
        <div className="flex gap-2" style={{ marginTop: 4 }}>
          <button className="btn btn-success btn-sm" onClick={() => onApprove(action)}>
            Review &amp; Approve
          </button>
          {onReject && (
            <button className="btn btn-danger btn-sm" onClick={() => onReject(action)}>
              Reject
            </button>
          )}
        </div>
      )}
      {readOnly && action.status === "pending" && (
        <button className="btn btn-sm" onClick={() => onApprove(action)}>
          Go to Response queue ({formatPercent(action.confidence)} confidence)
        </button>
      )}
    </div>
  );
}
