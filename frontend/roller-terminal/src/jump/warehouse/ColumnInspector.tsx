import type { WarehouseColumn } from "./warehouseApi";

type Props = {
  column: WarehouseColumn | null;
};

export default function ColumnInspector({ column }: Props) {
  if (!column) {
    return <p className="ju-drive-meta">Select a column.</p>;
  }
  return (
    <dl>
      <dt>Name</dt>
      <dd className="ju-drive-mono">{column.name}</dd>
      <dt>Type</dt>
      <dd className="ju-drive-mono">{column.type}</dd>
      <dt>Nullable</dt>
      <dd>{column.nullable ? "yes" : "no"}</dd>
      <dt>PIT</dt>
      <dd>{column.pit ? "yes" : "no"}</dd>
      <dt>Description</dt>
      <dd>{column.description || "Unavailable"}</dd>
    </dl>
  );
}
