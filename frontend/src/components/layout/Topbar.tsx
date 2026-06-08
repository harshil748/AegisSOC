import { useState } from "react";
import { useLocation } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { useGatewayStatus } from "../../hooks/useGatewayStatus";
import { ChevronDownIcon, LogOutIcon } from "../icons";

const ROUTE_LABELS: Record<string, string> = {
  alerts: "Alert Queue",
  cases: "Cases",
  investigate: "Investigation Workspace",
  response: "Response / Approvals",
  audit: "Audit Trail",
  replay: "Replay / Demo",
  metrics: "Metrics",
};

function useBreadcrumb(): string {
  const { pathname } = useLocation();
  const segments = pathname.split("/").filter(Boolean);
  const key = segments[0] ?? "alerts";
  return ROUTE_LABELS[key] ?? "AegisSOC";
}

export function Topbar() {
  const { user, logout } = useAuth();
  const gatewayStatus = useGatewayStatus();
  const crumb = useBreadcrumb();
  const [menuOpen, setMenuOpen] = useState(false);

  const initials = (user?.display_name ?? user?.username ?? "?")
    .split(/\s+/)
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <header className="topbar">
      <div className="topbar-title">
        AegisSOC<span className="crumb-sep">/</span>
        <span className="crumb-current">{crumb}</span>
      </div>
      <div className="topbar-right">
        <div className={`env-pill${gatewayStatus === "offline" ? " offline" : ""}`}>
          <span className="dot" />
          Gateway {gatewayStatus === "checking" ? "checking\u2026" : gatewayStatus}
        </div>
        <div style={{ position: "relative" }}>
          <button className="user-menu" onClick={() => setMenuOpen((v) => !v)}>
            <span className="avatar">{initials}</span>
            <div className="user-menu-info">
              <strong>{user?.display_name ?? user?.username}</strong>
              <span>{user?.role}</span>
            </div>
            <ChevronDownIcon size={14} style={{ color: "var(--text-tertiary)" }} />
          </button>
          {menuOpen && (
            <div
              className="panel"
              style={{
                position: "absolute",
                right: 0,
                top: "calc(100% + 6px)",
                width: 180,
                zIndex: 50,
                boxShadow: "var(--shadow-md)",
              }}
              onMouseLeave={() => setMenuOpen(false)}
            >
              <div style={{ padding: "var(--sp-3)" }}>
                <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                  Signed in as
                </div>
                <div style={{ fontWeight: 600, fontSize: 13 }}>{user?.username}</div>
              </div>
              <hr className="divider" />
              <button
                className="btn btn-ghost btn-block"
                style={{ justifyContent: "flex-start", margin: "var(--sp-2)", width: "calc(100% - var(--sp-4))" }}
                onClick={logout}
              >
                <LogOutIcon size={14} /> Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
