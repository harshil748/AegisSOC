import { useState } from "react";
import { listActions, submitApproval } from "../api/actions";
import { ApiError } from "../api/client";
import { ApprovalModal } from "../components/response/ApprovalModal";
import { RecommendationCard } from "../components/response/RecommendationCard";
import { EmptyState, ErrorState, LoadingState } from "../components/common/StateBlocks";
import { ResponseIcon, RefreshIcon } from "../components/icons";
import { useToast } from "../context/ToastContext";
import { useAsync } from "../hooks/useAsync";
import type { ActionRecommendation, ActionStatus } from "../types/domain";

type StatusFilter = ActionStatus | "all";

export function ResponsePage() {
  const toast = useToast();
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [modalState, setModalState] = useState<{
    action: ActionRecommendation;
    decision: "approved" | "rejected";
  } | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const { data, loading, error, refetch } = useAsync(
    (signal) => listActions(statusFilter === "all" ? {} : { status: statusFilter }, signal),
    [statusFilter],
  );

  async function handleSubmit(payload: { rationale: string; dry_run: boolean }) {
    if (!modalState) return;
    setSubmitting(true);
    try {
      await submitApproval({
        action_id: modalState.action.action_id,
        case_id: modalState.action.case_id,
        decision: modalState.decision,
        rationale: payload.rationale,
        dry_run: payload.dry_run,
      });
      toast.push({
        kind: modalState.decision === "approved" ? "success" : "info",
        title: modalState.decision === "approved" ? "Action approved" : "Action rejected",
        message: payload.dry_run && modalState.decision === "approved"
          ? "Dry-run execution recorded. No changes were made to live infrastructure."
          : `${modalState.action.title} \u2014 decision recorded to the audit trail.`,
      });
      setModalState(null);
      refetch();
    } catch (err) {
      toast.push({
        kind: "error",
        title: "Failed to submit decision",
        message: err instanceof ApiError ? err.message : "Unexpected error.",
      });
    } finally {
      setSubmitting(false);
    }
  }

  const actions = data ?? [];

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-heading">
          <h1>Response &amp; Approvals</h1>
          <p>Review recommended playbook actions. Disruptive actions require explicit analyst approval before execution.</p>
        </div>
        <div className="page-actions">
          <select className="select" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}>
            <option value="all">All</option>
            <option value="pending">Pending approval</option>
            <option value="auto_applied_dry_run">Auto-applied (dry-run)</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="executed">Executed</option>
            <option value="rolled_back">Rolled back</option>
          </select>
          <button className="btn btn-sm" onClick={refetch}>
            <RefreshIcon size={13} /> Refresh
          </button>
        </div>
      </div>

      {loading && <LoadingState label="Loading response recommendations\u2026" />}
      {!loading && error && <ErrorState message={error} onRetry={refetch} />}
      {!loading && !error && actions.length === 0 && (
        <EmptyState
          icon={<ResponseIcon size={26} className="state-icon" />}
          title="No recommendations in this queue"
          detail="Run a Demo scenario first, then refresh. High-risk cases create Pending approvals; low-risk ones appear as Auto-applied (dry-run). Switch the status filter to All if the list looks empty."
        />
      )}
      {!loading && !error && actions.length > 0 && (
        <div className="flex-col gap-3">
          {actions.map((action) => (
            <RecommendationCard
              key={action.action_id}
              action={action}
              onApprove={(a) => setModalState({ action: a, decision: "approved" })}
              onReject={(a) => setModalState({ action: a, decision: "rejected" })}
            />
          ))}
        </div>
      )}

      {modalState && (
        <ApprovalModal
          action={modalState.action}
          decision={modalState.decision}
          submitting={submitting}
          onClose={() => setModalState(null)}
          onSubmit={handleSubmit}
        />
      )}
    </div>
  );
}
