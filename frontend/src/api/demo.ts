import { api } from "./client";
import type { DemoRunResponse, DemoScenario } from "../types/domain";

/**
 * Static catalog of the three seeded demo scenarios described in the product
 * spec (prompt.md). The backend is the source of truth when reachable; this
 * list is used as the display fallback so the Replay page renders
 * immediately, but running a scenario always calls the real endpoint.
 */
export const DEMO_SCENARIOS: DemoScenario[] = [
  {
    scenario_id: "phishing_to_ransomware",
    name: "Phishing \u2192 Ransomware",
    description:
      "Phishing email delivers a macro-laced document that spawns PowerShell, harvests credentials, moves laterally, then detonates ransomware on a file server.",
    expected_outcome:
      "Escalates to a critical case with a full attack-path graph and a quarantine/isolate recommendation queued for approval.",
    tags: ["phishing", "credential-access", "lateral-movement", "ransomware"],
  },
  {
    scenario_id: "benign_admin_powershell",
    name: "Benign Admin PowerShell",
    description:
      "A scheduled task runs an administrator PowerShell maintenance script that superficially resembles living-off-the-land attacker behavior.",
    expected_outcome:
      "Low risk score, triage report explains benign rationale, no disruptive action recommended \u2014 demonstrates false-positive suppression.",
    tags: ["false-positive", "powershell", "scheduled-task"],
  },
  {
    scenario_id: "repeat_attacker_infra",
    name: "Repeat Attacker Infrastructure",
    description:
      "New alert touches IP/domain infrastructure previously observed in a prior confirmed incident, demonstrating graph memory across cases.",
    expected_outcome:
      "Case links to historical incident via shared entities, risk score boosted by intel/graph history, high analyst confidence.",
    tags: ["threat-intel", "graph-memory", "repeat-offender"],
  },
];

export function runScenario(scenarioId: string) {
  return api.post<DemoRunResponse>("/api/demo/run-scenario", { scenario_id: scenarioId });
}
