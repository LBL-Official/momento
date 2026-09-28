import { useCallback, useEffect, useState } from "react";
import CompanionTau from "./CompanionTau";
import { UniverseError, fetchNbaPath77, fetchUniverse77 } from "./api";
import { text, width } from "./text";
import type { ClockSlice, NbaPath, Partition, ScatterPoint, TradePath, Universe } from "./types";

function Row({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="row">
      <dt>{label}</dt>
      <dd>{text(value)}</dd>
    </div>
  );
}

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

function PartitionCard({ row }: { row: Partition }) {
  const paths = row.paths || [];
  const midPaths = row.mid_paths || [];
  return (
    <article>
      <h2>
        {row.sport_label} · {row.slice_label}
      </h2>
      <dl>
        <Row label="universe N" value={row.n} />
        <Row label="terminal W / L" value={`${row.W} / ${row.L}`} />
        <Row label="terminal W/N" value={`${text(row.terminal.p_display)} · ${text(row.terminal.p_pct_display)}`} />
        <Row
          label="77/40 S"
          value={`${text(row.trade_77_40?.S_display)} · ${text(row.trade_77_40?.S_pct_display)}`}
        />
        <Row label="77/40 EV" value={text(row.trade_77_40?.ev_per_trade_display)} />
        <Row label="77/55 N" value={row.trade_77_55?.n} />
        <Row
          label="77/55 S"
          value={`${text(row.trade_77_55?.S_display)} · ${text(row.trade_77_55?.S_pct_display)}`}
        />
        <Row label="77/55 EV" value={text(row.trade_77_55?.ev_per_trade_display)} />
        <Row label="excluded 83-first" value={row.trade_77_55?.excluded_hit_83} />
        <Row label="ledger rank" value={(row.ledger_rank || []).join(" > ")} />
        <Row label="mid rank" value={(row.mid_ledger_rank || []).join(" > ")} />
      </dl>
      <div className="path-list">
        {paths.map((path) => (
          <PathRow key={path.key} path={path} />
        ))}
      </div>
      {midPaths.length ? (
        <div className="path-list">
          {midPaths.map((path) => (
            <PathRow key={path.key} path={path} />
          ))}
        </div>
      ) : null}
      <div className="cells">
        <div className="cell">
          <span>W ∩ ¬T40</span>
          {row.cells.W_and_not_T40}
        </div>
        <div className="cell">
          <span>W ∩ T40</span>
          {row.cells.W_and_T40}
        </div>
        <div className="cell">
          <span>L ∩ ¬T40</span>
          {row.cells.L_and_not_T40}
        </div>
        <div className="cell">
          <span>L ∩ T40</span>
          {row.cells.L_and_T40}
        </div>
      </div>
    </article>
  );
}

function ClockPanel({ clock }: { clock: ClockSlice }) {
  return (
    <article>
      <h2>
        {clock.slice_label} bets · T40 clock · {clock.n_t40} stops
      </h2>
      <div className="chart">
        {clock.bins
          .filter((bin) => bin.n > 0)
          .map((bin) => (
            <div key={bin.label} className="chart-row">
              <span>{bin.label}</span>
              <div className="track">
                <div className="fill fill-clock" style={{ width: width(bin.bar_pct) }} />
              </div>
              <span>
                {text(bin.n_display)} · {text(bin.pct_display)}
              </span>
            </div>
          ))}
      </div>
      <dl>
        {(clock.mean_remaining || []).map((row) => (
          <Row key={row.period} label={`${row.period} mean remaining`} value={`${row.clock_display} · n=${row.n}`} />
        ))}
      </dl>
    </article>
  );
}

