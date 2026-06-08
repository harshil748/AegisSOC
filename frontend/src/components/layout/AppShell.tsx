import { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import { listActions } from "../../api/actions";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

export function AppShell() {
  const [pendingApprovals, setPendingApprovals] = useState<number | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    async function poll() {
      try {
        const actions = await listActions({ status: "pending" });
        if (!cancelled) setPendingApprovals(actions.length);
      } catch {
        if (!cancelled) setPendingApprovals(undefined);
      }
    }
    poll();
    const id = setInterval(poll, 30000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="app-shell">
      <Sidebar pendingApprovals={pendingApprovals} />
      <Topbar />
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
