import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { CheckIcon, XIcon, AlertTriangleIcon, InfoIcon } from "../components/icons";

export type ToastKind = "success" | "error" | "warning" | "info";

export interface ToastInput {
  kind?: ToastKind;
  title: string;
  message?: string;
  durationMs?: number;
}

interface ToastRecord extends ToastInput {
  id: number;
}

interface ToastContextValue {
  toasts: ToastRecord[];
  push: (toast: ToastInput) => void;
  dismiss: (id: number) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

function iconFor(kind: ToastKind) {
  switch (kind) {
    case "success":
      return <CheckIcon size={15} style={{ color: "var(--status-success)" }} />;
    case "error":
      return <XIcon size={15} style={{ color: "var(--status-danger)" }} />;
    case "warning":
      return <AlertTriangleIcon size={15} style={{ color: "var(--status-warning)" }} />;
    default:
      return <InfoIcon size={15} style={{ color: "var(--status-info)" }} />;
  }
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastRecord[]>([]);
  const idRef = useRef(0);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = useCallback(
    (toast: ToastInput) => {
      const id = ++idRef.current;
      const record: ToastRecord = { kind: "info", durationMs: 5000, ...toast, id };
      setToasts((prev) => [...prev, record]);
      if (record.durationMs && record.durationMs > 0) {
        setTimeout(() => dismiss(id), record.durationMs);
      }
    },
    [dismiss],
  );

  const value = useMemo(() => ({ toasts, push, dismiss }), [toasts, push, dismiss]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-stack" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.kind}`}>
            <span style={{ marginTop: 1 }}>{iconFor(t.kind ?? "info")}</span>
            <div>
              <div className="toast-title">{t.title}</div>
              {t.message && <div className="toast-message">{t.message}</div>}
            </div>
            <button className="toast-close" onClick={() => dismiss(t.id)} aria-label="Dismiss">
              <XIcon size={13} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
