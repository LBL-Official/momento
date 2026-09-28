import { useCallback, useEffect, useState } from "react";
import { UniverseError, fetchFirst78 } from "./api";
import { text, width } from "./text";

type Path = {
  key: string;
  n: number;
  S_display?: string | null;
  S_pct_display?: string | null;
  S_bar_pct?: number;
  ev_per_trade_display?: string | null;
  book_cents?: number;
  ev_bar_pct?: number;
};

type Cells = { W_and_not_T67: number; W_and_T67: number; L_and_not_T67: number; L_and_T67: number };

type Partition = {
  partition_id: string;
  sport_label: string;
  slice_label: string;
  n: number;
  W: number;
  L: number;
  terminal: { p_display?: string | null; p_pct_display?: string | null };
  trade?: Path;
  paths: Path[];
  mid_paths: Path[];
  comparisons: Path[];
  ledger_rank: string[];
  mid_ledger_rank: string[];
  cells: Cells;
  cap_55_excluded: number;
  n_bar_pct?: number;
  n_share_display?: string | null;
};

type Companion = {
  rule: string;
  gain_cents: number;
  n: number;
  note?: string;
  paths: Path[];
  ledger_rank: string[];
  partitions: Array<{ partition_id: string; sport_label: string; slice_label: string; n: number; paths: Path[] }>;
};

type ClockBin = { label: string; n: number; n_display?: string | null; pct_display?: string | null; bar_pct?: number };
type Clock = {
  slice: string;
  slice_label: string;
  n_stops: number;
  bins: ClockBin[];
  mean_remaining: Array<{ period: string; clock_display: string; n: number }>;
};

type Mean = { n: number; min: number; max: number; mean_display: string } | null;
type Scatter = {
  missing: number;
  n_survive: number;
  n_t67: number;
  x_label: string;
  y_label: string;
  points: Array<{ ticker: string; t67: boolean; entry_margin: number; final_margin: number; plot_x_pct: number; plot_y_pct: number }>;
  margins: {
    survive: { n: number; entry: Mean; final: Mean };
    t67: { n: number; entry: Mean; final: Mean; t67_time: Mean };
  };
};

type Desk = {
  membership_n: number;
  exclusions: Record<string, number>;
  universe: {
    n: number;
    terminal: { p_display?: string | null; p_pct_display?: string | null };
    trade?: Path;
    paths: Path[];
    mid_paths: Path[];
    comparisons: Path[];
    ledger_rank: string[];
    mid_ledger_rank: string[];
    unit?: string;
    verification?: string;
    cap_55_excluded: number;
  };
  partitions: Partition[];
  companions: Companion[];
  clocks: Clock[];
  scatter: Scatter;
  variables: Record<string, unknown>;
  disclaimers: string[];
  alignment: { model?: string; note?: string };
};

type Page = { status: string; message?: string; desk?: Desk };

function Row({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="row">
      <dt>{label}</dt>
      <dd>{text(value)}</dd>
    </div>
  );
}

function PathRow({ path, top }: { path: Path; top?: string }) {
  return (
    <div className={path.key === top ? "path-line is-top" : "path-line"}>
      <span>{path.key}</span>
      <span>
        {text(path.S_display)} · {text(path.S_pct_display)}
      </span>
      <span>{text(path.ev_per_trade_display)}</span>
    </div>
  );
}

function PartitionCard({ row }: { row: Partition }) {
  return (
    <article>
      <h2>
        {row.sport_label} · {row.slice_label}
      </h2>
      <dl>
        <Row label="universe N" value={row.n} />
        <Row label="terminal W / L" value={`${row.W} / ${row.L}`} />
        <Row label="terminal W/N" value={`${text(row.terminal.p_display)} · ${text(row.terminal.p_pct_display)}`} />
        <Row label="78/67 S" value={`${text(row.trade?.S_display)} · ${text(row.trade?.S_pct_display)}`} />
        <Row label="78/67 EV" value={row.trade?.ev_per_trade_display} />
        <Row label="ledger rank" value={row.ledger_rank.join(" > ")} />
        <Row label="mid rank" value={row.mid_ledger_rank.join(" > ")} />
      </dl>
      <div className="path-list">
        {row.paths.map((path) => (
          <PathRow key={path.key} path={path} top={row.ledger_rank[0]} />
        ))}
      </div>
      <div className="path-list">
        {row.mid_paths.map((path) => (
          <PathRow key={path.key} path={path} top={row.mid_ledger_rank[0]} />
        ))}
      </div>
      <div className="path-list">
        {row.comparisons.map((path) => (
          <PathRow key={path.key} path={path} />
        ))}
      </div>
      <div className="cells">
        <div className="cell">
          <span>W ∩ ¬T67</span>
          {row.cells.W_and_not_T67}
        </div>
        <div className="cell">
          <span>W ∩ T67</span>
          {row.cells.W_and_T67}
        </div>
        <div className="cell">
          <span>L ∩ ¬T67</span>
          {row.cells.L_and_not_T67}
        </div>
        <div className="cell">
          <span>L ∩ T67</span>
          {row.cells.L_and_T67}
        </div>
      </div>
    </article>
  );
}

