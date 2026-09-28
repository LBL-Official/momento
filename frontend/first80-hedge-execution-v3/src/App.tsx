import { useEffect, useMemo, useState } from "react";

type Surf = {
  h: number;
  n: number;
  close: number;
  wick: number;
  wick_only: number;
  classes: Record<string, number>;
  p_close: number | null;
  p_wick: number | null;
  median_persist: number | null;
  median_overshoot: number | null;
  median_rest_min: number | null;
  p_persist_ge: Record<string, number | null>;
  false: number;
  protected: number;
  miss: number;
  recall: number | null;
};
type EvPt = { h: number; p: number; ev: number; vs_stop: number; ev_cap: number };
type Pmin = { p_min_ev_positive: number | null; p_min_beat_8040: number | null; hold: number; stop: number };
type Req = { h: number; scenario: string; p_min_pos: number | null; p_min_8040: number | null; class_n: Record<string, number> };
type UMap = { split: string; cluster: number; x: number; y: number; persist: number | null; overshoot: number | null; class: string; settlement: string };
type Dash = {
  banner: string;
  verdict: [string, string];
  layers: { id: number; name: string; status: string }[];
  reproduction: Record<string, { ok: boolean }>;
  split_counts: Record<string, Record<string, number>>;
  surface: Record<string, Record<string, Surf[]>>;
  frontier: Record<string, { grid: EvPt[]; pmin: Record<string, Pmin> }>;
  required_fill: Record<string, Req[]>;
  cluster: Record<string, { method?: string; k?: number; silhouette_val?: number; rank_stable_train_val_oos?: boolean; observable?: Record<string, Record<string, { n: number; median_persist: number | null; median_overshoot: number | null; reversal_rate: number | null }>>; selection_rule?: string }>;
  umap: Record<string, UMap[]>;
  capital: Record<string, { h: number | null; p_fill_assumed: number | string | null; architecture: string; reserved_cents: number | null; gross_ev_cents: number | null; ev_per_capital: number | null }[]>;
  v2_h_star: Record<string, number>;
  portfolio_margin: string;
  actual_fill_experiment: string;
};

const VIEWS = [
  ["verdict", "Verdict"],
  ["surface", "Opportunity surface"],
  ["taxonomy", "Path taxonomy"],
  ["frontier", "Fill-probability frontier"],
  ["cluster", "Cluster explorer"],
  ["capital", "Reserved capital"],
  ["required", "Required fill quality"],
] as const;

function fmt(n?: number | null, d = 2) {
  return n == null || Number.isNaN(n) ? "—" : n.toFixed(d);
}
function pct(n?: number | null) {
  return n == null ? "—" : `${(n * 100).toFixed(1)}%`;
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
        · scenario / PRICE_OPPORTUNITY — not a fill
      </div>
    </div>
  );
}

