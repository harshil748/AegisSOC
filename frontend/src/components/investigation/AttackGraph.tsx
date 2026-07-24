import cytoscape, { type Core, type ElementDefinition } from "cytoscape";
// @ts-expect-error - no bundled types for cytoscape-dagre
import dagre from "cytoscape-dagre";
import { useEffect, useRef } from "react";
import type { GraphEdge, GraphNode } from "../../types/domain";
import { edgeColor, nodeColor } from "../../utils/graphStyle";
import { PlayIcon } from "../icons";

let dagreRegistered = false;
try {
  if (!dagreRegistered) {
    cytoscape.use(dagre);
    dagreRegistered = true;
  }
} catch {
  // already registered (hot reload) - ignore
}

interface AttackGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNodeId?: string | null;
  onSelectNode: (node: GraphNode | null) => void;
}

function buildElements(nodes: GraphNode[], edges: GraphEdge[]): ElementDefinition[] {
  const nodeEls: ElementDefinition[] = nodes.map((n) => ({
    data: {
      id: n.node_id,
      label: n.display_name || n.properties?.name || n.node_id,
      type: n.node_type,
      color: nodeColor(n.node_type),
      confidence: n.confidence,
    },
  }));
  const nodeIds = new Set(nodes.map((n) => n.node_id));
  const edgeEls: ElementDefinition[] = edges
    .filter((e) => nodeIds.has(e.src_id) && nodeIds.has(e.dst_id))
    .map((e) => ({
      data: {
        id: e.edge_id,
        source: e.src_id,
        target: e.dst_id,
        label: e.edge_type.replace(/_/g, " "),
        color: edgeColor(e.edge_type),
      },
    }));
  return [...nodeEls, ...edgeEls];
}

export function AttackGraph({ nodes, edges, selectedNodeId, onSelectNode }: AttackGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const cy = cytoscape({
      container: containerRef.current,
      elements: buildElements(nodes, edges),
      style: [
        {
          selector: "node",
          style: {
            "background-color": "data(color)",
            label: "data(label)",
            color: "#f2f2f0",
            "font-size": 10,
            "text-valign": "bottom",
            "text-margin-y": 6,
            width: 30,
            height: 30,
            "border-width": 2,
            "border-color": "#050505",
            "text-wrap": "ellipsis",
            "text-max-width": "90px",
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-width": 3,
            "border-color": "#ff6a00",
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.6,
            "line-color": "data(color)",
            "target-arrow-color": "data(color)",
            "target-arrow-shape": "triangle",
            "arrow-scale": 0.9,
            "curve-style": "bezier",
            label: "data(label)",
            "font-size": 8,
            color: "#a8a8a3",
            "text-background-color": "#050505",
            "text-background-opacity": 0.85,
            "text-background-padding": "2px",
          },
        },
        {
          selector: "edge:selected",
          style: {
            width: 2.6,
          },
        },
      ],
      layout: {
        name: "dagre",
        // @ts-expect-error dagre-specific options not in core types
        rankDir: "LR",
        nodeSep: 36,
        rankSep: 90,
        animate: false,
      },
      minZoom: 0.2,
      maxZoom: 3,
      wheelSensitivity: 0.25,
    });

    cy.on("tap", "node", (evt) => {
      const id = evt.target.id();
      const node = nodes.find((n) => n.node_id === id) ?? null;
      onSelectNode(node);
    });
    cy.on("tap", (evt) => {
      if (evt.target === cy) onSelectNode(null);
    });

    cyRef.current = cy;
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes, edges]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.nodes().unselect();
    if (selectedNodeId) {
      cy.getElementById(selectedNodeId).select();
    }
  }, [selectedNodeId]);

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      <div ref={containerRef} style={{ width: "100%", height: "100%" }} />
      {nodes.length === 0 && (
        <div
          className="state-block"
          style={{ position: "absolute", inset: 0, background: "var(--bg-panel)" }}
        >
          <PlayIcon size={24} className="state-icon" />
          <div className="state-title">No graph data</div>
          <div className="state-detail">
            This case has no entity-relationship graph yet. Graph edges appear after enrichment
            and graph-builder process related entities.
          </div>
        </div>
      )}
      <div className="flex gap-1" style={{ position: "absolute", top: 10, right: 10 }}>
        <button className="btn btn-icon btn-sm" title="Zoom in" onClick={() => cyRef.current?.zoom(cyRef.current.zoom() * 1.2)}>
          +
        </button>
        <button className="btn btn-icon btn-sm" title="Zoom out" onClick={() => cyRef.current?.zoom(cyRef.current.zoom() / 1.2)}>
          \u2212
        </button>
        <button className="btn btn-sm" title="Fit to view" onClick={() => cyRef.current?.fit(undefined, 40)}>
          Fit
        </button>
      </div>
    </div>
  );
}