function ClockPanel({ clock }: { clock: Clock }) {
  return (
    <article>
      <h2>
        {clock.slice_label} bets · T67 clock · {clock.n_stops} stops
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
        {clock.mean_remaining.map((row) => (
          <Row key={row.period} label={`${row.period} mean remaining`} value={`${row.clock_display} · n=${row.n}`} />
        ))}
      </dl>
    </article>
  );
}

function Scatter({ scatter }: { scatter: Scatter }) {
  const survive = scatter.margins.survive;
  const stopped = scatter.margins.t67;
  return (
    <article className="wide">
      <h2>NBA point differential · survive vs T67</h2>
      <p className="muted">
        {text(scatter.x_label)} vs {text(scatter.y_label)}. {scatter.n_survive} survive, {scatter.n_t67} T67.
        Missing scores {scatter.missing}. Not k-means. Survivors have no T67-time score.
      </p>
      <svg className="scatter" viewBox="0 0 100 100" role="img" aria-label="NBA survive versus T67 scatter">
        <rect x="0" y="0" width="100" height="100" className="scatter-bg" />
        {scatter.points.map((point) => (
          <circle
            key={point.ticker}
            cx={point.plot_x_pct}
            cy={point.plot_y_pct}
            r={point.t67 ? 0.7 : 0.55}
            className={point.t67 ? "dot-t40" : "dot-survive"}
          >
            <title>
              {point.ticker} entry {point.entry_margin} final {point.final_margin}
            </title>
          </circle>
        ))}
      </svg>
      <div className="legend">
        <span className="swatch survive" /> survive
        <span className="swatch t40" /> T67
      </div>
      <div className="stat-row second">
        <div className="stat">
          <dt>survive entry</dt>
          <dd>
            {text(survive.entry?.mean_display)}
            <span className="sub">
              n={survive.n} min {text(survive.entry?.min)} max {text(survive.entry?.max)}
            </span>
          </dd>
        </div>
        <div className="stat">
          <dt>survive final</dt>
          <dd>
            {text(survive.final?.mean_display)}
            <span className="sub">
              min {text(survive.final?.min)} max {text(survive.final?.max)}
            </span>
          </dd>
        </div>
        <div className="stat">
          <dt>T67 entry</dt>
          <dd>
            {text(stopped.entry?.mean_display)}
            <span className="sub">
              n={stopped.n} min {text(stopped.entry?.min)} max {text(stopped.entry?.max)}
            </span>
          </dd>
        </div>
        <div className="stat">
          <dt>T67-time / final</dt>
          <dd>
            {text(stopped.t67_time?.mean_display)}
            <span className="sub">final {text(stopped.final?.mean_display)}</span>
          </dd>
        </div>
      </div>
    </article>
  );
}

