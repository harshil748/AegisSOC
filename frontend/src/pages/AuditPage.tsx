import { useState } from "react";
import { listAudit } from "../api/audit";
import { EmptyState, ErrorState, LoadingState } from "../components/common/StateBlocks";
import { AuditIcon, ChevronDownIcon, RefreshIcon, SearchIcon } from "../components/icons";
import { useAsync } from "../hooks/useAsync";
import type { AuditEvent } from "../types/domain";
import { formatDateTime } from "../utils/format";

const ACTOR_TYPES = ["user", "system", "llm", "service"];

function actorTypeBadge(type: string) {
  switch (type) {
    case "llm":
      return "badge badge-info";
    case "system":
      return "badge badge-neutral";
    case "service":
      return "badge badge-outline";
    default:
      return "badge badge-success";
  }
}

function AuditRow({ event }: { event: AuditEvent }) {
  const [open, setOpen] = useState(false);
  const detailEntries = Object.entries(event.details ?? {});

  return (
    <>
      <tr className="clickable" onClick={() => setOpen((v) => !v)}>
        <td style={{ width: 22 }}>
          <ChevronDownIcon
            size={13}
            style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform 120ms ease", color: "var(--text-tertiary)" }}
          />
        </td>
        <td className="text-tertiary" style={{ whiteSpace: "nowrap" }}>
          {formatDateTime(event.timestamp)}
        </td>
        <td>
          <span className={actorTypeBadge(event.actor_type)}>{event.actor_type}</span>
        </td>
        <td className="text-mono">{event.actor}</td>
        <td style={{ fontWeight: 500 }}>{event.action}</td>
        <td>
          <span className="tag-chip">
            {event.resource_type}:{event.resource_id}
          </span>
        </td>
        <td className="text-tertiary">{event.evidence_refs.length} ref(s)</td>
      </tr>
      {open && (
        <tr>
          <td colSpan={7} style={{ background: "var(--bg-inset)" }}>
            <div className="flex-col gap-2" style={{ padding: "var(--sp-3) var(--sp-4)" }}>
              {event.prompt_hash && (
                <div style={{ fontSize: 12 }}>
                  <strong className="text-secondary">Prompt hash: </strong>
                  <span className="text-mono">{event.prompt_hash}</span>
                </div>
              )}
              {event.evidence_refs.length > 0 && (
                <div className="flex gap-1 wrap">
                  {event.evidence_refs.map((r) => (
                    <span key={r} className="tag-chip">
                      {r}
                    </span>
                  ))}
                </div>
              )}
              {detailEntries.length > 0 ? (
                <pre
                  className="text-mono"
                  style={{
                    background: "var(--bg-canvas)",
                    border: "1px solid var(--border-subtle)",
                    borderRadius: "var(--radius-md)",
                    padding: "var(--sp-2) var(--sp-3)",
                    fontSize: 11,
                    margin: 0,
                    overflowX: "auto",
                  }}
                >
                  {JSON.stringify(event.details, null, 2)}
                </pre>
              ) : (
                <span className="text-tertiary" style={{ fontSize: 12 }}>No additional detail recorded.</span>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export function AuditPage() {
  const [q, setQ] = useState("");
  const [actorType, setActorType] = useState("");

  const { data, loading, error, refetch } = useAsync(
    (signal) => listAudit({ q: q || undefined, actor_type: actorType || undefined, limit: 300 }, signal),
    [q, actorType],
  );

  const events = data?.items ?? [];

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-heading">
          <h1>Audit Trail</h1>
          <p>Immutable record of every AI recommendation, human override, and approval decision.</p>
        </div>
        <div className="page-actions">
          <button className="btn btn-sm" onClick={refetch}>
            <RefreshIcon size={13} /> Refresh
          </button>
        </div>
      </div>

      <div className="panel">
        <div className="panel-body flex items-center gap-3 wrap">
          <div style={{ position: "relative", flex: "1 1 240px", minWidth: 200 }}>
            <SearchIcon
              size={14}
              style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--text-tertiary)" }}
            />
            <input
              className="input"
              style={{ paddingLeft: 30, width: "100%" }}
              placeholder="Search actor, action, resource\u2026"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
          <select className="select" value={actorType} onChange={(e) => setActorType(e.target.value)}>
            <option value="">All actor types</option>
            {ACTOR_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          {data && (
            <span className="text-tertiary" style={{ fontSize: 12, marginLeft: "auto" }}>
              {data.total} event{data.total === 1 ? "" : "s"}
            </span>
          )}
        </div>
      </div>

      {loading && <LoadingState label="Loading audit events\u2026" />}
      {!loading && error && <ErrorState message={error} onRetry={refetch} />}
      {!loading && !error && events.length === 0 && (
        <EmptyState
          icon={<AuditIcon size={28} className="state-icon" />}
          title="No audit events found"
          detail="Audit events are written when a Demo scenario runs (triage + recommendations) and when you approve/reject actions. Run a Demo, then refresh."
        />
      )}
      {!loading && !error && events.length > 0 && (
        <div className="data-table-wrap panel">
          <table className="data-table">
            <thead>
              <tr>
                <th></th>
                <th>Timestamp</th>
                <th>Actor Type</th>
                <th>Actor</th>
                <th>Action</th>
                <th>Resource</th>
                <th>Evidence</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <AuditRow key={e.audit_id} event={e} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
