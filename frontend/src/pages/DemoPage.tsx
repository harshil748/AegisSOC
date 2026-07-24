import { useState } from "react";
import { DEMO_SCENARIOS, runScenario } from "../api/demo";
import { ScenarioCard, type ScenarioRunState } from "../components/demo/ScenarioCard";
import { PIPELINE_STAGE_ORDER } from "../components/demo/pipelineCopy";
import { useToast } from "../context/ToastContext";
import { PlayIcon } from "../components/icons";

export function DemoPage() {
  const { push } = useToast();
  const [runs, setRuns] = useState<Record<string, ScenarioRunState>>({});

  async function handleRun(scenarioId: string, name: string) {
    setRuns((prev) => ({ ...prev, [scenarioId]: { status: "running" } }));
    try {
      const result = await runScenario(scenarioId);
      setRuns((prev) => ({ ...prev, [scenarioId]: { status: "done", result } }));
      push({
        kind: "success",
        title: `${name} — pipeline finished`,
        message: result.case_id
          ? `Case ${result.case_id.slice(0, 8)}… ready in investigation.`
          : result.message ?? "Check Alert Queue and Cases.",
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Scenario failed.";
      setRuns((prev) => ({ ...prev, [scenarioId]: { status: "error", message } }));
      push({ kind: "error", title: "Demo run failed", message });
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-heading">
          <h1>Demo</h1>
          <p>
            Three guided cases that walk the full AegisSOC pipeline — from data ingestion through
            normalization, enrichment, graph, detection, case clustering, LLM triage, and human-approved response.
          </p>
        </div>
      </div>

      <section className="panel" style={{ marginBottom: 16 }}>
        <div className="panel-header">
          <span className="panel-title">
            <PlayIcon size={14} style={{ marginRight: 6, verticalAlign: -2 }} />
            How the system works
          </span>
        </div>
        <div className="panel-body">
          <p className="text-secondary" style={{ fontSize: 13, margin: "0 0 12px" }}>
            Every demo below executes the same stages in order. Detection stays deterministic (rules +
            graph + scoring); the LLM only summarizes evidence after a case exists.
          </p>
          <div className="demo-stage-strip">
            {PIPELINE_STAGE_ORDER.map((id, i) => (
              <div key={id} className="demo-stage-chip">
                <span className="demo-stage-num">{i + 1}</span>
                <span>{id}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="demo-grid">
        {DEMO_SCENARIOS.map((scenario) => (
          <ScenarioCard
            key={scenario.scenario_id}
            scenario={scenario}
            runState={runs[scenario.scenario_id] ?? { status: "idle" }}
            onRun={() => handleRun(scenario.scenario_id, scenario.title)}
          />
        ))}
      </div>
    </div>
  );
}
