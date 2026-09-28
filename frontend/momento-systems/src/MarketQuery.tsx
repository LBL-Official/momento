import { useEffect, useState } from "react";
import { fetchConnection, runWarehouseQuery } from "./api";
import type { ConnectionPayload, WarehouseQueryResult } from "./types";

const DEFAULT_SQL = "SELECT sport, count(*) AS n FROM games GROUP BY 1";

function cell(value: unknown): string {
  if (value == null) return "UNAVAILABLE";
  return String(value);
}

export default function MarketQuery() {
  const [sport, setSport] = useState<"nba" | "ncaab">("nba");
  const [sql, setSql] = useState(DEFAULT_SQL);
  const [connection, setConnection] = useState<ConnectionPayload | null>(null);
  const [result, setResult] = useState<WarehouseQueryResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchConnection()
      .then((body) => {
        if (!cancelled) setConnection(body);
      })
      .catch((exc: Error) => {
        if (!cancelled) setError(exc.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    setResult(null);
    setError(null);
    setRunning(true);
    runWarehouseQuery(sport, sql, 100)
      .then((body) => {
        setResult(body);
        setRunning(false);
      })
      .catch((exc: Error) => {
        setError(exc.message);
        setRunning(false);
      });
    // Auto-run the sport probe on mount and sport change. Manual Run uses current SQL.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sport]);

  function run() {
    setError(null);
    setRunning(true);
    runWarehouseQuery(sport, sql, 100)
      .then((body) => {
        setResult(body);
        setRunning(false);
      })
      .catch((exc: Error) => {
        setError(exc.message);
        setResult(null);
        setRunning(false);
      });
  }

  const nba = connection?.markets.nba;
  const ncaab = connection?.markets.ncaab;

  return (
    <article className="wide">
      <h2>NBA / NCAAB QUERY</h2>
      <p className="muted">
        Jump parquet desks. Confirm &amp; Run still reads CSV. Missing is UNAVAILABLE, never $0.
      </p>
      <div className="page-meta">
        <span className={`pill ${nba?.query === "OK" ? "is-ok" : "is-idle"}`}>
          NBA {nba?.query || "UNKNOWN"}
          {nba?.n != null ? ` n=${nba.n}` : ""}
        </span>
        <span className={`pill ${ncaab?.query === "OK" ? "is-ok" : "is-idle"}`}>
          NCAAB {ncaab?.query || "UNKNOWN"}
          {ncaab?.n != null ? ` n=${ncaab.n}` : ""}
        </span>
        <span className="pill">
          combined {connection?.research_query.combined.available?.includes("combined_league_union") ? "union" : "UNKNOWN"}
        </span>
      </div>
      <div className="page-meta">
        <button type="button" className={sport === "nba" ? "is-on" : ""} onClick={() => setSport("nba")}>
          NBA
        </button>
        <button type="button" className={sport === "ncaab" ? "is-on" : ""} onClick={() => setSport("ncaab")}>
          NCAAB
        </button>
        <button type="button" onClick={run} disabled={running}>
          {running ? "Running" : "Run"}
        </button>
      </div>
      <textarea className="query-sql" value={sql} onChange={(event) => setSql(event.target.value)} rows={4} />
      {error ? <p className="banner is-bad">{error}</p> : null}
      {result ? (
        <div className="md-table">
          <table className="data-table">
            <thead>
              <tr>
                {result.columns.map((col) => (
                  <th key={col}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.rows.map((row, index) => (
                <tr key={index}>
                  {result.columns.map((col) => (
                    <td key={col}>{cell(row[col])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted">
            {sport} returned {result.returned}. read_only {String(result.read_only)}.
          </p>
        </div>
      ) : null}
    </article>
  );
}
