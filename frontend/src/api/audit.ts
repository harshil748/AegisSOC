import { api } from "./client";
import type { AuditListResponse } from "../types/domain";

export interface AuditQueryParams {
  q?: string;
  actor?: string;
  actor_type?: string;
  resource_type?: string;
  limit?: number;
  offset?: number;
}

export function listAudit(params: AuditQueryParams = {}, signal?: AbortSignal) {
  return api.get<AuditListResponse>("/api/audit", { ...params }, signal);
}
