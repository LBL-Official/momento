type FileRow = {
  table?: string;
  layer?: string;
  path?: string;
  rows?: number;
  bytes?: number;
  exists?: boolean;
  note?: string;
};

type Props = {
  files: Record<string, unknown> | null;
};

export default function PhysicalFiles({ files }: Props) {
  if (!files) return <p className="ju-drive-meta">Loading physical files.</p>;
  const parquet = (files.parquet as FileRow[]) || [];
  const csv = (files.confirm_and_run_csv as FileRow[]) || [];
  return (
    <section>
      <h2>Phase 8 parquet</h2>
      <p className="ju-drive-mono">{String(files.phase8_root || "")}</p>
      <table className="ju-drive-table">
        <thead>
          <tr>
            <th>Table</th>
            <th>Path</th>
            <th>Rows</th>
            <th>Bytes</th>
          </tr>
        </thead>
        <tbody>
          {parquet.map((row, i) => (
            <tr key={`${row.path}-${i}`}>
              <td>{row.table}</td>
              <td className="ju-drive-mono">{row.path}</td>
              <td>{row.rows}</td>
              <td>{row.bytes}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h2>Confirm & Run CSV</h2>
      <p className="ju-drive-meta">Separate physical layer. Not the workbench database.</p>
      {csv.length ? (
        csv.map((row) => (
          <p key={row.path} className="ju-drive-mono">
            {row.path} — {row.note}
          </p>
        ))
      ) : (
        <p>Unavailable</p>
      )}
    </section>
  );
}