function Scatter({ path }: { path: NbaPath }) {
  const points = path.scatter.points;
  return (
    <article className="wide">
      <h2>NBA point differential · survive vs T40</h2>
      <p className="muted">
        {text(path.scatter.x_label)} vs {text(path.scatter.y_label)}. {path.n_survive} survive, {path.n_t40} T40.
        Not k-means. Survivors have no T40-time score.
      </p>
      <svg className="scatter" viewBox="0 0 100 100" role="img" aria-label="NBA survive versus T40 scatter">
        <rect x="0" y="0" width="100" height="100" className="scatter-bg" />
        {points.map((point: ScatterPoint) => (
          <circle
            key={point.ticker}
            cx={point.plot_x_pct}
            cy={point.plot_y_pct}
            r={point.t40 ? 0.7 : 0.55}
            className={point.t40 ? "dot-t40" : "dot-survive"}
          >
            <title>
              {point.ticker} {point.cohort} entry {point.entry_margin} final {point.final_margin}
            </title>
          </circle>
        ))}
      </svg>
      <div className="legend">
        <span className="swatch survive" /> survive
        <span className="swatch t40" /> T40
      </div>
      <div className="stat-row second">
        <div className="stat">
          <dt>survive entry</dt>
          <dd>
            {text(path.margins.survive.entry.mean_display)}
            <span className="sub">
              n={path.margins.survive.n} min {path.margins.survive.entry.min} max {path.margins.survive.entry.max}
            </span>
          </dd>
        </div>
        <div className="stat">
          <dt>survive final</dt>
          <dd>
            {text(path.margins.survive.final.mean_display)}
            <span className="sub">
              min {path.margins.survive.final.min} max {path.margins.survive.final.max}
            </span>
          </dd>
        </div>
        <div className="stat">
          <dt>T40 entry</dt>
          <dd>
            {text(path.margins.t40.entry.mean_display)}
            <span className="sub">
              n={path.margins.t40.n} min {path.margins.t40.entry.min} max {path.margins.t40.entry.max}
            </span>
          </dd>
        </div>
        <div className="stat">
          <dt>T40-time / final</dt>
          <dd>
            {text(path.margins.t40.t40_time.mean_display)}
            <span className="sub">final {text(path.margins.t40.final.mean_display)}</span>
          </dd>
        </div>
      </div>
    </article>
  );
}

