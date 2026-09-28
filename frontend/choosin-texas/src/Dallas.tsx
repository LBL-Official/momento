import { useCallback, useEffect, useState, type ReactNode } from "react";
import { UniverseError, fetchDallas } from "./api";
import { text, width } from "./text";
import type {
  Dallas,
  DallasChart,
  DallasCollapse,
  DallasCross,
  DallasCut,
  DallasGame,
  DallasSlice,
  DallasSnapshot,
} from "./types";

type Layer = "game" | "snapshots" | "collapse";
type HoverFn = (lines: string[] | null) => void;

function cohortClass(cohort: string): string {
  if (cohort === "t40_win") return "dot-t40-win";
  if (cohort === "t40_lose") return "dot-t40-lose";
  return "dot-survive";
}

function HoverCard({ lines }: { lines: string[] | null }) {
  const shown = lines && lines.length ? lines : ["Hover a dot or a cut cell."];
  return (
    <div className="hover-card">
      {shown.map((line, index) => (
        <div key={`${index}-${line}`}>{text(line)}</div>
      ))}
    </div>
  );
}

function PlotFrame({
  chart,
  label,
  children,
}: {
  chart: DallasChart;
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="plot-frame">
      <div className="plot-y-title">{text(chart.y_label)}</div>
      <div className="plot-y-ticks">
        {(chart.y_ticks || []).map((tick) => (
          <span key={`y-${tick.value}`} className="plot-tick is-y" style={{ top: width(tick.plot_pct) }}>
            {text(tick.label)}
          </span>
        ))}
      </div>
      <div className="plot-canvas">
        <svg className="scatter" viewBox="0 0 100 100" role="img" aria-label={label}>
          <rect x="0" y="0" width="100" height="100" className="scatter-bg" />
          {children}
        </svg>
      </div>
      <div className="plot-x-ticks">
        {(chart.x_ticks || []).map((tick) => (
          <span key={`x-${tick.value}`} className="plot-tick is-x" style={{ left: width(tick.plot_pct) }}>
            {text(tick.label)}
          </span>
        ))}
      </div>
      <div className="plot-x-title">{text(chart.x_label)}</div>
    </div>
  );
}

function Stack({ cut }: { cut: DallasCut }) {
  return (
    <div className="track stack">
      <div className="fill fill-survive" style={{ width: width(cut.survive.bar_pct) }} />
      <div className="fill fill-t40-win" style={{ width: width(cut.t40_win.bar_pct) }} />
      <div className="fill fill-t40-lose" style={{ width: width(cut.t40_lose.bar_pct) }} />
    </div>
  );
}

function CutRates({ cut }: { cut: DallasCut }) {
  return (
    <div className="cut-rates">
      <span>
        T40 {text(cut.t40.display)} · {text(cut.t40.pct_display)}
      </span>
      <span>
        W ∩ T40 {text(cut.t40_win.display)} · {text(cut.t40_win.pct_display)}
      </span>
      <span>
        L ∩ T40 {text(cut.t40_lose.display)} · {text(cut.t40_lose.pct_display)}
      </span>
      <span>
        survive {text(cut.survive.display)} · {text(cut.survive.pct_display)}
      </span>
    </div>
  );
}

function CutChart({ title, rows, onHover }: { title: string; rows: DallasCut[]; onHover: HoverFn }) {
  return (
    <div className="chart">
      <h3>{title}</h3>
      {rows.map((row) => (
        <div
          key={row.key}
          className="cut-row"
          onMouseEnter={() => onHover(row.hover_lines)}
          onMouseLeave={() => onHover(null)}
        >
          <span>
            {row.label} · n {row.n}
          </span>
          <Stack cut={row} />
          <CutRates cut={row} />
        </div>
      ))}
    </div>
  );
}

