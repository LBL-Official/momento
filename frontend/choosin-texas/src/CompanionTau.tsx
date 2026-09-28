import { useCallback, useEffect, useState } from "react";
import { UniverseError, fetchUniverse81, fetchUniverse83 } from "./api";
import { text } from "./text";
import type { Partition, TradePath, Universe } from "./types";

function PathRow({ path }: { path: TradePath }) {
  return (
    <div className="path-line">
      <span>{path.key}</span>
      <span>
        {text(path.S_display)} · {text(path.S_pct_display)}
      </span>
      <span>{text(path.ev_per_trade_display)}</span>
    </div>
  );
}

function TauBlock({ body }: { body: Universe }) {
  const pool = body.pool;
  const paths = pool?.paths || [];
  const top = (pool?.ledger_rank || [])[0];
  return (
    <div className="tau-block">
      <h3>
        {body.rule} · derived four N={pool?.n} · gain {text(body.gain_cents)}¢
      </h3>
      <p className="muted">{text(pool?.note)}</p>
      <div className="path-list">
        {paths.map((path) => (
          <div key={path.key} className={path.key === top ? "path-line is-top" : "path-line"}>
            <span>{path.key}</span>
            <span>
              {text(path.S_display)} · {text(path.S_pct_display)}
            </span>
            <span>{text(path.ev_per_trade_display)}</span>
          </div>
        ))}
      </div>
      <div className="grid four">
        {(body.partitions || []).map((row: Partition) => (
          <article key={row.partition_id}>
            <h3>
              {row.sport_label} · {row.slice_label} · N={row.n}
            </h3>
            <div className="path-list">
              {(row.paths || []).map((path) => (
                <PathRow key={path.key} path={path} />
              ))}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

export default function CompanionTau() {
  const [book81, set81] = useState<Universe | null>(null);
  const [book83, set83] = useState<Universe | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const notes: string[] = [];
    try {
      const next81 = await fetchUniverse81();
      if (next81.status === "OBSERVED") {
        set81(next81);
      } else {
        set81(null);
        notes.push(next81.message || next81.status || "DATA_REQUIRED");
      }
    } catch (err) {
      set81(null);
      notes.push(err instanceof UniverseError ? err.message : err instanceof Error ? err.message : String(err));
    }
    try {
      const next83 = await fetchUniverse83();
      if (next83.status === "OBSERVED") {
        set83(next83);
      } else {
        set83(null);
        notes.push(next83.message || next83.status || "DATA_REQUIRED");
      }
    } catch (err) {
      set83(null);
      notes.push(err instanceof UniverseError ? err.message : err instanceof Error ? err.message : String(err));
    }
    setError(notes[0] || null);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="grid">
      <article className="wide">
        <h2>FIRST81 + FIRST83 · entry thresholds · derived four</h2>
        <p className="muted">
          These are separate τ books, not stops on 75/77/80. 81/55 is entry&lt;87. 83/55 is entry&lt;89.
          Candle-path theoretical. Not a fill. Not live FIRST01 / 80/81/83/89.
        </p>
        {error ? <p className="banner is-bad">{error}</p> : null}
        {book81 ? <TauBlock body={book81} /> : null}
        {book83 ? <TauBlock body={book83} /> : null}
      </article>
    </section>
  );
}
