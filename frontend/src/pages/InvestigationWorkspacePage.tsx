import { useState } from "react";
import { useParams } from "react-router-dom";
import { getCase, getCaseEvidence, getCaseGraph, getCaseTimeline, getCaseTriage } from "../api/cases";
import { AttackGraph } from "../components/investigation/AttackGraph";
import { CaseTimeline } from "../components/investigation/CaseTimeline";
import { EntityDetailPanel } from "../components/investigation/EntityDetailPanel";
import { EvidencePanel } from "../components/investigation/EvidencePanel";
import { GraphLegend } from "../components/investigation/GraphLegend";
import { TriageReportPanel } from "../components/investigation/TriageReportPanel";
import { CaseStatusBadge, SeverityBadge } from "../components/common/Badges";
import { ErrorState, LoadingState } from "../components/common/StateBlocks";
import { RefreshIcon } from "../components/icons";
import { useAsync } from "../hooks/useAsync";
import type { GraphNode } from "../types/domain";
import { riskScoreToPercent } from "../utils/format";

type TabKey = "timeline" | "evidence" | "triage";

export function InvestigationWorkspacePage() {
  const { caseId = "" } = useParams<{ caseId: string }>();
  const [activeTab, setActiveTab] = useState<TabKey>("triage");
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  const caseQuery = useAsync((signal) => getCase(caseId, signal), [caseId]);
  const graphQuery = useAsync((signal) => getCaseGraph(caseId, signal), [caseId]);
  const timelineQuery = useAsync((signal) => getCaseTimeline(caseId, signal), [caseId]);
  const triageQuery = useAsync((signal) => getCaseTriage(caseId, signal), [caseId]);
  const evidenceQuery = useAsync((signal) => getCaseEvidence(caseId, signal), [caseId]);

  function refetchAll() {
    caseQuery.refetch();
    graphQuery.refetch();
    timelineQuery.refetch();
    triageQuery.refetch();
    evidenceQuery.refetch();
  }

  const theCase = caseQuery.data;

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-heading">
          <h1>Investigation Workspace</h1>
          <p>
            Case <span className="text-mono">{caseId}</span>
          </p>
        </div>
        <div className="page-actions">
          <button className="btn btn-sm" onClick={refetchAll}>
            <RefreshIcon size={13} /> Refresh
          </button>
        </div>
      </div>

      {caseQuery.loading && <LoadingState label="Loading case\u2026" />}
      {!caseQuery.loading && caseQuery.error && (
        <ErrorState message={caseQuery.error} onRetry={caseQuery.refetch} />
      )}

      {theCase && (
        <div className="panel">
          <div className="panel-body investigation-summary">
            <div style={{ minWidth: 200 }}>
              <div style={{ fontWeight: 700, fontSize: 15 }}>{theCase.title}</div>
              <div className="text-tertiary" style={{ fontSize: 11, marginTop: 2 }}>
                Assignee: {theCase.assignee ?? "Unassigned"}
              </div>
            </div>
            <SeverityBadge severity={theCase.severity} />
            <CaseStatusBadge status={theCase.status} />
            <div className="risk-stat">
              <span>Risk score</span>
              <span>{riskScoreToPercent(theCase.risk_score)}</span>
            </div>
            <div className="risk-stat">
              <span>Alerts</span>
              <span>{theCase.alert_ids.length}</span>
            </div>
            <div className="risk-stat">
              <span>Entities</span>
              <span>{theCase.entity_ids.length}</span>
            </div>
            <div className="flex gap-1 wrap" style={{ marginLeft: "auto" }}>
              {theCase.technique_ids.slice(0, 6).map((t) => (
                <span key={t} className="tag-chip">
                  {t}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="investigation-grid">
        <div className="panel graph-pane">
          <div className="panel-header">
            <span className="panel-title">Attack-Path Graph</span>
            {graphQuery.data && <GraphLegend nodes={graphQuery.data.nodes} />}
          </div>
          <div className="panel-body">
            {graphQuery.loading && <LoadingState label="Loading attack-path graph\u2026" />}
            {!graphQuery.loading && graphQuery.error && (
              <ErrorState message={graphQuery.error} onRetry={graphQuery.refetch} />
            )}
            {!graphQuery.loading && !graphQuery.error && graphQuery.data && (
              <>
                <AttackGraph
                  nodes={graphQuery.data.nodes}
                  edges={graphQuery.data.edges}
                  selectedNodeId={selectedNode?.node_id ?? null}
                  onSelectNode={setSelectedNode}
                />
                {selectedNode && (
                  <div className="entity-detail-drawer">
                    <EntityDetailPanel node={selectedNode} onClose={() => setSelectedNode(null)} />
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        <div className="panel side-panel">
          <div className="tab-bar">
            <button className={activeTab === "triage" ? "active" : ""} onClick={() => setActiveTab("triage")}>
              Triage Report
            </button>
            <button className={activeTab === "timeline" ? "active" : ""} onClick={() => setActiveTab("timeline")}>
              Timeline
            </button>
            <button className={activeTab === "evidence" ? "active" : ""} onClick={() => setActiveTab("evidence")}>
              Evidence
            </button>
          </div>
          <div className="tab-panel">
            {activeTab === "triage" && (
              <>
                {triageQuery.loading && <LoadingState label="Generating triage report\u2026" />}
                {!triageQuery.loading && triageQuery.error && (
                  <ErrorState message={triageQuery.error} onRetry={triageQuery.refetch} />
                )}
                {!triageQuery.loading && !triageQuery.error && (
                  <TriageReportPanel report={triageQuery.data} />
                )}
              </>
            )}
            {activeTab === "timeline" && (
              <>
                {timelineQuery.loading && <LoadingState label="Loading timeline\u2026" />}
                {!timelineQuery.loading && timelineQuery.error && (
                  <ErrorState message={timelineQuery.error} onRetry={timelineQuery.refetch} />
                )}
                {!timelineQuery.loading && !timelineQuery.error && (
                  <CaseTimeline events={timelineQuery.data?.items ?? []} />
                )}
              </>
            )}
            {activeTab === "evidence" && (
              <>
                {evidenceQuery.loading && <LoadingState label="Loading evidence\u2026" />}
                {!evidenceQuery.loading && evidenceQuery.error && (
                  <ErrorState message={evidenceQuery.error} onRetry={evidenceQuery.refetch} />
                )}
                {!evidenceQuery.loading && !evidenceQuery.error && (
                  <EvidencePanel items={evidenceQuery.data?.items ?? []} />
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
