import { api } from "./client";
import type {
  Case,
  CaseGraphResponse,
  CaseListResponse,
  CaseStatus,
  CaseTimelineResponse,
  EvidenceItem,
  Severity,
  TriageReport,
} from "../types/domain";

export interface CaseQueryParams {
  status?: CaseStatus;
  severity?: Severity;
  q?: string;
  limit?: number;
  offset?: number;
}

export function listCases(params: CaseQueryParams = {}, signal?: AbortSignal) {
  return api.get<CaseListResponse>("/api/cases", { ...params }, signal);
}

export function getCase(caseId: string, signal?: AbortSignal) {
  return api.get<Case>(`/api/cases/${caseId}`, undefined, signal);
}

export function getCaseGraph(caseId: string, signal?: AbortSignal) {
  return api.get<CaseGraphResponse>(`/api/cases/${caseId}/graph`, undefined, signal);
}

export function getCaseTimeline(caseId: string, signal?: AbortSignal) {
  return api.get<CaseTimelineResponse>(`/api/cases/${caseId}/timeline`, undefined, signal);
}

export function getCaseTriage(caseId: string, signal?: AbortSignal) {
  return api.get<TriageReport>(`/api/cases/${caseId}/triage`, undefined, signal);
}

export function getCaseEvidence(caseId: string, signal?: AbortSignal) {
  return api.get<{ items: EvidenceItem[] }>(`/api/cases/${caseId}/evidence`, undefined, signal);
}
