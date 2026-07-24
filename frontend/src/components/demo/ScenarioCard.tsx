import { useState } from "react";
import { Link } from "react-router-dom";
import type { DemoRunResponse, DemoScenario } from "../../types/domain";
import { stagesForScenario } from "./pipelineCopy";
import { PlayIcon, CheckIcon, AlertTriangleIcon } from "../icons";

export type ScenarioRunState =
  | { status: "idle" }
  | { status: "running" }
  | { status: "done"; result: DemoRunResponse }
  | { status: "error"; message: string };

export function ScenarioCard({
  scenario,
  runState,
  onRun,
}: {
  scenario: DemoScenario;
  runState: ScenarioRunState;
  onRun: () => void;
}) {
  const [open, setOpen] = useState(true);
  const stages = stagesForScenario(scenario.scenario_id);
  const busy = runState.status === "running";

  return (
    <article className="panel demo-card">
      <header className="panel-header demo-card-header">
        <div>
          <div className="panel-title">{scenario.title}</div>
          <div className="text-tertiary" style={{ fontSize: 12, marginTop: 4 }}>
            <code className="text-mono">{scenario.scenario_id}</code>
            {scenario.event_count != null && <> · {scenario.event_count} events</>}
          </div>
        </div>
        <button className="btn btn-primary btn-sm" onClick={onRun} disabled={busy}>
          <PlayIcon size={13} />
          {busy ? "Running pipeline\u2026" : "Run end-to-end"}
        </button>
      </header>

      <div className="panel-body demo-card-body">
        <p style={{ fontSize: 13, color: "var(--text-secondary)", margin: 0 }}>
          {scenario.description}
        </p>

        {scenario.expected_outcome && (
          <div className="demo-outcome">
            <strong>Expected outcome:</strong> {scenario.expected_outcome}
          </div>
        )}

        {!!scenario.tags?.length && (
          <div className="flex gap-1 wrap" style={{ marginTop: 10 }}>
            {scenario.tags.map((t) => (
              <span key={t} className="tag-chip">
                {t}
              </span>
            ))}
          </div>
        )}

        <button
          type="button"
          className="btn btn-ghost btn-sm"
          style={{ marginTop: 12, alignSelf: "flex-start" }}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "Hide" : "Show"} pipeline walkthrough
        </button>

        {open && (
          <ol className="demo-pipeline">
            {stages.map((stage) => (
              <li key={stage.id} className="demo-pipeline-step">
                <div className="demo-pipeline-label">{stage.label}</div>
                <div className="demo-pipeline-detail">{stage.detail}</div>
              </li>
            ))}
          </ol>
        )}

        {runState.status === "done" && (
          <div className="demo-run-result success">
            <CheckIcon size={15} />
            <div>
              <div style={{ fontWeight: 600 }}>{runState.result.message ?? "Scenario completed"}</div>
              <div className="text-tertiary" style={{ fontSize: 12, marginTop: 2 }}>
                {runState.result.events_processed != null && (
                  <>Processed {runState.result.events_processed}/{runState.result.events_total ?? "?"} events · </>
                )}
                {runState.result.elapsed_ms != null && <>{runState.result.elapsed_ms} ms · </>}
                {runState.result.case_id ? (
                  <Link to={`/investigate/${runState.result.case_id}`}>Open investigation workspace</Link>
                ) : (
                  <Link to="/cases">Check Cases</Link>
                )}
              </div>
            </div>
          </div>
        )}

        {runState.status === "error" && (
          <div className="demo-run-result error">
            <AlertTriangleIcon size={15} />
            <div>{runState.message}</div>
          </div>
        )}
      </div>
    </article>
  );
}
