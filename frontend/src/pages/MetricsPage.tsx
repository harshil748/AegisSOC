import { getMetrics } from "../api/metrics";
import { MetricCard } from "../components/metrics/MetricCard";
import { ErrorState, LoadingState } from "../components/common/StateBlocks";
import { RefreshIcon } from "../components/icons";
import { useAsync } from "../hooks/useAsync";
import { formatDateTime, formatNumber, formatPercent, formatUsd } from "../utils/format";

export function MetricsPage() {
  const { data, loading, error, refetch } = useAsync((signal) => getMetrics(signal), []);

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-heading">
          <h1>Metrics</h1>
          <p>Pipeline throughput, detection quality, LLM cost, and response-workflow health.</p>
        </div>
        <div className="page-actions">
          {data && <span className="text-tertiary" style={{ fontSize: 12 }}>as of {formatDateTime(data.generated_at)}</span>}
          <button className="btn btn-sm" onClick={refetch}>
            <RefreshIcon size={13} /> Refresh
          </button>
        </div>
      </div>

      {loading && <LoadingState label="Loading metrics\u2026" />}
      {!loading && error && <ErrorState message={error} onRetry={refetch} />}

      {!loading && !error && data && (
        <div className="flex-col gap-5">
          <section>
            <h2 style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-secondary)", marginBottom: 10 }}>
              Ingestion
            </h2>
            <div className="metrics-grid">
              <MetricCard label="Events / sec" value={formatNumber(data.ingestion.events_per_sec)} />
              <MetricCard label="Events today" value={formatNumber(data.ingestion.events_today)} />
              <MetricCard label="Queue lag" value={`${formatNumber(data.ingestion.queue_lag_ms)} ms`} />
              <MetricCard
                label="DLQ count"
                value={formatNumber(data.ingestion.dlq_count)}
                accent={data.ingestion.dlq_count > 0 ? "var(--status-warning)" : undefined}
              />
            </div>
          </section>

          <section>
            <h2 style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-secondary)", marginBottom: 10 }}>
              Detection &amp; Triage
            </h2>
            <div className="metrics-grid">
              <MetricCard label="Alerts today" value={formatNumber(data.detection.alerts_today)} />
              <MetricCard label="Open alerts" value={formatNumber(data.detection.open_alerts)} accent="var(--sev-high)" />
              <MetricCard label="Precision" value={formatPercent(data.detection.precision)} />
              <MetricCard label="Recall" value={formatPercent(data.detection.recall)} />
              <MetricCard label="Avg. time to triage" value={`${formatNumber(data.detection.avg_time_to_triage_minutes)} min`} />
            </div>
          </section>

          <section>
            <h2 style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-secondary)", marginBottom: 10 }}>
              Cases
            </h2>
            <div className="metrics-grid">
              <MetricCard label="Open cases" value={formatNumber(data.cases.open)} />
              <MetricCard label="Investigating" value={formatNumber(data.cases.investigating)} />
              <MetricCard label="Resolved today" value={formatNumber(data.cases.resolved_today)} accent="var(--status-success)" />
              <MetricCard label="False positive rate" value={formatPercent(data.cases.false_positive_rate)} />
            </div>
          </section>

          <section>
            <h2 style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-secondary)", marginBottom: 10 }}>
              LLM Reasoning
            </h2>
            <div className="metrics-grid">
              <MetricCard label="Avg. latency" value={`${formatNumber(data.llm.avg_latency_ms)} ms`} />
              <MetricCard label="Requests today" value={formatNumber(data.llm.requests_today)} />
              <MetricCard label="Cost today" value={formatUsd(data.llm.cost_today_usd)} />
              <MetricCard label="Avg. groundedness" value={formatPercent(data.llm.groundedness_avg)} />
            </div>
          </section>

          <section>
            <h2 style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-secondary)", marginBottom: 10 }}>
              Response &amp; Approvals
            </h2>
            <div className="metrics-grid">
              <MetricCard
                label="Pending approvals"
                value={formatNumber(data.response.pending_approvals)}
                accent={data.response.pending_approvals > 0 ? "var(--status-warning)" : undefined}
              />
              <MetricCard label="Approved today" value={formatNumber(data.response.approved_today)} accent="var(--status-success)" />
              <MetricCard label="Rejected today" value={formatNumber(data.response.rejected_today)} accent="var(--status-danger)" />
              <MetricCard label="Executed today" value={formatNumber(data.response.executed_today)} />
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
