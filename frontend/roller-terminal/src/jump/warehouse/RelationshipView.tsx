import type { RelationshipGraph } from "./warehouseApi";
import RelationshipCanvas from "./RelationshipCanvas";

type Props = {
  warehouseId: string;
  graph: RelationshipGraph | null;
  onChange: (graph: RelationshipGraph) => void;
};

export default function RelationshipView({ warehouseId, graph, onChange }: Props) {
  if (!graph) return <p className="ju-drive-meta">Loading relationships.</p>;
  return (
    <section>
      <p className="ju-drive-meta">
        Trusted joins are DECLARED / CANONICAL_MAPPING from GameMarketLink. Name-similar columns stay CANDIDATE.
      </p>
      <RelationshipCanvas warehouseId={warehouseId} graph={graph} onChange={onChange} />
      <h2>Declared</h2>
      <table className="ju-drive-table">
        <thead>
          <tr>
            <th>From</th>
            <th>To</th>
            <th>Cardinality</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {graph.edges.map((edge) => (
            <tr key={edge.id}>
              <td>
                {edge.from_table}.{edge.from_column}
              </td>
              <td>
                {edge.to_table}.{edge.to_column}
              </td>
              <td>{edge.cardinality}</td>
              <td>{edge.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h2>Candidates (not trusted)</h2>
      <table className="ju-drive-table">
        <thead>
          <tr>
            <th>From</th>
            <th>To</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {graph.candidates.map((edge) => (
            <tr key={edge.id}>
              <td>
                {edge.from_table}.{edge.from_column}
              </td>
              <td>
                {edge.to_table}.{edge.to_column}
              </td>
              <td>{edge.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