export default function First78() {
  const [page, setPage] = useState<Page | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const body = (await fetchFirst78("67")) as Page;
      setPage(body);
      setError(body.status === "OBSERVED" ? null : body.message || body.status);
    } catch (err) {
      setPage(null);
      setError(err instanceof UniverseError ? err.message : err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const desk = page?.desk;
  const observed = page?.status === "OBSERVED" && desk;
  const universe = desk?.universe;
  const paths = universe?.paths || [];
  const midPaths = universe?.mid_paths || [];
  const variables = desk?.variables || {};
  const topMid = universe?.mid_ledger_rank?.[0];

  return (
    <>
      <div className="page-meta">
        <span className={`pill ${observed ? "is-ok" : "is-bad"}`}>{observed ? "OBSERVED" : page?.status || "UNREAD"}</span>
        <button type="button" onClick={() => void load()}>
          refresh
        </button>
      </div>
      {error ? <p className="banner is-bad">{error}</p> : null}
      {universe ? (
        <section className="grid">
          <article className="wide">
            <h2>Universe · derived four, 78¢ entry</h2>
            <div className="stat-row">
              <div className="stat">
                <dt>Games N</dt>
                <dd>
                  {universe.n}
                  <span className="sub">{text(universe.unit)}</span>
                </dd>
              </div>
              <div className="stat">
                <dt>Terminal W/N</dt>
                <dd>
                  {text(universe.terminal.p_display)}
                  <span className="sub">{text(universe.terminal.p_pct_display)}</span>
                </dd>
              </div>
              <div className="stat">
                <dt>78/67 S</dt>
                <dd>
                  {text(universe.trade?.S_display)}
                  <span className="sub">{text(universe.trade?.S_pct_display)}</span>
                </dd>
              </div>
              <div className="stat">
                <dt>Verify</dt>
                <dd className="is-ok">
                  {text(universe.verification)}
                  <span className="sub">membership {text(desk?.membership_n)}</span>
                </dd>
              </div>
            </div>
            <div className="stat-row seven second">
              {paths.map((path) => (
                <div key={path.key} className={`stat ev-chip${path.key.endsWith("/67") ? " is-top" : ""}`}>
                  <dt>
                    {path.key} EV{path.key.endsWith("/67") ? " · official" : ""}
                  </dt>
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
              Ledger rank {text(universe.ledger_rank.join(" > "))}. Candle-path threshold EV, not a fill. Stops are
              52–77¢ around the official 67¢ exit, not the 40¢ ladder. Official trade is 78/67{" "}
              {text(universe.trade?.ev_per_trade_display)}, S {text(universe.trade?.S_display)}.
            </p>
            <div className="path-list">
              {(universe.comparisons || []).map((path) => (
                <PathRow key={path.key} path={path} />
              ))}
            </div>
          </article>
          {midPaths.length ? (
            <article className="wide">
              <h2>78/60 · 78/64 · 78/70 · 78/74 · same qualified book</h2>
              <div className="stat-row">
                {midPaths.map((path) => (
                  <div key={path.key} className={`stat ev-chip${path.key === topMid ? " is-top" : ""}`}>
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
                Mid rank {text(universe.mid_ledger_rank.join(" > "))}. Candle-path threshold EV, not a fill. Same qualified
                N as the other stops around 67¢. Not a 40¢ ladder.
              </p>
            </article>
          ) : null}
        </section>
      ) : null}
      {desk ? (
        <section>
          <h2>FIRST79 + FIRST81 · entry thresholds · same derived four</h2>
          <p className="muted">
            These are +1¢ and +3¢ entry comparisons on the same 52–77¢ exits. They do not change official FIRST78_67.
            Candle path ≠ fill.
          </p>
          {desk.companions.map((book) => (
            <div className="tau-block" key={book.rule}>
              <h3>
                {book.rule} · derived four qualified N={book.n} · gain {book.gain_cents}¢
              </h3>
              <p className="muted">{text(book.note)}</p>
              <div className="path-list">
                {book.paths.map((path) => (
                  <PathRow key={path.key} path={path} top={book.ledger_rank[0]} />
                ))}
              </div>
              <div className="grid four">
                {book.partitions.map((row) => (
                  <article key={row.partition_id}>
                    <h3>
                      {row.sport_label} · {row.slice_label} · N={row.n}
                    </h3>
                    <div className="path-list">
                      {row.paths.map((path) => (
                        <PathRow key={path.key} path={path} />
                      ))}
                    </div>
                  </article>
                ))}
              </div>
            </div>
          ))}
        </section>
      ) : null}
      {desk ? (
        <section className="grid four">
          {desk.partitions.map((row) => (
            <PartitionCard key={row.partition_id} row={row} />
          ))}
        </section>
      ) : null}
      {desk && universe ? (
        <section className="grid">
          <article className="wide">
            <h2>Charts · API bars only</h2>
            <div className="chart">
              {desk.partitions.map((row) => (
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
              {desk.partitions.map((row) => (
                <div key={`${row.partition_id}-s`} className="chart-row">
                  <span>{row.slice_label} 78/67 S</span>
                  <div className="track">
                    <div className="fill fill-s" style={{ width: width(row.trade?.S_bar_pct) }} />
                  </div>
                  <span>{text(row.trade?.S_pct_display)}</span>
                </div>
              ))}
            </div>
          </article>
          <article>
            <h2>Variables · locked</h2>
            <dl>
              <Row label="rule" value={variables.rule} />
              <Row label="K" value={variables.K} />
              <Row label="stop" value={variables.stop_cents} />
              <Row label="entry cap" value={variables.entry_cap_cents} />
              <Row label="gain" value={variables.gain_cents} />
              <Row label="path stops" value={(variables.path_stops as number[] | undefined)?.join(", ")} />
              <Row label="mid stops" value={(variables.mid_stops as number[] | undefined)?.join(", ")} />
              <Row label="comparison stops" value={(variables.comparison_stops as number[] | undefined)?.join(", ")} />
              <Row label="slices" value={(variables.slices as string[] | undefined)?.join(", ")} />
              <Row label="fee" value={variables.fee_applicability} />
              <Row label="locked" value={variables.locked} />
              <Row label="recompute" value={variables.recompute} />
            </dl>
            <p className="muted">{text(variables.note)}</p>
          </article>
          <article>
            <h2>Not this desk</h2>
            <ul className="muted">
              {(desk.disclaimers || []).map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </article>
        </section>
      ) : null}
      {desk ? (
        <section className="grid">
          {desk.clocks.map((clock) => (
            <ClockPanel key={clock.slice} clock={clock} />
          ))}
          <Scatter scatter={desk.scatter} />
          <article className="wide">
            <h2>Alignment</h2>
            <p className="muted">{text(desk.alignment.model)}</p>
            <p className="muted">{text(desk.alignment.note)}</p>
          </article>
        </section>
      ) : null}
    </>
  );
}
