import { NavLink } from "react-router-dom";
import {
  AlertQueueIcon,
  AuditIcon,
  CaseIcon,
  DemoIcon,
  MetricsIcon,
  ResponseIcon,
  ShieldIcon,
} from "../icons";

interface NavItem {
  to: string;
  label: string;
  icon: (props: { size?: number }) => JSX.Element;
  badgeCount?: number;
}

export function Sidebar({ pendingApprovals }: { pendingApprovals?: number }) {
  const items: NavItem[] = [
    { to: "/alerts", label: "Alert Queue", icon: AlertQueueIcon },
    { to: "/cases", label: "Cases", icon: CaseIcon },
    {
      to: "/response",
      label: "Response",
      icon: ResponseIcon,
      badgeCount: pendingApprovals,
    },
    { to: "/audit", label: "Audit Trail", icon: AuditIcon },
    { to: "/metrics", label: "Metrics", icon: MetricsIcon },
    { to: "/demo", label: "Demo", icon: DemoIcon },
  ];

  return (
    <nav className="sidebar">
      <div className="brand">
        <ShieldIcon className="brand-mark" size={24} />
        <div className="brand-text">
          <strong>AegisSOC</strong>
          <span>Analyst Console</span>
        </div>
      </div>

      <div className="nav-section-label">Workspace</div>
      {items.map(({ to, label, icon: Icon, badgeCount }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
        >
          <Icon size={16} />
          <span>{label}</span>
          {!!badgeCount && <span className="nav-badge">{badgeCount}</span>}
        </NavLink>
      ))}
    </nav>
  );
}
