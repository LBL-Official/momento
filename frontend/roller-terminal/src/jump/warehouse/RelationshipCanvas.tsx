import { useEffect, useState } from "react";
import type { RelationshipGraph } from "./warehouseApi";
import { saveRelationshipLayout } from "./warehouseApi";

type Props = {
  warehouseId: string;
  graph: RelationshipGraph;
  onChange: (graph: RelationshipGraph) => void;
};

const BOX_W = 140;
const BOX_H = 44;

export default function RelationshipCanvas({ warehouseId, graph, onChange }: Props) {
  const [drag, setDrag] = useState<{ id: string; dx: number; dy: number } | null>(null);
  const nodes = graph.nodes;
  const width = Math.max(720, ...nodes.map((n) => n.x + BOX_W + 24));
  const height = Math.max(420, ...nodes.map((n) => n.y + BOX_H + 24));

  useEffect(() => {
    if (!drag) return;
    const current = drag;
    function move(event: MouseEvent) {
      onChange({
        ...graph,
        nodes: graph.nodes.map((node) =>
          node.id === current.id
            ? { ...node, x: Math.max(8, event.clientX - current.dx), y: Math.max(8, event.clientY - current.dy) }
            : node
        ),
      });
    }
    function up() {
      const layout: Record<string, { x: number; y: number }> = {};
      graph.nodes.forEach((node) => {
        layout[node.id] = { x: node.x, y: node.y };
      });
      saveRelationshipLayout(warehouseId, layout).then(onChange).catch(() => undefined);
      setDrag(null);
    }
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
    return () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    };
  }, [drag, graph, onChange, warehouseId]);

  return (
    <div className="ju-wh-canvas" style={{ width, height }}>
      <svg width={width} height={height}>
        {graph.edges.map((edge) => {
          const from = nodes.find((n) => n.id === edge.from_table);
          const to = nodes.find((n) => n.id === edge.to_table);
          if (!from || !to) return null;
          return (
            <line
              key={edge.id}
              x1={from.x + BOX_W / 2}
              y1={from.y + BOX_H}
              x2={to.x + BOX_W / 2}
              y2={to.y}
              stroke="currentColor"
            />
          );
        })}
      </svg>
      {nodes.map((node) => (
        <button
          key={node.id}
          type="button"
          className="ju-wh-box"
          style={{ left: node.x, top: node.y, width: BOX_W, height: BOX_H }}
          onMouseDown={(event) => {
            const rect = (event.currentTarget.parentElement as HTMLElement).getBoundingClientRect();
            setDrag({ id: node.id, dx: event.clientX - rect.left - node.x, dy: event.clientY - rect.top - node.y });
          }}
        >
          {node.label}
        </button>
      ))}
    </div>
  );
}
