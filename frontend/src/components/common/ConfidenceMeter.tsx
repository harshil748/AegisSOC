export function ConfidenceMeter({
  value,
  label,
  color,
}: {
  value: number;
  label?: string;
  color?: string;
}) {
  const pct = Math.max(0, Math.min(100, Math.round((value > 1 ? value / 100 : value) * 100)));
  return (
    <div className="flex-col gap-1">
      {label && (
        <div className="flex items-center justify-between" style={{ fontSize: 11 }}>
          <span className="text-secondary">{label}</span>
          <span className="text-mono">{pct}%</span>
        </div>
      )}
      <div className="progress-track">
        <div
          className="progress-fill"
          style={{ width: `${pct}%`, background: color ?? "var(--accent-500)" }}
        />
      </div>
    </div>
  );
}
