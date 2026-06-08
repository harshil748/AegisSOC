import { Fragment } from "react";
import type { GraphNode } from "../../types/domain";
import { formatDateTime } from "../../utils/format";
import { nodeColor } from "../../utils/graphStyle";
import { ConfidenceMeter } from "../common/ConfidenceMeter";
import { XIcon } from "../icons";

export function EntityDetailPanel({
  node,
  onClose,
}: {
  node: GraphNode | null;
  onClose: () => void;
}) {
  if (!node) {
    return (
      <div className="state-block" style={{ padding: "var(--sp-5)" }}>
        <div className="state-detail">Select a node in the graph to inspect entity details.</div>
      </div>
    );
  }

  const properties = Object.entries(node.properties ?? {});

  return (
    <div className="flex-col gap-3" style={{ padding: "var(--sp-4)" }}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            style={{ width: 10, height: 10, borderRadius: "50%", background: nodeColor(node.node_type) }}
          />
          <span className="badge badge-outline">{node.node_type}</span>
        </div>
        <button className="btn btn-icon btn-sm btn-ghost" onClick={onClose} aria-label="Close">
          <XIcon size={14} />
        </button>
      </div>

      <div style={{ fontSize: 13, fontWeight: 600, wordBreak: "break-word" }}>
        {node.display_name || (node.properties?.name as string) || node.node_id}
      </div>

      <ConfidenceMeter value={node.confidence} label="Confidence" />

      <dl className="kv-list">
        <dt>Node ID</dt>
        <dd className="text-mono">{node.node_id}</dd>
        <dt>First seen</dt>
        <dd>{formatDateTime(node.first_seen)}</dd>
        <dt>Last seen</dt>
        <dd>{formatDateTime(node.last_seen)}</dd>
        <dt>Occurrences</dt>
        <dd>{node.count}</dd>
        <dt>Sources</dt>
        <dd>{node.sources.length ? node.sources.join(", ") : "\u2014"}</dd>
      </dl>

      {node.labels.length > 0 && (
        <div className="flex gap-1 wrap">
          {node.labels.map((l) => (
            <span key={l} className="tag-chip">
              {l}
            </span>
          ))}
        </div>
      )}

      {properties.length > 0 && (
        <>
          <hr className="divider" />
          <div className="panel-title" style={{ padding: 0 }}>
            Properties
          </div>
          <dl className="kv-list">
            {properties.map(([key, val]) => (
              <Fragment key={key}>
                <dt>{key}</dt>
                <dd className="text-mono">
                  {typeof val === "object" ? JSON.stringify(val) : String(val)}
                </dd>
              </Fragment>
            ))}
          </dl>
        </>
      )}
    </div>
  );
}
