import { useState } from "react";
import type { EvidenceItem } from "../../types/domain";
import { formatDateTime } from "../../utils/format";
import { EmptyState } from "../common/StateBlocks";
import { ChevronDownIcon, InfoIcon } from "../icons";

const KIND_LABELS: Record<string, string> = {
  event: "Raw Event",
  node: "Graph Node",
  edge: "Graph Edge",
  detection: "Detection",
  intel: "Threat Intel",
};

function EvidenceRow({ item }: { item: EvidenceItem }) {
  const [open, setOpen] = useState(false);
  const payloadEntries = Object.entries(item.payload ?? {});

  return (
    <div className="card" style={{ padding: "var(--sp-3)" }}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2"
        style={{ width: "100%", background: "none", border: "none", cursor: "pointer", textAlign: "left", padding: 0 }}
      >
        <span className="badge badge-outline">{KIND_LABELS[item.kind] ?? item.kind}</span>
        <span className="flex-1 truncate" style={{ fontSize: 12.5 }}>
          {item.summary}
        </span>
        {item.timestamp && (
          <span className="text-tertiary" style={{ fontSize: 11, whiteSpace: "nowrap" }}>
            {formatDateTime(item.timestamp)}
          </span>
        )}
        <ChevronDownIcon
          size={14}
          style={{
            color: "var(--text-tertiary)",
            transform: open ? "rotate(180deg)" : "none",
            transition: "transform 120ms ease",
            flex: "none",
          }}
        />
      </button>
      {open && (
        <div style={{ marginTop: "var(--sp-3)" }}>
          <div className="kv-list" style={{ marginBottom: payloadEntries.length ? "var(--sp-2)" : 0 }}>
            <dt>Evidence ID</dt>
            <dd className="text-mono">{item.evidence_id}</dd>
            <dt>Source</dt>
            <dd>{item.source ?? "\u2014"}</dd>
          </div>
          {payloadEntries.length > 0 && (
            <pre
              className="text-mono"
              style={{
                background: "var(--bg-inset)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                padding: "var(--sp-2) var(--sp-3)",
                fontSize: 11,
                overflowX: "auto",
                margin: 0,
              }}
            >
              {JSON.stringify(item.payload, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

export function EvidencePanel({ items }: { items: EvidenceItem[] }) {
  if (items.length === 0) {
    return (
      <EmptyState
        icon={<InfoIcon size={26} className="state-icon" />}
        title="No evidence recorded"
        detail="Evidence items with provenance appear here once detections and enrichment cite grounded source events."
      />
    );
  }

  return (
    <div className="flex-col gap-2" style={{ padding: "var(--sp-3) var(--sp-4)" }}>
      {items.map((item) => (
        <EvidenceRow key={item.evidence_id} item={item} />
      ))}
    </div>
  );
}
