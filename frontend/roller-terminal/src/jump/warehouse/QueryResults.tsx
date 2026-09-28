import TableGrid from "./TableGrid";

type Props = {
  columns: string[];
  rows: Record<string, unknown>[];
  error?: string | null;
};

export default function QueryResults({ columns, rows, error }: Props) {
  if (error) return <p className="ju-drive-error">{error}</p>;
  if (!columns.length) return <p className="ju-drive-meta">No query results.</p>;
  return (
    <TableGrid
      columns={columns}
      rows={rows}
      onSort={() => undefined}
      onSelectRow={() => undefined}
    />
  );
}
