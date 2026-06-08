import type { AlertStatus, Severity } from "../../types/domain";
import { SearchIcon } from "../icons";

export interface AlertFilterState {
  severity?: Severity;
  status?: AlertStatus;
  q: string;
}

const SEVERITIES: Severity[] = ["critical", "high", "medium", "low", "informational"];
const STATUSES: AlertStatus[] = ["open", "investigating", "escalated", "closed", "false_positive"];

export function AlertFilters({
  value,
  onChange,
  resultCount,
}: {
  value: AlertFilterState;
  onChange: (next: AlertFilterState) => void;
  resultCount?: number;
}) {
  return (
    <div className="panel">
      <div className="panel-body flex items-center gap-3 wrap">
        <div style={{ position: "relative", flex: "1 1 220px", minWidth: 200 }}>
          <SearchIcon
            size={14}
            style={{
              position: "absolute",
              left: 10,
              top: "50%",
              transform: "translateY(-50%)",
              color: "var(--text-tertiary)",
            }}
          />
          <input
            className="input"
            style={{ paddingLeft: 30, width: "100%" }}
            placeholder="Search title, technique, entity\u2026"
            value={value.q}
            onChange={(e) => onChange({ ...value, q: e.target.value })}
          />
        </div>

        <select
          className="select"
          value={value.severity ?? ""}
          onChange={(e) =>
            onChange({ ...value, severity: (e.target.value || undefined) as Severity | undefined })
          }
        >
          <option value="">All severities</option>
          {SEVERITIES.map((s) => (
            <option key={s} value={s}>
              {s[0].toUpperCase() + s.slice(1)}
            </option>
          ))}
        </select>

        <select
          className="select"
          value={value.status ?? ""}
          onChange={(e) =>
            onChange({ ...value, status: (e.target.value || undefined) as AlertStatus | undefined })
          }
        >
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s.replace(/_/g, " ")}
            </option>
          ))}
        </select>

        {(value.severity || value.status || value.q) && (
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => onChange({ severity: undefined, status: undefined, q: "" })}
          >
            Clear filters
          </button>
        )}

        {resultCount !== undefined && (
          <span className="text-tertiary" style={{ fontSize: 12, marginLeft: "auto" }}>
            {resultCount} result{resultCount === 1 ? "" : "s"}
          </span>
        )}
      </div>
    </div>
  );
}
