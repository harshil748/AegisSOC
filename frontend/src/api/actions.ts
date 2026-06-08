import { api } from "./client";
import type { ActionRecommendation, ApprovalDecision, ApprovalRequest } from "../types/domain";

export function listActions(params: { case_id?: string; status?: string } = {}, signal?: AbortSignal) {
  return api.get<ActionRecommendation[]>("/api/actions", { ...params }, signal);
}

export function submitApproval(payload: ApprovalRequest) {
  return api.post<ApprovalDecision>("/api/approvals", payload);
}
