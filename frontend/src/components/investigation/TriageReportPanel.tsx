import type { TriageReport } from "../../types/domain";
import { formatDateTime, formatPercent } from "../../utils/format";
import { ConfidenceMeter } from "../common/ConfidenceMeter";
import { EmptyState } from "../common/StateBlocks";
import { AlertTriangleIcon, InfoIcon } from "../icons";

export function TriageReportPanel({ report }: { report: TriageReport | null }) {
  if (!report) {
    return (
      <EmptyState
        icon={<InfoIcon size={26} className="state-icon" />}
        title="No triage report yet"
        detail="The LLM triage agent generates an evidence-grounded summary once enough correlated evidence exists for this case."
      />
    );
  }

  return (
    <div className="flex-col gap-4" style={{ padding: "var(--sp-4)" }}>
      <div className="flex items-center justify-between wrap gap-2">
        <span className="text-tertiary" style={{ fontSize: 11 }}>
          Model <span className="text-mono">{report.model_id}</span> \u00b7 generated{" "}
          {formatDateTime(report.created_at)}
        </span>
        <span className="badge badge-info">Groundedness {formatPercent(report.groundedness_score)}</span>
      </div>

      <section>
        <h3 style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-secondary)", marginBottom: 6 }}>
          Summary
        </h3>
        <p style={{ fontSize: 13, lineHeight: 1.55 }}>{report.summary}</p>
      </section>

      <section>
        <h3 style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-secondary)", marginBottom: 6 }}>
          Likely Objective
        </h3>
        <p style={{ fontSize: 13, lineHeight: 1.55 }}>{report.likely_objective}</p>
      </section>

      {report.attack_mapping.length > 0 && (
        <section>
          <h3 style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-secondary)", marginBottom: 6 }}>
            ATT&amp;CK Mapping
          </h3>
          <div className="flex-col gap-2">
            {report.attack_mapping.map((m, i) => (
              <div
                key={`${m.technique_id}-${i}`}
                className="flex items-start gap-2"
                style={{ fontSize: 12, background: "var(--bg-inset)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: "var(--sp-2) var(--sp-3)" }}
              >
                <span className="tag-chip" style={{ flex: "none" }}>
                  {m.technique_id}
                </span>
                <div>
                  <div style={{ fontWeight: 600 }}>
                    {m.technique_name ?? "\u2014"}
                    {m.tactic && <span className="text-tertiary"> \u00b7 {m.tactic}</span>}
                  </div>
                  {m.rationale && <div className="text-secondary" style={{ marginTop: 2 }}>{m.rationale}</div>}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {report.investigation_queries.length > 0 && (
        <section>
          <h3 style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-secondary)", marginBottom: 6 }}>
            Recommended Investigation Queries
          </h3>
          <ul style={{ margin: 0, paddingLeft: 18, display: "flex", flexDirection: "column", gap: 6 }}>
            {report.investigation_queries.map((q, i) => (
              <li key={i} className="text-mono" style={{ fontSize: 11.5, color: "var(--text-secondary)" }}>
                {q}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h3 style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-secondary)", marginBottom: 6 }}>
          Containment Recommendation
        </h3>
        <p style={{ fontSize: 13, lineHeight: 1.55 }}>{report.containment_recommendation}</p>
      </section>

      <section>
        <h3 style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-secondary)", marginBottom: 6 }}>
          Confidence
        </h3>
        <ConfidenceMeter value={report.groundedness_score} />
        <p className="text-secondary" style={{ fontSize: 12, marginTop: 6, lineHeight: 1.5 }}>
          {report.confidence_explanation}
        </p>
      </section>

      {report.unsupported_claims.length > 0 && (
        <section
          style={{
            background: "var(--sev-medium-bg)",
            border: "1px solid rgba(232,195,74,0.3)",
            borderRadius: "var(--radius-md)",
            padding: "var(--sp-3)",
          }}
        >
          <div className="flex items-center gap-2" style={{ marginBottom: 6 }}>
            <AlertTriangleIcon size={14} style={{ color: "var(--sev-medium)" }} />
            <strong style={{ fontSize: 12 }}>Flagged unsupported claims</strong>
          </div>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: "var(--text-secondary)" }}>
            {report.unsupported_claims.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </section>
      )}

      <div className="text-tertiary" style={{ fontSize: 11 }}>
        Evidence cited: {report.evidence_cited.length} item{report.evidence_cited.length === 1 ? "" : "s"}
      </div>
    </div>
  );
}
