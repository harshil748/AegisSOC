import { api } from "./client";
import type { MetricsSnapshot } from "../types/domain";

export function getMetrics(signal?: AbortSignal) {
  return api.get<MetricsSnapshot>("/api/metrics", undefined, signal);
}
