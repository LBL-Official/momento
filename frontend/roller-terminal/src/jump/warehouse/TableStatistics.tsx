type Props = {
  stats: Record<string, unknown> | null;
  loading?: boolean;
  onCompute: () => void;
};

export default function TableStatistics({ stats, loading, onCompute }: Props) {
  if (!stats) {
    return <p className="ju-drive-meta">No statistics loaded.</p>;
  }
  const columns = Array.isArray(stats.columns) ? (stats.columns as Record<string, unknown>[]) : [];
  return (
    <section>
      <p className="ju-drive-meta">
        source={String(stats.source || "parquet_footer")} · exact={String(stats.exact)} · sampled={String(stats.sampled)} ·
        rows={String(stats.row_count)} · bytes={String(stats.bytes)}
      </p>
      <button type="button" className="ju-drive-quiet" onClick={onCompute} disabled={loading}>
        {loading ? "Calculating" : "Calculate column null counts"}
      </button>
      {columns.length ? (
        <table className="ju-drive-table">
          <thead>
            <tr>
              <th>Column</th>
              <th>Non-null</th>
              <th>Nulls</th>
              <th>Exact</th>
            </tr>
          </thead>
          <tbody>
            {columns.map((col) => (
              <tr key={String(col.name)}>
                <td>{String(col.name)}</td>
                <td>{String(col.non_null)}</td>
                <td>{String(col.nulls)}</td>
                <td>{String(col.exact)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="ju-drive-meta">{String(stats.note || "Footer metadata only.")}</p>
      )}
    </section>
  );
}
