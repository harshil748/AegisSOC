import type { DemoScenario } from "../../types/domain";
import { PlayIcon } from "../icons";

export type ScenarioRunState = "idle" | "running" | "done" | "error";

export function ScenarioCard({
  scenario,
  state,
  resultMessage,
  caseId,
  onRun,
  onOpenCase,
}: {
  scenario: DemoScenario;
  state: ScenarioRunState;
  resultMessage?: string;
  caseId?: string | null;
  onRun: () => void;
  onOpenCase?: (caseId: string) => void;
}) {
  return (
    <div className="card flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <div style={{ fontWeight: 600, fontSize: 14 }}>{scenario.name}</div>
        {state === "running" && <span className="badge badge-info">Running\u2026</span>}
        {state === "done" && <span className="badge badge-success">Completed</span>}
        {state === "error" && <span className="badge badge-danger">Failed</span>}
      </div>

      <p style={{ fontSize: 12.5, color: "var(--text-secondary)", margin: 0 }}>{scenario.description}</p>

      <div
        style={{
          fontSize: 11.5,
          background: "var(--bg-inset)",
          border: "1px solid var(--border-subtle)",
          borderRadius: "var(--radius-md)",
          padding: "var(--sp-2) var(--sp-3)",
          color: "var(--text-secondary)",
        }}
      >
        <strong>Expected outcome: </strong>
        {scenario.expected_outcome}
      </div>

      <div className="flex gap-1 wrap">
        {scenario.tags.map((t) => (
          <span key={t} className="tag-chip">
            {t}
          </span>
        ))}
      </div>

      {resultMessage && (
        <div
          className="text-secondary"
          style={{
            fontSize: 12,
            borderLeft: `3px solid ${state === "error" ? "var(--status-danger)" : "var(--status-success)"}`,
            paddingLeft: 10,
          }}
        >
          {resultMessage}
        </div>
      )}

      <div className="flex gap-2">
        <button className="btn btn-primary btn-sm" onClick={onRun} disabled={state === "running"}>
          <PlayIcon size={13} /> {state === "running" ? "Running\u2026" : "Run scenario"}
        </button>
        {caseId && onOpenCase && (
          <button className="btn btn-sm" onClick={() => onOpenCase(caseId)}>
            Open resulting case
          </button>
        )}
      </div>
    </div>
  );
}
