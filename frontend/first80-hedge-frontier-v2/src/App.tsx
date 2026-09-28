import { useEffect, useMemo, useState } from "react";

type Wilson = { n: number; k: number; rate: number | null; pct: number | null; ci95: (number | null)[] };
type Dist = { n: number; mean: number; median: number | null } | null;
type Row = {
  h: number;
  n: number;
  hedge_opportunities: number;
  false_hedges: number;
  protected_losses: number;
  catastrophic_misses: number;
  no_hedge_wins: number;
  gross_ev_cents: number;
  ev_per_reserved: number;
  ev_per_conditional_capital: number | null;
  p_opportunity: Wilson;
  p_false_hedge: Wilson;
  p_miss: Wilson;
  precision_loss: Wilson;
  recall_loss: Wilson;
  time_to_hedge_min: Dist;
  hedge_leads_fav40_min: Dist;
  p_persist_ge: Record<string, number | null>;
  regimes: Record<string, number>;
  held_bid_at_H_cents: Dist;
  fee_max_total_cents: number;
};
type Persist = {
  h: number;
  persist_min: number;
  hedge_opportunities: number;
  false_hedges: number;
  protected_losses: number;
  catastrophic_misses: number;
  gross_ev_cents: number;
  ev_per_reserved: number;
};
type Cmp = {
  strategy: string;
  sport: string;
  h: number | null;
  gross_ev: number;
  reserved: number;
  ev_cap: number;
  recall?: number;
  miss?: number;
};
type Dash = {
  banner: string;
  verdict: [string, string];
  policy: Record<string, { selected_h: number | null }>;
  reproduction: Record<string, { ok: boolean }>;
  split_counts: Record<string, Record<string, number>>;
  oos_eval: Record<string, Record<string, { gross_ev_cents: number }>>;
  frontiers: Record<string, Record<string, Record<string, Row[]>>>;
  persist_surface: Record<string, Persist[]>;
  comparison: Cmp[];
};

const VIEWS = [
  ["economics", "Economics"],
  ["risk", "Risk"],
  ["execution", "Execution plausibility"],
  ["geometry", "Path geometry"],
  ["cross", "Cross-sport"],
] as const;

function fmt(n?: number | null, d = 2) {
  return n == null || Number.isNaN(n) ? "—" : n.toFixed(d);
}
function pct(n?: number | null) {
  return n == null ? "—" : `${(n * 100).toFixed(2)}%`;
}

function LineChart({
  series,
  yLabel,
}: {
  series: { name: string; pts: { x: number; y: number }[] }[];
  yLabel: string;
}) {
  const w = 640;
  const h = 220;
  const pad = { l: 48, r: 12, t: 12, b: 28 };
  const xs = series.flatMap((s) => s.pts.map((p) => p.x));
  const ys = series.flatMap((s) => s.pts.map((p) => p.y));
  if (!xs.length) return null;
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(0, ...ys);
  const maxY = Math.max(...ys);
  const x = (v: number) => pad.l + ((v - minX) / (maxX - minX || 1)) * (w - pad.l - pad.r);
  const y = (v: number) => h - pad.b - ((v - minY) / (maxY - minY || 1)) * (h - pad.t - pad.b);
  const colors = ["#c8a25a", "#6ea8d6", "#3dba7a", "#e05d5d"];
  return (
    <div className="chart">
      <svg viewBox={`0 0 ${w} ${h}`}>
        <line x1={pad.l} y1={y(0)} x2={w - pad.r} y2={y(0)} stroke="#232a33" />
        <text x={8} y={16} fill="#8b98a5" fontSize="10">
          {yLabel}
        </text>
        <text x={pad.l} y={h - 8} fill="#8b98a5" fontSize="10">
          {minX}
        </text>
        <text x={w - 40} y={h - 8} fill="#8b98a5" fontSize="10">
          {maxX}
        </text>
        {series.map((s, i) => (
          <polyline
            key={s.name}
            fill="none"
            stroke={colors[i % colors.length]}
            strokeWidth="1.6"
            points={s.pts.map((p) => `${x(p.x)},${y(p.y)}`).join(" ")}
          />
        ))}
      </svg>
      <div className="caption">
        {series.map((s, i) => (
          <span key={s.name} style={{ color: colors[i % colors.length], marginRight: 12 }}>
            {s.name}
          </span>
        ))}
        · candle PRICE_OPPORTUNITY, not a fill
      </div>
    </div>
  );
}