export default function Texas77() {
  const [universe, setUniverse] = useState<Universe | null>(null);
  const [nbaPath, setNbaPath] = useState<NbaPath | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pathError, setPathError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const next = await fetchUniverse77();
      if (next.status !== "OBSERVED") {
        setUniverse(null);
        setNbaPath(null);
        setError(next.message || next.status || "LOCK_MISMATCH");
        return;
      }
      setUniverse(next);
      setError(null);
    } catch (err) {
      setUniverse(null);
      setNbaPath(null);
      if (err instanceof UniverseError) {
        setError(err.message);
        return;
      }
      setError(err instanceof Error ? err.message : String(err));
      return;
    }
    try {
      const path = await fetchNbaPath77();
      if (path.status !== "OBSERVED") {
        setNbaPath(null);
        setPathError(path.message || path.status || "LOCK_MISMATCH");
        return;
      }
      setNbaPath(path);
      setPathError(null);
    } catch (err) {
      setNbaPath(null);
      if (err instanceof UniverseError) {
        setPathError(err.message);
        return;
      }
      setPathError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const observed = universe !== null && universe.status === "OBSERVED";
  const pool = observed ? universe.pool : null;
  const paths = pool?.paths || [];
  const midPaths = pool?.mid_paths || [];
  const topPath = (pool?.ledger_rank || [])[0];
  const topMidPath = (pool?.mid_ledger_rank || [])[0];

  return (
    <>
      <div className="page-meta">
        <span className={`pill ${observed ? "is-ok" : "is-bad"}`}>
          {observed ? "OBSERVED" : error ? "LOCK_MISMATCH" : "UNREAD"}
        </span>
        <button type="button" onClick={() => void load()}>
          refresh
        </button>
      </div>

      {error ? <p className="banner is-bad">{error}</p> : null}
      {pathError ? <p className="banner is-bad">{pathError}</p> : null}

      {pool ? (
        <section className="grid">
          <article className="wide">
            <h2>Universe · FIRST77 derived four, not asked-six</h2>
            <div className="stat-row">
              <div className="stat">
                <dt>Games N</dt>
                <dd>
                  {pool.n}
                  <span className="sub">{text(universe?.unit)}</span>
                </dd>
              </div>
              <div className="stat">
                <dt>Terminal W/N</dt>
                <dd>
                  {text(pool.terminal.p_display)}
                  <span className="sub">{text(pool.terminal.p_pct_display)}</span>
                </dd>
              </div>
              <div className="stat">
                <dt>77/40 S</dt>
                <dd>
                  {text(pool.trade_77_40?.S_display)}
                  <span className="sub">{text(pool.trade_77_40?.S_pct_display)}</span>
                </dd>
              </div>
              <div className="stat">
                <dt>Verify</dt>
                <dd className="is-ok">
                  {text(universe?.verification?.status)}
                  <span className="sub">{text(universe?.complement?.identity)}</span>
                </dd>
              </div>
            </div>
            <div className="stat-row seven second">
              {paths.map((path) => (
                <div key={path.key} className={`stat ev-chip${path.key === topPath ? " is-top" : ""}`}>
                  <dt>{path.key} EV</dt>
                  <dd>
                    {text(path.ev_per_trade_display)}
                    <span className="sub">
                      {text(path.S_display)} · book {text(path.book_cents)}¢ · n={path.n}
                    </span>
                  </dd>
                </div>
              ))}
            </div>
            <p className="muted">
              Ledger rank {text((pool.ledger_rank || []).join(" > "))}. Candle-path theoretical EV, not a fill.
              77/55 is the entry&lt;83 book.
            </p>
          </article>
          {midPaths.length ? (
            <article className="wide">
              <h2>77/33 · 77/37 · 77/43 · 77/47 · full 933 book</h2>
              <div className="stat-row">
                {midPaths.map((path) => (
                  <div key={path.key} className={`stat ev-chip${path.key === topMidPath ? " is-top" : ""}`}>
                    <dt>{path.key} EV</dt>
                    <dd>
                      {text(path.ev_per_trade_display)}
                      <span className="sub">
                        {text(path.S_display)} · book {text(path.book_cents)}¢ · n={path.n}
                      </span>
                    </dd>
                  </div>
                ))}
              </div>
              <p className="muted">
                Mid rank {text((pool.mid_ledger_rank || []).join(" > "))}. Candle-path theoretical EV, not a fill.
                Same derived four N as 77/25–77/50. Not the 55 cap book.
              </p>
            </article>
          ) : null}
        </section>
      ) : null}

      {observed ? <CompanionTau /> : null}

      {observed ? (
        <section className="grid four">
          {universe.partitions.map((row) => (
            <PartitionCard key={row.partition_id} row={row} />
          ))}
        </section>
      ) : null}

      {observed ? (
        <section className="grid">
          <article className="wide">
            <h2>Charts · API bars only</h2>
            <div className="chart">
              {universe.partitions.map((row) => (
                <div key={`${row.partition_id}-n`} className="chart-row">
                  <span>
                    {row.sport_label} {row.slice_label} N
                  </span>
                  <div className="track">
                    <div className="fill fill-n" style={{ width: width(row.n_bar_pct) }} />
                  </div>
                  <span>{text(row.n_share_display)}</span>
                </div>
              ))}
              {paths.map((path) => (
                <div key={`pool-${path.key}`} className="chart-row">
                  <span>{path.key} EV</span>
                  <div className="track">
                    <div className="fill fill-ev" style={{ width: width(path.ev_bar_pct) }} />
                  </div>
                  <span>{text(path.ev_per_trade_display)}</span>
                </div>
              ))}
              {universe.partitions.map((row) => (
                <div key={`${row.partition_id}-s`} className="chart-row">
                  <span>{row.slice_label} 77/40 S</span>
                  <div className="track">
                    <div className="fill fill-s" style={{ width: width(row.trade_77_40?.S_bar_pct) }} />
                  </div>
                  <span>{text(row.trade_77_40?.S_pct_display)}</span>
                </div>
              ))}
            </div>
          </article>

          <article>
            <h2>Variables · locked</h2>
            <dl>
              <Row label="rule" value={universe.variables?.rule} />
              <Row label="K" value={universe.variables?.K} />
              <Row label="entry" value={universe.variables?.entry_cents} />
              <Row label="stop" value={universe.variables?.stop_cents} />
              <Row label="77/55 stop" value={universe.variables?.stop_55_cents} />
              <Row label="entry cap" value={universe.variables?.entry_cap_cents} />
              <Row label="gain" value={universe.variables?.gain_cents} />
              <Row label="path stops" value={(universe.variables?.path_stops || []).join(", ")} />
              <Row label="mid stops" value={(universe.variables?.mid_stops || []).join(", ")} />
              <Row label="slices" value={(universe.variables?.slices || []).join(", ")} />
              <Row label="locked" value={universe.variables?.locked} />
              <Row label="recompute" value={universe.variables?.recompute} />
            </dl>
            <p className="muted">{text(universe.variables?.note)}</p>
          </article>

          <article>
            <h2>Not this desk</h2>
            <ul className="muted">
              {(universe.disclaimers || []).map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </article>
        </section>
      ) : null}

      {nbaPath ? (
        <section className="grid">
          {nbaPath.clocks.map((clock) => (
            <ClockPanel key={clock.slice} clock={clock} />
          ))}
          <Scatter path={nbaPath} />
          <article className="wide">
            <h2>Alignment</h2>
            <p className="muted">{text(nbaPath.alignment?.model)}</p>
            <p className="muted">{text(nbaPath.alignment?.note)}</p>
          </article>
        </section>
      ) : null}
    </>
  );
}
