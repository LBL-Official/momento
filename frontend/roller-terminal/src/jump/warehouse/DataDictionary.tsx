type DictTable = {
  name: string;
  logical_name?: string;
  kind?: string;
  row_count?: number;
  pit_field?: string | null;
  pit_status?: string | null;
  used_by?: string[];
  columns?: { name: string; type: string; description?: string; pit?: boolean }[];
};

type Props = {
  dictionary: Record<string, unknown> | null;
};

export default function DataDictionary({ dictionary }: Props) {
  if (!dictionary) return <p className="ju-drive-meta">Loading dictionary.</p>;
  const tables = (dictionary.tables as DictTable[]) || [];
  return (
    <section>
      <p className="ju-drive-meta">
        PIT field {String(dictionary.pit_field)} · PBP aligned {String(dictionary.pbp_pit_aligned_to_candles)} ·
        orderbook {String(dictionary.orderbook)} · ticks {String(dictionary.ticks)}
      </p>
      {tables.map((table) => (
        <article key={table.name}>
          <h2>{table.logical_name || table.name}</h2>
          <p className="ju-drive-meta">
            {table.kind} · rows {table.row_count} · PIT {table.pit_status || "UNKNOWN"} · used_by{" "}
            {(table.used_by || []).join(", ") || "none"}
          </p>
          <table className="ju-drive-table">
            <thead>
              <tr>
                <th>Column</th>
                <th>Type</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              {(table.columns || []).map((col) => (
                <tr key={col.name}>
                  <td>{col.name}</td>
                  <td className="ju-drive-mono">{col.type}</td>
                  <td>{col.description || "Unavailable"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>
      ))}
    </section>
  );
}
