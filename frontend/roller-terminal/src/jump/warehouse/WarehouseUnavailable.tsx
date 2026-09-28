type Props = {
  message: string;
  sourceUri?: string | null;
};

export default function WarehouseUnavailable({ message, sourceUri }: Props) {
  return (
    <section className="ju-wh-unavailable">
      <h1>WAREHOUSE_UNAVAILABLE</h1>
      <p>{message}</p>
      {sourceUri ? <p className="ju-drive-mono">{sourceUri}</p> : null}
      <p className="ju-drive-meta">Jump does not invent tables when the Phase 8 desk is missing.</p>
    </section>
  );
}