function Scatter({ pts }: { pts: UMap[] }) {
  if (!pts.length) return <p className="muted">No UMAP points.</p>;
  const w = 640;
  const h = 280;
  const pad = 24;
  const xs = pts.map((p) => p.x);
  const ys = pts.map((p) => p.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const x = (v: number) => pad + ((v - minX) / (maxX - minX || 1)) * (w - 2 * pad);
  const y = (v: number) => h - pad - ((v - minY) / (maxY - minY || 1)) * (h - 2 * pad);
  const colors = ["#c8a25a", "#6ea8d6", "#3dba7a", "#e05d5d", "#b07ad6"];
  return (
    <div className="chart">
      <svg viewBox={`0 0 ${w} ${h}`}>
        {pts.map((p, i) => (
          <circle key={i} cx={x(p.x)} cy={y(p.y)} r="2.4" fill={colors[p.cluster % colors.length]} opacity="0.85" />
        ))}
      </svg>
      <div className="caption">UMAP of path features at H=40 close opportunities. Color = cluster. Not “good execution.”</div>
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
  const [h, setH] = useState(40);
  const [pFill, setPFill] = useState(50);
  const [view, setView] = useState<(typeof VIEWS)[number][0]>("verdict");

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

  const evAt = useMemo(() => {
    if (!dash) return [];
    const p = pFill / 100;
    return sports.map((sp) => {
      const grid = dash.frontier[sp].grid.filter((r) => r.h === h);
      const hit = grid.find((r) => Math.abs(r.p - p) < 1e-9);
      return { sport: sp, ev: hit?.ev ?? null, vs: hit?.vs_stop ?? null, cap: hit?.ev_cap ?? null };
    });
  }, [dash, sport, h, pFill]);

  if (err) return <div className="main">Failed to load dashboard.json ({err})</div>;
  if (!dash) return <div className="main muted">Loading…</div>;

  const focus = sports[0];
  const row = dash.surface[focus][split]?.find((r) => r.h === h);
  const pmin = dash.frontier[focus].pmin[String(h)];

  return (
    <div className="app">
      <div className="banner">{dash.banner}</div>
      <div className="top">
        <div className="brand">
          FIRST80 HEDGE EXECUTION V3
          <small>
            Verdict {dash.verdict[0]} · ACTUAL_FILL {dash.actual_fill_experiment} · no arming
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
            <option value="FULL">Full</option>
            <option value="TRAIN">TRAIN</option>
            <option value="VALIDATION">VALIDATION</option>
            <option value="OOS">OOS</option>
          </select>
        </div>
        <div className="ctrl">
          <label>Hedge H = {h}¢</label>
          <input type="range" min={10} max={60} value={h} onChange={(e) => setH(Number(e.target.value))} />
        </div>
        <div className="ctrl">
          <label>Assumed p_fill = {pFill}%</label>
          <input type="range" min={0} max={100} step={10} value={pFill} onChange={(e) => setPFill(Number(e.target.value))} />
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
        {view === "verdict" && (
          <>
            <p className="muted">{dash.verdict[1]}</p>
            <div className="row">
              <Card k="Verdict" v={dash.verdict[0]} cls="warn" />
              <Card k="NBA H=40 gate" v={dash.reproduction.nba.ok ? "PASS" : "FAIL"} cls={dash.reproduction.nba.ok ? "pos" : "neg"} />
              <Card k="NCAAB H=40 gate" v={dash.reproduction.ncaab.ok ? "PASS" : "FAIL"} cls={dash.reproduction.ncaab.ok ? "pos" : "neg"} />
              <Card k="Portfolio margin" v={dash.portfolio_margin} />
            </div>
            <h2>Four-layer model</h2>
            <ol className="layers">
              {dash.layers.map((L) => (
                <li key={L.id}>
                  <strong>{L.name}</strong>
                  <span className={L.id === 3 ? "neg" : "muted"}> — {L.status}</span>
                </li>
              ))}
            </ol>
            <p className="muted">
              A pre-rested maker bid at H is a different execution problem than a reactive 80/40 liquidation.
              Neither fill is historically observed.
            </p>
          </>
        )}

        {view === "surface" && (
          <>
            <div className="row">
              <Card k={`${focus} close opp`} v={String(row?.close ?? "—")} />
              <Card k="Wick opp" v={String(row?.wick ?? "—")} />
              <Card k="Wick-only" v={String(row?.wick_only ?? "—")} cls="warn" />
              <Card k="Median persist (min)" v={fmt(row?.median_persist, 1)} />
              <Card k="Median overshoot ¢" v={fmt(row?.median_overshoot, 1)} />
              <Card k="Median rest before touch" v={`${fmt(row?.median_rest_min, 0)} min`} />
            </div>
            <h2>H vs close opportunity rate</h2>
            <LineChart
              series={sports.map((sp) => ({
                name: sp,
                pts: (dash.surface[sp][split] ?? []).map((r) => ({ x: r.h, y: (r.p_close ?? 0) * 100 })),
              }))}
              yLabel="Close %"
            />
            <h2>H vs median persistence</h2>
            <LineChart
              series={sports.map((sp) => ({
                name: sp,
                pts: (dash.surface[sp][split] ?? [])
                  .filter((r) => r.median_persist != null)
                  .map((r) => ({ x: r.h, y: r.median_persist as number })),
              }))}
              yLabel="Minutes"
            />
          </>
        )}

        {view === "taxonomy" && (
          <>
            <p className="muted">
              Deterministic FILL_OPPORTUNITY_QUALITY. Strong ≠ fill. Jump = previous close &lt; H−10¢.
            </p>
            <table>
              <thead>
                <tr>
                  <th>Class at H={h}</th>
                  <th>Count</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(row?.classes ?? {}).map(([k, v]) => (
                  <tr key={k}>
                    <td>{k}</td>
                    <td>{v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <h2>Class mix vs H (close + wick-only)</h2>
            <LineChart
              series={["A_STRONG", "B_MODERATE", "C_WEAK", "E_JUMP"].map((cl) => ({
                name: cl,
                pts: (dash.surface[focus][split] ?? []).map((r) => ({ x: r.h, y: r.classes[cl] ?? 0 })),
              }))}
              yLabel="Count"
            />
          </>
        )}

        {view === "frontier" && (
          <>
            <div className="row">
              {evAt.map((e) => (
                <Card key={e.sport} k={`${e.sport} EV @ p=${pFill}%`} v={`${fmt(e.ev)}¢`} cls={(e.ev ?? 0) >= 0 ? "pos" : "neg"} />
              ))}
              <Card k={`${focus} p_min EV>0`} v={pct(pmin?.p_min_ev_positive)} />
              <Card k={`${focus} p_min beat 80/40`} v={pct(pmin?.p_min_beat_8040)} cls="warn" />
            </div>
            <p className="muted">p_fill is an assumed scenario. It is not estimated from candles.</p>
            <h2>EV vs assumed p_fill at H={h}</h2>
            <LineChart
              series={sports.map((sp) => ({
                name: sp,
                pts: dash.frontier[sp].grid.filter((r) => r.h === h).map((r) => ({ x: r.p * 100, y: r.ev })),
              }))}
              yLabel="Gross EV ¢"
            />
            <h2>p_min to beat 80/40 vs H</h2>
            <LineChart
              series={sports.map((sp) => ({
                name: sp,
                pts: Object.entries(dash.frontier[sp].pmin)
                  .map(([hh, v]) => ({ x: Number(hh), y: (v.p_min_beat_8040 ?? Number.NaN) * 100 }))
                  .filter((p) => !Number.isNaN(p.y)),
              }))}
              yLabel="Min p_fill %"
            />
          </>
        )}

        {view === "cluster" && (
          <>
            <p className="muted">
              {focus}: {dash.cluster[focus].method} k={dash.cluster[focus].k} · VAL silhouette {fmt(dash.cluster[focus].silhouette_val, 3)} ·
              rank-stable {String(dash.cluster[focus].rank_stable_train_val_oos)} · {dash.cluster[focus].selection_rule}
            </p>
            <Scatter pts={dash.umap[focus] ?? []} />
            <table>
              <thead>
                <tr>
                  <th>Split</th>
                  <th>Cluster</th>
                  <th>n</th>
                  <th>Median persist</th>
                  <th>Median overshoot</th>
                  <th>Reversal</th>
                </tr>
              </thead>
              <tbody>
                {(["TRAIN", "VALIDATION", "OOS"] as const).flatMap((sp) =>
                  Object.entries(dash.cluster[focus].observable?.[sp] ?? {}).map(([c, o]) => (
                    <tr key={`${sp}-${c}`}>
                      <td>{sp}</td>
                      <td>{c}</td>
                      <td>{o.n}</td>
                      <td>{fmt(o.median_persist, 1)}</td>
                      <td>{fmt(o.median_overshoot, 1)}</td>
                      <td>{pct(o.reversal_rate)}</td>
                    </tr>
                  )),
                )}
              </tbody>
            </table>
          </>
        )}

        {view === "capital" && (
          <>
            <p className="muted">Architecture C portfolio margin = {dash.portfolio_margin}. Reserved = 80+H even if the hedge never fills.</p>
            <table>
              <thead>
                <tr>
                  <th>Arch</th>
                  <th>H</th>
                  <th>p_fill</th>
                  <th>EV ¢</th>
                  <th>Capital</th>
                  <th>EV/cap</th>
                </tr>
              </thead>
              <tbody>
                {(dash.capital[focus] ?? [])
                  .filter((r) => r.p_fill_assumed === pFill / 100 || r.architecture === "STOP_80_40" || r.architecture === "C_PORTFOLIO_MARGIN")
                  .map((r, i) => (
                    <tr key={i}>
                      <td>{r.architecture}</td>
                      <td>{r.h ?? "—"}</td>
                      <td>{r.p_fill_assumed ?? "—"}</td>
                      <td>{fmt(r.gross_ev_cents)}</td>
                      <td>{r.reserved_cents ?? "—"}</td>
                      <td>{fmt(r.ev_per_capital, 4)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </>
        )}

        {view === "required" && (
          <>
            <p className="muted">
              Historical opportunity → minimum assumed maker fill rate → next-season empirical test. V2 H* NBA{" "}
              {dash.v2_h_star.nba} / NCAAB {dash.v2_h_star.ncaab}.
            </p>
            <table>
              <thead>
                <tr>
                  <th>Sport</th>
                  <th>H</th>
                  <th>Scenario</th>
                  <th>p_min EV&gt;0</th>
                  <th>p_min beat 80/40</th>
                </tr>
              </thead>
              <tbody>
                {(["nba", "ncaab"] as const).flatMap((sp) =>
                  dash.required_fill[sp]
                    .filter((r) => r.h === h || r.h === dash.v2_h_star[sp] || r.h === 40)
                    .map((r, i) => (
                      <tr key={`${sp}-${i}`} className={r.scenario === "UNIVERSAL_CLOSE" ? "hl" : undefined}>
                        <td>{sp}</td>
                        <td>{r.h}</td>
                        <td>{r.scenario}</td>
                        <td>{pct(r.p_min_pos)}</td>
                        <td>{pct(r.p_min_8040)}</td>
                      </tr>
                    )),
                )}
              </tbody>
            </table>
          </>
        )}
      </div>
    </div>
  );
}
