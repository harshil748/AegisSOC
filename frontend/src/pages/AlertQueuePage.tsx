import { useMemo, useState } from "react";
import { listAlerts } from "../api/alerts";
import { AlertFilters, type AlertFilterState } from "../components/alerts/AlertFilters";
import { AlertTable, type AlertSortKey } from "../components/alerts/AlertTable";
import { EmptyState, ErrorState, LoadingState } from "../components/common/StateBlocks";
import { RefreshIcon, AlertQueueIcon } from "../components/icons";
import { useAsync } from "../hooks/useAsync";
import { SEVERITY_ORDER } from "../types/domain";

export function AlertQueuePage() {
  const [filters, setFilters] = useState<AlertFilterState>({ q: "" });
  const [sortKey, setSortKey] = useState<AlertSortKey>("risk");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const { data, loading, error, refetch } = useAsync(
    (signal) =>
      listAlerts(
        {
          severity: filters.severity,
          status: filters.status,
          q: filters.q || undefined,
          limit: 200,
        },
        signal,
      ),
    [filters.severity, filters.status, filters.q],
  );

  const sortedAlerts = useMemo(() => {
    const items = data?.items ?? [];
    const sorted = [...items].sort((a, b) => {
      if (sortKey === "risk") {
        const ra = a.risk.calibrated_score || a.risk.ensemble_score;
        const rb = b.risk.calibrated_score || b.risk.ensemble_score;
        return rb - ra;
      }
      if (sortKey === "severity") {
        return SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity);
      }
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });
    return sortDir === "asc" ? sorted.reverse() : sorted;
  }, [data, sortKey, sortDir]);

  function handleSort(key: AlertSortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-heading">
          <h1>Alert Queue</h1>
          <p>Prioritized alerts ranked by ensemble risk score. Click a row to open the investigation workspace.</p>
        </div>
        <div className="page-actions">
          <button className="btn btn-sm" onClick={refetch}>
            <RefreshIcon size={13} /> Refresh
          </button>
        </div>
      </div>

      <AlertFilters value={filters} onChange={setFilters} resultCount={data?.total} />

      {loading && <LoadingState label="Loading alert queue\u2026" />}
      {!loading && error && <ErrorState message={error} onRetry={refetch} />}
      {!loading && !error && sortedAlerts.length === 0 && (
        <EmptyState
          icon={<AlertQueueIcon size={28} className="state-icon" />}
          title="No alerts match these filters"
          detail="Try clearing filters, or run a demo scenario from the Replay page to generate sample alerts."
        />
      )}
      {!loading && !error && sortedAlerts.length > 0 && (
        <AlertTable alerts={sortedAlerts} sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
      )}
    </div>
  );
}
