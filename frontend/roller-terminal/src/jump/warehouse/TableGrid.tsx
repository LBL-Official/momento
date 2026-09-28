type Props = {
  columns: string[];
  rows: Record<string, unknown>[];
  sort?: string | null;
  order?: string;
  selectedIndex?: number | null;
  onSort: (column: string) => void;
  onSelectRow: (index: number, row: Record<string, unknown>) => void;
};

function cell(value: unknown): string {
  if (value === null || value === undefined) return "NULL";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export default function TableGrid({ columns, rows, sort, order, selectedIndex, onSort, onSelectRow }: Props) {
  return (
    <div className="ju-wh-grid-wrap">
      <table className="ju-drive-table ju-wh-grid">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col}>
                <button type="button" onClick={() => onSort(col)}>
                  {col}
                  {sort === col ? (order === "desc" ? " desc" : " asc") : ""}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr
              key={index}
              className={selectedIndex === index ? "is-selected" : undefined}
              onClick={() => onSelectRow(index, row)}
            >
              {columns.map((col) => (
                <td key={col} className={row[col] == null ? "is-null" : undefined}>
                  {cell(row[col])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
