import { useNavigate } from "react-router-dom";
import type { Alert } from "../../types/domain";
import { SeverityBadge, AlertStatusBadge, TagChip } from "../common/Badges";
import { formatDateTime, riskScoreToPercent } from "../../utils/format";

export type AlertSortKey = "risk" | "created_at" | "severity";

export function AlertTable({
  alerts,
  sortKey,
  sortDir,
  onSort,
}: {
  alerts: Alert[];
  sortKey: AlertSortKey;
  sortDir: "asc" | "desc";
  onSort: (key: AlertSortKey) => void;
}) {
  const navigate = useNavigate();

  function caret(key: AlertSortKey) {
    if (sortKey !== key) return "";
    return sortDir === "asc" ? " \u2191" : " \u2193";
  }

  return (
    <div className="data-table-wrap panel">
      <table className="data-table">
        <thead>
          <tr>
            <th className="sortable" onClick={() => onSort("severity")}>
              Severity{caret("severity")}
            </th>
            <th className="sortable" onClick={() => onSort("risk")}>
              Risk{caret("risk")}
            </th>
            <th>Title</th>
            <th>Techniques</th>
            <th>Status</th>
            <th className="sortable" onClick={() => onSort("created_at")}>
              Created{caret("created_at")}
            </th>
          </tr>
        </thead>
        <tbody>
          {alerts.map((alert) => {
            const risk = riskScoreToPercent(alert.risk.calibrated_score || alert.risk.ensemble_score);
            const caseId = alert.case_id;
            return (
              <tr
                key={alert.alert_id}
                className={caseId ? "clickable" : undefined}
                onClick={() => {
                  if (caseId) navigate(`/investigate/${caseId}`);
                }}
                title={caseId ? undefined : "No linked case yet"}
              >
                <td>
                  <SeverityBadge severity={alert.severity} />
                </td>
                <td>
                  <span className="text-mono" style={{ fontWeight: 600 }}>
                    {risk}
                  </span>
                </td>
                <td style={{ maxWidth: 360 }}>
                  <div className="truncate" style={{ fontWeight: 500 }}>
                    {alert.title}
                  </div>
                  <div className="truncate text-tertiary" style={{ fontSize: 11 }}>
                    {alert.description}
                  </div>
                </td>
                <td>
                  <div className="flex gap-1 wrap" style={{ maxWidth: 220 }}>
                    {alert.technique_ids.slice(0, 3).map((t) => (
                      <TagChip key={t} label={t} />
                    ))}
                    {alert.technique_ids.length > 3 && (
                      <span className="text-tertiary" style={{ fontSize: 11 }}>
                        +{alert.technique_ids.length - 3}
                      </span>
                    )}
                  </div>
                </td>
                <td>
                  <AlertStatusBadge status={alert.status} />
                </td>
                <td className="text-tertiary" style={{ whiteSpace: "nowrap" }}>
                  {formatDateTime(alert.created_at)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
