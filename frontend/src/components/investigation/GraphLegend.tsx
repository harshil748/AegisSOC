import { NODE_TYPE_COLORS, NODE_TYPE_ORDER } from "../../utils/graphStyle";
import type { GraphNode } from "../../types/domain";

export function GraphLegend({ nodes }: { nodes: GraphNode[] }) {
  const present = new Set(nodes.map((n) => n.node_type));
  const types = NODE_TYPE_ORDER.filter((t) => present.has(t));

  if (types.length === 0) return null;

  return (
    <div className="flex gap-3 wrap" style={{ padding: "6px 4px", fontSize: 11 }}>
      {types.map((type) => (
        <div key={type} className="flex items-center gap-1">
          <span
            style={{
              width: 9,
              height: 9,
              borderRadius: "50%",
              background: NODE_TYPE_COLORS[type],
              flex: "none",
            }}
          />
          <span className="text-secondary">{type}</span>
        </div>
      ))}
    </div>
  );
}
