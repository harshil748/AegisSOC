import { api } from "./client";
import type { DemoRunResponse, DemoScenario } from "../types/domain";

/** Catalog of the three seeded end-to-end demo scenarios. */
export const DEMO_SCENARIOS: DemoScenario[] = [
  {
    scenario_id: "phishing_ransomware_chain",
    title: "Phishing → Ransomware Chain",
    description:
      "A finance analyst receives a spoofed invoice email with a macro-enabled Word document. Opening it launches PowerShell, C2 beaconing, credential access, lateral movement, and ransomware staging.",
    expected_outcome:
      "Multiple correlated alerts, a high-severity case, attack-path graph across email→host→process→IP, grounded triage, and a disruptive containment recommendation pending approval.",
    event_count: 18,
    tags: ["phishing", "ransomware", "lateral-movement"],
  },
  {
    scenario_id: "benign_admin_false_positive",
    title: "Benign Admin False Positive",
    description:
      "A change-managed SCCM patch task runs Base64-encoded PowerShell on an IT admin workstation. It looks suspicious but is authorized maintenance.",
    expected_outcome:
      "Low risk score, triage explains the benign rationale, and no disruptive action is recommended — demonstrating false-positive suppression.",
    event_count: 9,
    tags: ["false-positive", "powershell", "admin"],
  },
  {
    scenario_id: "repeat_attacker_infra",
    title: "Repeat Attacker Infrastructure",
    description:
      "A new alert touches IP/domain infrastructure previously observed in a confirmed incident, showing how graph memory links current activity to past compromise.",
    expected_outcome:
      "Elevated graph/intel score, case linked to known-bad infrastructure, and investigation workspace highlighting historical edges.",
    event_count: 11,
    tags: ["graph-memory", "infra-reuse", "intel"],
  },
];

export function runScenario(scenarioId: string) {
  return api.post<DemoRunResponse>("/api/demo/run-scenario", { scenario_id: scenarioId });
}