function CrossGrid({ cross, onHover }: { cross: DallasCross; onHover: HoverFn }) {
  const byKey = new Map(cross.cells.map((cell) => [cell.key, cell]));
  return (
    <div className="cross-grid">
      <h3>lead at 80 × opening price</h3>
      <table>
        <thead>
          <tr>
            <th>lead \ open</th>
            {cross.pregame_labels.map((col) => (
              <th key={col.key}>{col.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {cross.lead_labels.map((row) => (
            <tr key={row.key}>
              <th>{row.label}</th>
              {cross.pregame_labels.map((col) => {
                const cell = byKey.get(`${row.key}__${col.key}`);
                if (!cell) {
                  return <td key={col.key} className="is-empty" />;
                }
                return (
                  <td
                    key={col.key}
                    onMouseEnter={() => onHover(cell.hover_lines)}
                    onMouseLeave={() => onHover(null)}
                  >
                    <Stack cut={cell} />
                    <span>n {cell.n}</span>
                    <span>T40 {text(cell.t40.display)}</span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function GameChart({ slice, onHover }: { slice: DallasSlice; onHover: HoverFn }) {
  return (
    <PlotFrame chart={slice.game_chart} label={`${slice.slice_label} game dots`}>
      {slice.games.map((point: DallasGame) => (
        <g key={point.ticker}>
          <circle
            cx={point.plot_x_pct}
            cy={point.plot_y_pct}
            r={point.cohort === "survive" ? 0.55 : 0.7}
            className={cohortClass(point.cohort)}
          />
          <circle
            cx={point.plot_x_pct}
            cy={point.plot_y_pct}
            r={1.8}
            className="dot-hit"
            onMouseEnter={() => onHover(point.hover_lines)}
            onMouseLeave={() => onHover(null)}
          />
        </g>
      ))}
    </PlotFrame>
  );
}

function SnapshotChart({ slice, onHover }: { slice: DallasSlice; onHover: HoverFn }) {
  return (
    <PlotFrame chart={slice.snapshot_chart} label={`${slice.slice_label} snapshots`}>
      {slice.snapshots.map((point: DallasSnapshot, index) => (
        <g key={`${point.ticker}-${point.label}-${index}`}>
          <circle
            cx={point.plot_x_pct}
            cy={point.plot_y_pct}
            r={point.label === "FIRST80" ? 0.7 : 0.5}
            className={cohortClass(point.cohort)}
          />
          <circle
            cx={point.plot_x_pct}
            cy={point.plot_y_pct}
            r={1.8}
            className="dot-hit"
            onMouseEnter={() => onHover(point.hover_lines)}
            onMouseLeave={() => onHover(null)}
          />
        </g>
      ))}
    </PlotFrame>
  );
}

function CollapseChart({ slice, onHover }: { slice: DallasSlice; onHover: HoverFn }) {
  return (
    <PlotFrame chart={slice.collapse_chart} label={`${slice.slice_label} collapse`}>
      {slice.collapse.map((point: DallasCollapse) => (
        <g key={point.ticker}>
          <line
            x1={point.plot_x0_pct}
            y1={point.plot_y0_pct}
            x2={point.plot_x_pct}
            y2={point.plot_y_pct}
            className="collapse-line"
          />
          <circle cx={point.plot_x_pct} cy={point.plot_y_pct} r={0.75} className={cohortClass(point.cohort)} />
          <circle
            cx={point.plot_x_pct}
            cy={point.plot_y_pct}
            r={1.8}
            className="dot-hit"
            onMouseEnter={() => onHover(point.hover_lines)}
            onMouseLeave={() => onHover(null)}
          />
        </g>
      ))}
    </PlotFrame>
  );
}

function SlicePanel({ slice, layer }: { slice: DallasSlice; layer: Layer }) {
  const [hover, setHover] = useState<string[] | null>(null);
  const chart =
    layer === "snapshots" ? (
      <SnapshotChart slice={slice} onHover={setHover} />
    ) : layer === "collapse" ? (
      <CollapseChart slice={slice} onHover={setHover} />
    ) : (
      <GameChart slice={slice} onHover={setHover} />
    );
  return (
    <article>
      <h2>
        {slice.slice_label} · N {slice.n}
      </h2>
      <div className="stat-row">
        <div className="stat">
          <dt>T40</dt>
          <dd>
            {text(slice.rates.t40.display)}
            <span className="sub">{text(slice.rates.t40.pct_display)}</span>
          </dd>
        </div>
        <div className="stat">
          <dt>W ∩ T40</dt>
          <dd>
            {text(slice.rates.t40_win.display)}
            <span className="sub">{text(slice.rates.t40_win.pct_display)}</span>
          </dd>
        </div>
        <div className="stat">
          <dt>L ∩ T40</dt>
          <dd>
            {text(slice.rates.t40_lose.display)}
            <span className="sub">{text(slice.rates.t40_lose.pct_display)}</span>
          </dd>
        </div>
        <div className="stat">
          <dt>survive</dt>
          <dd>
            {text(slice.rates.survive.display)}
            <span className="sub">{text(slice.rates.survive.pct_display)}</span>
          </dd>
        </div>
      </div>
      {chart}
      <HoverCard lines={hover} />
      <CutChart title="by lead at 80" rows={slice.cuts.lead_80} onHover={setHover} />
      <CutChart title="by opening price" rows={slice.cuts.pregame} onHover={setHover} />
      <CrossGrid cross={slice.cuts.cross} onHover={setHover} />
    </article>
  );
}

export default function Dallas() {
  const [desk, setDesk] = useState<Dallas | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [layer, setLayer] = useState<Layer>("game");
  const [poolHover, setPoolHover] = useState<string[] | null>(null);

  const load = useCallback(async () => {
    try {
      const next = await fetchDallas();
      if (next.status !== "OBSERVED") {
        setDesk(null);
        setError(next.message || next.status || "LOCK_MISMATCH");
        return;
      }
      setDesk(next);
      setError(null);
    } catch (err) {
      setDesk(null);
      if (err instanceof UniverseError) {
        setError(err.message);
        return;
      }
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const observed = desk !== null && desk.status === "OBSERVED";

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

      {desk ? (
        <section className="grid">
          <article className="wide">
            <h2>Dallas · NBA 2Q+3Q deterioration</h2>
            <div className="stat-row">
              <div className="stat">
                <dt>Games N</dt>
                <dd>
                  {desk.n}
                  <span className="sub">FIRST80 NBA 2Q ∪ 3Q</span>
                </dd>
              </div>
              <div className="stat">
                <dt>T40</dt>
                <dd>
                  {text(desk.rates.t40.display)}
                  <span className="sub">{text(desk.rates.t40.pct_display)}</span>
                </dd>
              </div>
              <div className="stat">
                <dt>W ∩ T40</dt>
                <dd>
                  {text(desk.rates.t40_win.display)}
                  <span className="sub">{desk.n_t40_win} path stops that still settled yes</span>
                </dd>
              </div>
              <div className="stat">
                <dt>L ∩ T40</dt>
                <dd>
                  {text(desk.rates.t40_lose.display)}
                  <span className="sub">{desk.n_t40_lose} path stops that settled no</span>
                </dd>
              </div>
            </div>
            <div className="layer-toggle">
              <button type="button" className={layer === "game" ? "is-on" : ""} onClick={() => setLayer("game")}>
                Game
              </button>
              <button
                type="button"
                className={layer === "snapshots" ? "is-on" : ""}
                onClick={() => setLayer("snapshots")}
              >
                Snapshots
              </button>
              <button
                type="button"
                className={layer === "collapse" ? "is-on" : ""}
                onClick={() => setLayer("collapse")}
              >
                Collapse
              </button>
            </div>
            <p className="muted">{text(desk.note)}</p>
            <p className="muted">
              Exiting before 40 would have also killed the {desk.n_t40_win} W∩T40 books. Not an early-exit
              rule. Hover a dot for what that point is. Cuts are not a tradable filter.
            </p>
            <div className="legend">
              <span className="swatch survive" /> survive
              <span className="swatch t40-win" /> T40 then won
              <span className="swatch t40-lose" /> T40 then lost
            </div>
          </article>
        </section>
      ) : null}

      {desk ? (
        <section className="grid">
          {desk.slices.map((slice) => (
            <SlicePanel key={slice.slice} slice={slice} layer={layer} />
          ))}
        </section>
      ) : null}

      {desk ? (
        <section className="grid">
          <article className="wide">
            <h2>Pool cuts · NBA 2Q ∪ 3Q</h2>
            <HoverCard lines={poolHover} />
            <div className="grid">
              <CutChart title="by lead at 80" rows={desk.cuts.lead_80} onHover={setPoolHover} />
              <CutChart title="by opening price" rows={desk.cuts.pregame} onHover={setPoolHover} />
            </div>
            <CrossGrid cross={desk.cuts.cross} onHover={setPoolHover} />
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
    </>
  );
}
