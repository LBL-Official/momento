import type { PathWindowRow } from "../types/superasi";

type Props = {
  ticker: string;
  rows: PathWindowRow[];
};

export default function PathWindowStrip({ ticker, rows }: Props) {
  const byOff = new Map(rows.filter((r) => r.ticker === ticker).map((r) => [r.offset, r]));
  const offsets = [-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5];
  return (
    <div className="sa-path-strip">
      <p className="muted small">
        {ticker} · offset 0 = FIRST THROUGH-CLOSE / PATH EVENT · missing = UNAVAILABLE
      </p>
      <ol>
        {offsets.map((off) => {
          const row = byOff.get(off);
          const bid = row?.yes_bid_close;
          const label = off === 0 ? "PATH EVENT" : `${off > 0 ? "+" : ""}${off}`;
          return (
            <li key={off}>
              <span className="v2-kicker">{label}</span>
              <span className="evidence">{bid != null ? `${bid}¢` : "UNAVAILABLE"}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
