import type { ReactNode } from "react";
import { AlertTriangleIcon, InboxEmptyIcon, RefreshIcon } from "../icons";

export function LoadingState({ label = "Loading\u2026" }: { label?: string }) {
  return (
    <div className="state-block">
      <div className="spinner" />
      <div className="state-detail">{label}</div>
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="state-block">
      <AlertTriangleIcon size={28} className="state-icon" />
      <div className="state-title">Something went wrong</div>
      <div className="state-detail">{message}</div>
      {onRetry && (
        <button className="btn btn-sm" onClick={onRetry} style={{ marginTop: 6 }}>
          <RefreshIcon size={13} /> Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({
  title = "Nothing here yet",
  detail,
  icon,
  action,
}: {
  title?: string;
  detail?: string;
  icon?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="state-block">
      {icon ?? <InboxEmptyIcon size={28} className="state-icon" />}
      <div className="state-title">{title}</div>
      {detail && <div className="state-detail">{detail}</div>}
      {action}
    </div>
  );
}
