import type { ReactNode } from "react";

export function MetricCard({
  label,
  value,
  sublabel,
  accent,
  icon,
}: {
  label: string;
  value: string;
  sublabel?: string;
  accent?: string;
  icon?: ReactNode;
}) {
  return (
    <div className="card flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-tertiary" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em" }}>
          {label}
        </span>
        {icon && <span style={{ color: accent ?? "var(--accent-400)" }}>{icon}</span>}
      </div>
      <div className="text-mono" style={{ fontSize: 24, fontWeight: 700, color: accent ?? "var(--text-primary)" }}>
        {value}
      </div>
      {sublabel && <div className="text-tertiary" style={{ fontSize: 11.5 }}>{sublabel}</div>}
    </div>
  );
}
