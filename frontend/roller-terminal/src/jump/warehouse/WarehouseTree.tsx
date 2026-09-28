import type { WarehouseTable } from "./warehouseApi";

type Props = {
  tables: WarehouseTable[];
  active?: string | null;
  onOpen: (name: string) => void;
};

export default function WarehouseTree({ tables, active, onOpen }: Props) {
  return (
    <ul className="ju-wh-tree">
      {tables.map((table) => (
        <li key={table.name}>
          <button
            type="button"
            className={table.name === active ? "is-active" : undefined}
            onClick={() => onOpen(table.name)}
          >
            <span>{table.logical_name || table.name}</span>
            <span className="ju-drive-count">{table.row_count.toLocaleString()}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
