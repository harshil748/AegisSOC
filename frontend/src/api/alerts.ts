import { api } from "./client";
import type { Alert, AlertListResponse, AlertStatus, Severity } from "../types/domain";

export interface AlertQueryParams {
  severity?: Severity;
  status?: AlertStatus;
  q?: string;
  limit?: number;
  offset?: number;
  sort?: string;
}

export function listAlerts(params: AlertQueryParams = {}, signal?: AbortSignal) {
  return api.get<AlertListResponse>("/api/alerts", { ...params }, signal);
}

export function getAlert(alertId: string, signal?: AbortSignal) {
  return api.get<Alert>(`/api/alerts/${alertId}`, undefined, signal);
}
