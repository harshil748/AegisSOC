import type { DemoPipelineStage } from "../../types/domain";

/** Shared pipeline order shown on every demo card. */
export const PIPELINE_STAGE_ORDER = [
  "ingest",
  "normalize",
  "enrich",
  "graph",
  "detect",
  "case",
  "triage",
  "recommend",
] as const;

export type PipelineStageId = (typeof PIPELINE_STAGE_ORDER)[number];

const STAGE_LABELS: Record<PipelineStageId, string> = {
  ingest: "1. Ingest",
  normalize: "2. Normalize",
  enrich: "3. Enrich",
  graph: "4. Graph",
  detect: "5. Detect",
  case: "6. Case",
  triage: "7. Triage (LLM)",
  recommend: "8. Recommend → Approve",
};

/** Per-scenario explanations of what happens from ingestion to response. */
export const SCENARIO_PIPELINE: Record<string, Record<PipelineStageId, string>> = {
  phishing_ransomware_chain: {
    ingest:
      "Raw envelopes arrive from email, Sysmon/EDR, DNS, and network sources (spoofed invoice, Word macro, PowerShell, C2). Ingestion dedupes and publishes to aegis.raw.events (or DLQ if malformed).",
    normalize:
      "Each source-specific payload is mapped into a CanonicalEvent with UTC time, host, user, process, and file fields so later stages share one schema.",
    enrich:
      "Events get asset criticality (finance workstation), identity resolution (Elena Martinez), MITRE ATT&CK tags (T1566 phishing, T1059.001 PowerShell), and intel hits on the spoofed domain/C2 IP.",
    graph:
      "Neo4j (or in-memory graph) upserts Email→User→Host→Process→File→IP→Domain edges so the attack path is queryable as a neighborhood.",
    detect:
      "Sigma-like rules + correlation + graph features fire on macro spawn, encoded PowerShell, C2, and lateral movement. Ensemble risk scores climb into high/critical.",
    case:
      "Related alerts are clustered into one auto-case with a shared timeline instead of flooding the analyst with separate tickets.",
    triage:
      "LLM writes an evidence-grounded report (citations only — it does not invent detections) describing likely objective and ATT&CK narrative.",
    recommend:
      "Policy suggests containment (e.g. isolate host / block infra). Disruptive actions stay pending until a human approves in the Response panel.",
  },
  benign_admin_false_positive: {
    ingest:
      "Scheduled-task and PowerShell telemetry from the SCCM service account is ingested like any other event — same RawEnvelope path, no special casing.",
    normalize:
      "Base64 PowerShell and scheduled-task fields become CanonicalEvents with admin host/user context preserved.",
    enrich:
      "Asset is tagged as IT admin; change-management / SCCM context and lower criticality reduce blast-radius weight versus a finance laptop.",
    graph:
      "Process and host nodes are written, but there is no phishing email or known-bad C2 edge — the graph stays locally administrative.",
    detect:
      "A PowerShell-looking rule may still match superficially, but correlation + calibrated ensemble keep the score low (authorized pattern).",
    case:
      "A low-severity case may open for review so analysts can confirm benign intent without treating it as ransomware.",
    triage:
      "LLM summary explains why this looks like change-managed patch compliance, citing the admin account and scheduled-task evidence.",
    recommend:
      "Policy leans toward ignore / monitor — no disruptive isolate/block is pushed as the default outcome.",
  },
  repeat_attacker_infra: {
    ingest:
      "New beaconing / DNS / process events are ingested pointing at infrastructure seen in a prior confirmed incident.",
    normalize:
      "IP, domain, and host fields land in CanonicalEvent form identical to any live connector feed.",
    enrich:
      "Threat-intel enrichment flags the reused domain/IP; ATT&CK network C2 tags attach; prior incident tags raise context.",
    graph:
      "Graph memory is the point: edges reconnect today's host activity to historically observed malicious infra nodes.",
    detect:
      "Rules fire on reconnection, but graph_score / intel_score dominate the ensemble — history amplifies confidence.",
    case:
      "Case title/timeline highlight reuse of previously observed malicious infrastructure for faster prioritization.",
    triage:
      "Report cites both current events and graph-linked prior incident evidence so the analyst sees the repeat pattern.",
    recommend:
      "Elevated risk drives a stronger response recommendation (block infra / contain host) still gated by human approval.",
  },
};

export function stagesForScenario(scenarioId: string): DemoPipelineStage[] {
  const details = SCENARIO_PIPELINE[scenarioId];
  return PIPELINE_STAGE_ORDER.map((id) => ({
    id,
    label: STAGE_LABELS[id],
    detail:
      details?.[id] ??
      "This stage runs in the shared AegisSOC pipeline (ingest → … → recommend).",
  }));
}
