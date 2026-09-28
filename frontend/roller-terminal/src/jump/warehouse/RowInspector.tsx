type Props = {
  row: Record<string, unknown> | null;
};

export default function RowInspector({ row }: Props) {
  if (!row) {
    return <p className="ju-drive-meta">Select a row.</p>;
  }
  return (
    <dl>
      {Object.entries(row).map(([key, value]) => (
        <div key={key}>
          <dt>{key}</dt>
          <dd className="ju-drive-mono">{value === null || value === undefined ? "NULL" : String(value)}</dd>
        </div>
      ))}
    </dl>
  );
}
