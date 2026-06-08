import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { DEMO_SCENARIOS, runScenario } from "../api/demo";
import { ApiError } from "../api/client";
import { ScenarioCard, type ScenarioRunState } from "../components/demo/ScenarioCard";
import { useToast } from "../context/ToastContext";

interface ScenarioRun {
  state: ScenarioRunState;
  message?: string;
  caseId?: string | null;
}

export function ReplayPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const [runs, setRuns] = useState<Record<string, ScenarioRun>>({});

  async function handleRun(scenarioId: string, name: string) {
    setRuns((prev) => ({ ...prev, [scenarioId]: { state: "running" } }));
    try {
      const res = await runScenario(scenarioId);
      setRuns((prev) => ({
        ...prev,
        [scenarioId]: { state: "done", message: res.message, caseId: res.case_id },
      }));
      toast.push({
        kind: "success",
        title: `${name} \u2014 scenario replayed`,
        message: res.message,
      });
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Failed to run scenario.";
      setRuns((prev) => ({ ...prev, [scenarioId]: { state: "error", message } }));
      toast.push({ kind: "error", title: "Scenario run failed", message });
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-heading">
          <h1>Replay / Demo</h1>
          <p>
            Replay seeded telemetry for the three canonical demo scenarios to validate detection, triage, and
            response end-to-end.
          </p>
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
          gap: "var(--sp-4)",
        }}
      >
        {DEMO_SCENARIOS.map((scenario) => {
          const run = runs[scenario.scenario_id];
          return (
            <ScenarioCard
              key={scenario.scenario_id}
              scenario={scenario}
              state={run?.state ?? "idle"}
              resultMessage={run?.message}
              caseId={run?.caseId}
              onRun={() => handleRun(scenario.scenario_id, scenario.name)}
              onOpenCase={(caseId) => navigate(`/investigate/${caseId}`)}
            />
          );
        })}
      </div>

      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">About Replay Mode</span>
        </div>
        <div className="panel-body" style={{ fontSize: 12.5, color: "var(--text-secondary)", lineHeight: 1.6 }}>
          Replay mode re-emits recorded/synthetic telemetry through the same ingestion \u2192 normalization \u2192
          enrichment \u2192 detection \u2192 graph pipeline used in production, so triage output and response
          recommendations reflect real system behavior. Use it for onboarding new analysts, regression-testing
          detections, and live demos.
        </div>
      </div>
    </div>
  );
}