function Card({ k, v, cls }: { k: string; v: string; cls?: string }) {
  return (
    <div className="card">
      <div className="k">{k}</div>
      <div className={`v ${cls ?? ""}`}>{v}</div>
    </div>
  );
}

export default function App() {
  const [dash, setDash] = useState<Dash | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [sport, setSport] = useState<"nba" | "ncaab" | "both">("ncaab");
  const [split, setSplit] = useState("FULL");
  const [path, setPath] = useState<"close" | "wick">("close");
  const [h, setH] = useState(40);
  const [capital, setCapital] = useState<"reserved" | "conditional">("reserved");
  const [persist, setPersist] = useState(0);
  const [view, setView] = useState<(typeof VIEWS)[number][0]>("economics");

  useEffect(() => {
    fetch("/data/dashboard.json")
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then(setDash)
      .catch((e: Error) => setErr(e.message));
  }, []);

  const sports = sport === "both" ? (["nba", "ncaab"] as const) : ([sport] as const);

  const rowsFor = (sp: string): Row[] => {
    if (!dash) return [];
    if (persist > 0 && path === "close" && split === "FULL") {
      const n = dash.split_counts[sp].FULL;
      return dash.persist_surface[sp]
        .filter((p) => p.persist_min === persist)
        .map((p) => ({
          h: p.h,
          n,
          hedge_opportunities: p.hedge_opportunities,
          false_hedges: p.false_hedges,
          protected_losses: p.protected_losses,
          catastrophic_misses: p.catastrophic_misses,
          no_hedge_wins: 0,
          gross_ev_cents: p.gross_ev_cents,
          ev_per_reserved: p.ev_per_reserved,
          ev_per_conditional_capital: null,
          p_opportunity: { n: 0, k: 0, rate: null, pct: null, ci95: [] },
          p_false_hedge: { n: 0, k: 0, rate: null, pct: null, ci95: [] },
          p_miss: { n: 0, k: 0, rate: null, pct: null, ci95: [] },
          precision_loss: { n: 0, k: 0, rate: null, pct: null, ci95: [] },
          recall_loss: { n: 0, k: 0, rate: null, pct: null, ci95: [] },
          time_to_hedge_min: null,
          hedge_leads_fav40_min: null,
          p_persist_ge: {},
          regimes: {},
          held_bid_at_H_cents: null,
          fee_max_total_cents: p.gross_ev_cents,
        }));
    }
    return dash.frontiers[sp][split][path];
  };

  const evSeries = useMemo(() => {
    if (!dash) return [];
    return sports.map((sp) => ({
      name: `${sp} EV ¢`,
      pts: rowsFor(sp).map((r) => ({ x: r.h, y: r.gross_ev_cents })),
    }));
  }, [dash, sport, split, path, persist]);

  const capSeries = useMemo(() => {
    if (!dash) return [];
    return sports.map((sp) => ({
      name: `${sp} EV/${capital}`,
      pts: rowsFor(sp).map((r) => ({
        x: r.h,
        y: capital === "reserved" ? r.ev_per_reserved * 100 : (r.ev_per_conditional_capital ?? 0) * 100,
      })),
    }));
  }, [dash, sport, split, path, persist, capital]);

  if (err) return <div className="main">Failed to load dashboard.json ({err})</div>;
  if (!dash) return <div className="main muted">Loading…</div>;

  const focus = sports[0];
  const row = rowsFor(focus).find((r) => r.h === h);

  return (
    <div className="app">
      <div className="banner">{dash.banner} · LIVE EXECUTION CHANGED: FALSE · no arming controls</div>
      <div className="top">
        <div className="brand">
          FIRST80 HEDGE FRONTIER V2
          <small>
            Verdict {dash.verdict[0]} · H* NBA {dash.policy.nba.selected_h} / NCAAB {dash.policy.ncaab.selected_h}
          </small>
        </div>
        <div className="ctrl">
          <label>Sport</label>
          <select value={sport} onChange={(e) => setSport(e.target.value as typeof sport)}>
            <option value="ncaab">NCAAB</option>
            <option value="nba">NBA</option>
            <option value="both">Both</option>
          </select>
        </div>
        <div className="ctrl">
          <label>Dataset</label>
          <select value={split} onChange={(e) => setSplit(e.target.value)}>
            <option value="FULL">Full research view</option>
            <option value="TRAIN">TRAIN</option>
            <option value="VALIDATION">VALIDATION</option>
            <option value="OOS">OOS</option>
          </select>
        </div>
        <div className="ctrl">
          <label>Path</label>
          <select value={path} onChange={(e) => setPath(e.target.value as "close" | "wick")}>
            <option value="close">Close (primary)</option>
            <option value="wick">Wick (diagnostic)</option>
          </select>
        </div>
        <div className="ctrl">
          <label>Hedge H = {h}¢</label>
          <input type="range" min={20} max={60} value={h} onChange={(e) => setH(Number(e.target.value))} />
        </div>
        <div className="ctrl">
          <label>Capital</label>
          <select value={capital} onChange={(e) => setCapital(e.target.value as typeof capital)}>
            <option value="reserved">Reserved 80+H</option>
            <option value="conditional">Conditional (research only)</option>
          </select>
        </div>
        <div className="ctrl">
          <label>Persistence filter</label>
          <select value={persist} onChange={(e) => setPersist(Number(e.target.value))}>
            {[0, 1, 2, 3, 5, 10].map((x) => (
              <option key={x} value={x}>
                {x} min
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="tabs">
        {VIEWS.map(([id, label]) => (
          <button key={id} className={view === id ? "on" : ""} onClick={() => setView(id)}>
            {label}
          </button>
        ))}
      </div>
      <div className="main">
        <p className="muted">{dash.verdict[1]}</p>
        {persist > 0 && (
          <p className="muted">Persistence surface is FULL / close / coarse H only. PROXY, not a live wait rule.</p>
        )}

        {view === "economics" && (
          <>
            <div className="row">
              <Card k={`${focus} opportunities`} v={String(row?.hedge_opportunities ?? "—")} />
              <Card k="False hedges" v={String(row?.false_hedges ?? "—")} cls="warn" />
              <Card k="Protected losses" v={String(row?.protected_losses ?? "—")} cls="pos" />
              <Card k="Catastrophic misses" v={String(row?.catastrophic_misses ?? "—")} cls="neg" />
              <Card k="Gross EV ¢" v={fmt(row?.gross_ev_cents)} cls={(row?.gross_ev_cents ?? 0) >= 0 ? "pos" : "neg"} />
              <Card
                k={capital === "reserved" ? "EV / reserved" : "EV / cond. cap"}
                v={capital === "reserved" ? fmt(row?.ev_per_reserved, 4) : fmt(row?.ev_per_conditional_capital, 4)}
              />
              <Card k="Fee_max (gross)" v={`${fmt(row?.fee_max_total_cents)}¢`} />
            </div>
            <h2>H vs gross EV</h2>
            <LineChart series={evSeries} yLabel="Gross EV ¢" />
            <h2>H vs EV per capital</h2>
            <LineChart series={capSeries} yLabel="EV / capital ×100" />
            <h2>H* TRAIN / VAL / OOS</h2>
            <table>
              <thead>
                <tr>
                  <th>Sport</th>
                  <th>H*</th>
                  <th>TRAIN EV</th>
                  <th>VAL EV</th>
                  <th>OOS EV</th>
                </tr>
              </thead>
              <tbody>
                {(["nba", "ncaab"] as const).map((sp) => (
                  <tr key={sp}>
                    <td>{sp}</td>
                    <td>{dash.policy[sp].selected_h}</td>
                    <td>{fmt(dash.oos_eval[sp]?.TRAIN?.gross_ev_cents)}</td>
                    <td>{fmt(dash.oos_eval[sp]?.VALIDATION?.gross_ev_cents)}</td>
                    <td>{fmt(dash.oos_eval[sp]?.OOS?.gross_ev_cents)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {view === "risk" && (
          <>
            <div className="row">
              <Card k="Miss rate" v={row?.p_miss.pct != null ? `${row.p_miss.pct}%` : "—"} cls="neg" />
              <Card k="Loss recall" v={row?.recall_loss.pct != null ? `${row.recall_loss.pct}%` : "—"} />
              <Card k="Precision (NO|H)" v={row?.precision_loss.pct != null ? `${row.precision_loss.pct}%` : "—"} />
              <Card k="False-hedge rate" v={row?.p_false_hedge.pct != null ? `${row.p_false_hedge.pct}%` : "—"} cls="warn" />
            </div>
            <h2>Catastrophic miss rate</h2>
            <LineChart
              series={sports.map((sp) => ({
                name: sp,
                pts: rowsFor(sp).map((r) => ({ x: r.h, y: (r.p_miss.rate ?? 0) * 100 })),
              }))}
              yLabel="Miss %"
            />
            <h2>False hedge rate</h2>
            <LineChart
              series={sports.map((sp) => ({
                name: sp,
                pts: rowsFor(sp).map((r) => ({ x: r.h, y: (r.p_false_hedge.rate ?? 0) * 100 })),
              }))}
              yLabel="False %"
            />
            <h2>Precision vs recall (loss protection)</h2>
            <p className="muted">
              Empirical P(favorite NO | opponent reaches H) vs P(opponent reaches H | favorite NO). Not a
              classifier. Empty under the persistence surface (rates not recomputed there).
            </p>
            <LineChart
              series={sports.map((sp) => ({
                name: `${sp} PR`,
                pts: rowsFor(sp)
                  .filter((r) => r.recall_loss.rate != null && r.precision_loss.rate != null)
                  .map((r) => ({
                    x: (r.recall_loss.rate as number) * 100,
                    y: (r.precision_loss.rate as number) * 100,
                  })),
              }))}
              yLabel="Precision %"
            />
          </>
        )}

        {view === "execution" && (
          <>
            <p className="muted">
              FILL_PLAUSIBILITY_PROXY. Persistence is minutes the opponent close stayed ≥ H after first touch. Not a
              queue model.
            </p>
            <table>
              <thead>
                <tr>
                  <th>Regime at H={h}</th>
                  <th>Count</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(row?.regimes ?? {}).map(([k, v]) => (
                  <tr key={k}>
                    <td>{k}</td>
                    <td>{v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {row && (
              <>
                <h2>P(persist ≥ X) at H={h}</h2>
                <LineChart
                  series={[
                    {
                      name: `${focus} persist`,
                      pts: Object.entries(row.p_persist_ge)
                        .map(([x, p]) => ({ x: Number(x), y: (p ?? 0) * 100 }))
                        .sort((a, b) => a.x - b.x),
                    },
                  ]}
                  yLabel="% of opportunities"
                />
              </>
            )}
          </>
        )}

        {view === "geometry" && (
          <>
            <div className="row">
              <Card k="Median time-to-H (min)" v={fmt(row?.time_to_hedge_min?.median, 1)} />
              <Card k="Median lead vs fav-40 (min)" v={fmt(row?.hedge_leads_fav40_min?.median, 1)} />
              <Card k="Held YES at H (median ¢)" v={fmt(row?.held_bid_at_H_cents?.median, 1)} />
            </div>
            <h2>Median time-to-hedge</h2>
            <LineChart
              series={sports.map((sp) => ({
                name: sp,
                pts: rowsFor(sp)
                  .filter((r) => r.time_to_hedge_min?.median != null)
                  .map((r) => ({ x: r.h, y: r.time_to_hedge_min!.median as number })),
              }))}
              yLabel="Minutes"
            />
          </>
        )}

        {view === "cross" && (
          <>
            <h2>NBA vs NCAAB EV</h2>
            <LineChart
              series={(["nba", "ncaab"] as const).map((sp) => ({
                name: sp,
                pts: dash.frontiers[sp][split][path].map((r) => ({ x: r.h, y: r.gross_ev_cents })),
              }))}
              yLabel="Gross EV ¢"
            />
            <h2>Required comparison</h2>
            <table>
              <thead>
                <tr>
                  <th>Strategy</th>
                  <th>Sport</th>
                  <th>H</th>
                  <th>Gross EV</th>
                  <th>Reserved</th>
                  <th>EV/cap</th>
                  <th>Recall</th>
                  <th>Miss</th>
                </tr>
              </thead>
              <tbody>
                {dash.comparison.map((r, i) => (
                  <tr key={i} className={r.strategy === "Selected H*" ? "hl" : undefined}>
                    <td>{r.strategy}</td>
                    <td>{r.sport}</td>
                    <td>{r.h == null ? "—" : r.h}</td>
                    <td>{fmt(r.gross_ev)}</td>
                    <td>{r.reserved}</td>
                    <td>{fmt(r.ev_cap, 4)}</td>
                    <td>{pct(r.recall)}</td>
                    <td>{r.miss == null ? "—" : r.miss}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="muted">
              Reproduction NBA {dash.reproduction.nba.ok ? "PASS" : "FAIL"} · NCAAB{" "}
              {dash.reproduction.ncaab.ok ? "PASS" : "FAIL"}. Architecture C UNAVAILABLE. ACTUAL_FILL NOT_RUN.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
