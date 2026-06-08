import { useEffect, useState } from "react";
import { API_BASE } from "../api/client";

export type GatewayStatus = "online" | "offline" | "checking";

/**
 * Lightweight reachability probe for the frontend-gateway. Any HTTP
 * response (even 404/401) means the gateway process is reachable; a
 * network-level failure means it is not.
 */
export function useGatewayStatus(intervalMs = 20000): GatewayStatus {
  const [status, setStatus] = useState<GatewayStatus>("checking");

  useEffect(() => {
    let cancelled = false;

    async function probe() {
      try {
        await fetch(`${API_BASE}/health`, { method: "GET" });
        if (!cancelled) setStatus("online");
      } catch {
        if (!cancelled) setStatus("offline");
      }
    }

    probe();
    const id = setInterval(probe, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [intervalMs]);

  return status;
}
