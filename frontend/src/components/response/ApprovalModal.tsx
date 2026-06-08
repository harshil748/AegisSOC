import { useState } from "react";
import type { ActionRecommendation } from "../../types/domain";
import { AlertTriangleIcon, XIcon } from "../icons";

export function ApprovalModal({
  action,
  decision,
  onClose,
  onSubmit,
  submitting,
}: {
  action: ActionRecommendation;
  decision: "approved" | "rejected";
  onClose: () => void;
  onSubmit: (payload: { rationale: string; dry_run: boolean }) => void;
  submitting: boolean;
}) {
  const [rationale, setRationale] = useState("");
  const [dryRun, setDryRun] = useState(action.dry_run_default);
  const isApprove = decision === "approved";

  return (
    <div className="modal-overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <div className="modal-header">
          <div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>
              {isApprove ? "Approve response action" : "Reject response action"}
            </div>
            <div className="text-tertiary" style={{ fontSize: 11.5, marginTop: 2 }}>
              {action.title}
            </div>
          </div>
          <button className="btn btn-icon btn-sm btn-ghost" onClick={onClose} aria-label="Close">
            <XIcon size={16} />
          </button>
        </div>

        <div className="modal-body">
          <div
            style={{
              background: "var(--bg-inset)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "var(--sp-3)",
              fontSize: 12.5,
            }}
          >
            <div style={{ marginBottom: 8 }}>
              <strong style={{ color: "var(--text-secondary)" }}>Impact summary</strong>
              <p style={{ margin: "4px 0 0" }}>{action.impact_summary}</p>
            </div>
            <div className="flex gap-3 wrap">
              <span className="badge badge-outline">Risk if executed: {action.risk_if_executed}</span>
              {action.disruptive && (
                <span className="badge badge-warning">
                  <AlertTriangleIcon size={10} /> Disruptive action
                </span>
              )}
            </div>
          </div>

          {isApprove && action.disruptive && (
            <div
              className="flex items-center justify-between"
              style={{
                background: "var(--sev-medium-bg)",
                border: "1px solid rgba(232,195,74,0.3)",
                borderRadius: "var(--radius-md)",
                padding: "var(--sp-3)",
              }}
            >
              <div>
                <div style={{ fontWeight: 600, fontSize: 12.5 }}>Dry-run mode</div>
                <div className="text-secondary" style={{ fontSize: 11.5 }}>
                  Simulate the action without executing it against live infrastructure.
                </div>
              </div>
              <button
                type="button"
                className="switch"
                data-checked={dryRun}
                onClick={() => setDryRun((v) => !v)}
                aria-pressed={dryRun}
                aria-label="Toggle dry-run mode"
              >
                <span className="switch-knob" />
              </button>
            </div>
          )}

          <div className="field">
            <label htmlFor="rationale">
              Rationale {isApprove ? "(analyst justification)" : "(reason for rejection)"}
            </label>
            <textarea
              id="rationale"
              className="textarea"
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
              placeholder={
                isApprove
                  ? "e.g. Evidence confirms lateral movement from compromised host; approving isolation to contain spread."
                  : "e.g. False positive \u2014 confirmed benign scheduled maintenance task."
              }
            />
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn btn-sm" onClick={onClose} disabled={submitting}>
            Cancel
          </button>
          <button
            className={`btn btn-sm ${isApprove ? "btn-success" : "btn-danger"}`}
            disabled={submitting || rationale.trim().length === 0}
            onClick={() => onSubmit({ rationale: rationale.trim(), dry_run: dryRun })}
          >
            {submitting ? "Submitting\u2026" : isApprove ? "Confirm approval" : "Confirm rejection"}
          </button>
        </div>
      </div>
    </div>
  );
}
