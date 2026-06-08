import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { listCases } from "../api/cases";
import { CaseStatusBadge, SeverityBadge } from "../components/common/Badges";
import { EmptyState, ErrorState, LoadingState } from "../components/common/StateBlocks";
import { CaseIcon, RefreshIcon, SearchIcon } from "../components/icons";
import { useAsync } from "../hooks/useAsync";
import type { CaseStatus, Severity } from "../types/domain";
import { formatDateTime, riskScoreToPercent } from "../utils/format";

export function CasesPage() {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<CaseStatus | "">("");
  const [severity, setSeverity] = useState<Severity | "">("");

  const { data, loading, error, refetch } = useAsync(
    (signal) =>
      listCases(
        {
          q: q || undefined,
          status: status || undefined,
          severity: severity || undefined,
          limit: 200,
        },
        signal,
      ),
    [q, status, severity],
  );

  const cases = data?.items ?? [];

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-heading">
          <h1>Cases</h1>
          <p>Correlated incidents grouped from one or more alerts sharing entities or attack patterns.</p>
        </div>
        <div className="page-actions">
          <button className="btn btn-sm" onClick={refetch}>
            <RefreshIcon size={13} /> Refresh
          </button>
        </div>
      </div>

      <div className="panel">
        <div className="panel-body flex items-center gap-3 wrap">
          <div style={{ position: "relative", flex: "1 1 220px", minWidth: 200 }}>
            <SearchIcon
              size={14}
              style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--text-tertiary)" }}
            />
            <input
              className="input"
              style={{ paddingLeft: 30, width: "100%" }}
              placeholder="Search case title, tag\u2026"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
          <select className="select" value={severity} onChange={(e) => setSeverity(e.target.value as Severity | "")}>
            <option value="">All severities</option>
            {(["critical", "high", "medium", "low", "informational"] as Severity[]).map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <select className="select" value={status} onChange={(e) => setStatus(e.target.value as CaseStatus | "")}>
            <option value="">All statuses</option>
            {(["new", "triaging", "investigating", "contained", "resolved", "false_positive"] as CaseStatus[]).map(
              (s) => (
                <option key={s} value={s}>
                  {s.replace(/_/g, " ")}
                </option>
              ),
            )}
          </select>
          {data && (
            <span className="text-tertiary" style={{ fontSize: 12, marginLeft: "auto" }}>
              {data.total} case{data.total === 1 ? "" : "s"}
            </span>
          )}
        </div>
      </div>

      {loading && <LoadingState label="Loading cases\u2026" />}
      {!loading && error && <ErrorState message={error} onRetry={refetch} />}
      {!loading && !error && cases.length === 0 && (
        <EmptyState
          icon={<CaseIcon size={28} className="state-icon" />}
          title="No cases found"
          detail="Cases are created automatically when correlated alerts form an incident cluster."
        />
      )}
      {!loading && !error && cases.length > 0 && (
        <div className="data-table-wrap panel">
          <table className="data-table">
            <thead>
              <tr>
                <th>Severity</th>
                <th>Risk</th>
                <th>Title</th>
                <th>Status</th>
                <th>Alerts</th>
                <th>Assignee</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.case_id} className="clickable" onClick={() => navigate(`/cases/${c.case_id}`)}>
                  <td>
                    <SeverityBadge severity={c.severity} />
                  </td>
                  <td>
                    <span className="text-mono" style={{ fontWeight: 600 }}>
                      {riskScoreToPercent(c.risk_score)}
                    </span>
                  </td>
                  <td style={{ maxWidth: 320 }}>
                    <div className="truncate" style={{ fontWeight: 500 }}>
                      {c.title}
                    </div>
                  </td>
                  <td>
                    <CaseStatusBadge status={c.status} />
                  </td>
                  <td>{c.alert_ids.length}</td>
                  <td className="text-secondary">{c.assignee ?? "Unassigned"}</td>
                  <td className="text-tertiary" style={{ whiteSpace: "nowrap" }}>
                    {formatDateTime(c.updated_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
