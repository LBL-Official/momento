import type { WarehouseColumn } from "./warehouseApi";

type Props = {
  columns: WarehouseColumn[];
  onSelect?: (name: string) => void;
  active?: string | null;
};

export default function TableStructure({ columns, onSelect, active }: Props) {
  return (
    <table className="ju-drive-table">
      <thead>
        <tr>
          <th>Column</th>
          <th>Type</th>
          <th>Nullable</th>
          <th>PIT</th>
          <th>Description</th>
        </tr>
      </thead>
      <tbody>
        {columns.map((col) => (
          <tr
            key={col.name}
            className={active === col.name ? "is-selected" : undefined}
            onClick={() => onSelect?.(col.name)}
          >
            <td className="ju-drive-name">{col.name}</td>
            <td className="ju-drive-mono">{col.type}</td>
            <td>{col.nullable ? "yes" : "no"}</td>
            <td>{col.pit ? "available_at" : ""}</td>
            <td>{col.description || "Unavailable"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
