import { useNavigate, useParams } from "react-router-dom";
import { listActions } from "../api/actions";
import { getCase } from "../api/cases";
import { CaseStatusBadge, SeverityBadge } from "../components/common/Badges";
import { ErrorState, LoadingState } from "../components/common/StateBlocks";
import { GraphIcon, RefreshIcon } from "../components/icons";
import { RecommendationCard } from "../components/response/RecommendationCard";
import { useAsync } from "../hooks/useAsync";
import { formatDateTime, riskScoreToPercent } from "../utils/format";

export function CaseDetailPage() {
  const { caseId = "" } = useParams<{ caseId: string }>();
  const navigate = useNavigate();

  const caseQuery = useAsync((signal) => getCase(caseId, signal), [caseId]);
  const actionsQuery = useAsync((signal) => listActions({ case_id: caseId }, signal), [caseId]);

  if (caseQuery.loading) {
    return (
      <div className="page">
        <LoadingState label="Loading case\u2026" />
      </div>
    );
  }
  if (caseQuery.error || !caseQuery.data) {
    return (
      <div className="page">
        <ErrorState message={caseQuery.error ?? "Case not found."} onRetry={caseQuery.refetch} />
      </div>
    );
  }

  const c = caseQuery.data;

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-heading">
          <h1>{c.title}</h1>
          <p>
            Case <span className="text-mono">{c.case_id}</span> \u00b7 created {formatDateTime(c.created_at)}
          </p>
        </div>
        <div className="page-actions">
          <button className="btn btn-sm" onClick={() => { caseQuery.refetch(); actionsQuery.refetch(); }}>
            <RefreshIcon size={13} /> Refresh
          </button>
          <button className="btn btn-primary btn-sm" onClick={() => navigate(`/investigate/${c.case_id}`)}>
            <GraphIcon size={14} /> Open Investigation Workspace
          </button>
        </div>
      </div>

      <div className="panel">
        <div className="panel-body flex gap-4 wrap items-center">
          <SeverityBadge severity={c.severity} />
          <CaseStatusBadge status={c.status} />
          <div className="risk-stat">
            <span style={{ fontSize: 10, color: "var(--text-tertiary)", textTransform: "uppercase" }}>Risk score</span>
            <div className="text-mono" style={{ fontSize: 16, fontWeight: 700 }}>
              {riskScoreToPercent(c.risk_score)}
            </div>
          </div>
          <div>
            <span style={{ fontSize: 10, color: "var(--text-tertiary)", textTransform: "uppercase" }}>Assignee</span>
            <div>{c.assignee ?? "Unassigned"}</div>
          </div>
          <div>
            <span style={{ fontSize: 10, color: "var(--text-tertiary)", textTransform: "uppercase" }}>Last updated</span>
            <div>{formatDateTime(c.updated_at)}</div>
          </div>
        </div>
      </div>

      {c.attack_story && (
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">Attack Story</span>
          </div>
          <div className="panel-body" style={{ fontSize: 13, lineHeight: 1.6 }}>
            {c.attack_story}
          </div>
        </div>
      )}

      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">Linked Alerts ({c.alert_ids.length})</span>
        </div>
        <div className="panel-body flex gap-2 wrap">
          {c.alert_ids.length === 0 && <span className="text-tertiary">No alerts linked.</span>}
          {c.alert_ids.map((id) => (
            <span key={id} className="tag-chip">
              {id}
            </span>
          ))}
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">MITRE ATT&amp;CK Techniques</span>
        </div>
        <div className="panel-body flex gap-2 wrap">
          {c.technique_ids.length === 0 && <span className="text-tertiary">No techniques mapped yet.</span>}
          {c.technique_ids.map((t) => (
            <span key={t} className="tag-chip">
              {t}
            </span>
          ))}
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">Response Recommendations</span>
        </div>
        <div className="panel-body flex-col gap-3">
          {actionsQuery.loading && <LoadingState label="Loading recommendations\u2026" />}
          {!actionsQuery.loading && actionsQuery.error && (
            <ErrorState message={actionsQuery.error} onRetry={actionsQuery.refetch} />
          )}
          {!actionsQuery.loading && !actionsQuery.error && (actionsQuery.data ?? []).length === 0 && (
            <span className="text-tertiary" style={{ fontSize: 12.5 }}>
              No response actions recommended for this case yet.
            </span>
          )}
          {!actionsQuery.loading &&
            !actionsQuery.error &&
            (actionsQuery.data ?? []).map((action) => (
              <RecommendationCard key={action.action_id} action={action} onApprove={() => navigate("/response")} readOnly />
            ))}
        </div>
      </div>
    </div>
  );
}
