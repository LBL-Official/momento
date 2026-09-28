type Props = {
  sport: "MLB" | "WNBA";
  onHome: () => void;
};

export default function ExecutionDesk({ sport, onHome }: Props) {
  const mlb = sport === "MLB";
  return (
    <main style={{ fontFamily: "Menlo, monospace", padding: 24, background: "#111", color: "#eee", minHeight: "100vh" }}>
      <button type="button" onClick={onHome}>Bracket</button>
      <h1>{sport} Algorithmic Execution</h1>
      <p>LIVE EXECUTION = FALSE</p>
      {mlb ? (
        <dl>
          <dt>bot</dt><dd>mlb-001</dd>
          <dt>owner</dt><dd>vital</dd>
          <dt>runtime</dt><dd>momento-live.service</dd>
          <dt>strategy</dt><dd>strategies/mlb</dd>
          <dt>api</dt><dd>/vital/bots/mlb-001</dd>
          <dt>orders</dt><dd>UNAVAILABLE</dd>
          <dt>fills</dt><dd>UNAVAILABLE</dd>
        </dl>
      ) : (
        <dl>
          <dt>bot</dt><dd>UNAVAILABLE</dd>
          <dt>runtime</dt><dd>UNAVAILABLE</dd>
          <dt>orders</dt><dd>UNAVAILABLE</dd>
          <dt>fills</dt><dd>UNAVAILABLE</dd>
          <dt>reason</dt><dd>no wnba-* bot under research/vital/bots/</dd>
        </dl>
      )}
      <button type="button" disabled>start</button>
      <button type="button" disabled>stop</button>
      <button type="button" disabled>arm</button>
      <p>These controls stay disabled. up does not arm trading and does not start momento-live.service.</p>
    </main>
  );
}
