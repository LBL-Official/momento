import { useEffect, useMemo, useState } from "react";

type Gate = { status: string; n?: number; items?: string[]; fails?: string[] };
type SplitStats = {
  n?: number;
  mean_h?: number | null;
  median_h?: number | null;
  std_h?: number | null;
  corner_zero?: number | null;
  corner_one?: number | null;
  interior_rate?: number | null;
};
type InteriorFam = {
  TRAIN?: SplitStats;
  VALIDATION?: SplitStats;
  OOS?: SplitStats;
  stability?: string;
};
type ModelRow = {
  model: string;
  split: string;
  n?: number;
  auc?: number | null;
  brier?: number | null;
  logloss?: number | null;
  ece?: number | null;
  layer?: string;
};
type Surface = {
  split: string;
  family: string;
  price_lo: number;
  price_hi: number;
  clock: string;
  n: number;
  mean_h: number;
  median_h: number;
  interior_rate: number;
  emp_settle?: number | null;
};
type Slice = {
  n: number;
  mean_price?: number;
  emp_settle?: number | null;
  mean_h_N1?: number;
  mean_h_N4?: number;
  mean_h_E2?: number;
};
type Contrast = {
  split: string;
  band: string;
  early?: Slice;
  late?: Slice;
  leading?: Slice;
  trailing?: Slice;
};
type Curve = {
  trade_id: string;
  split: string;
  current_price: number | null;
  period: number | null;
  game_seconds_remaining: number | null;
  score_differential_from_A1: number | null;
  p_terminal: number | null;
  h_grid: number[];
  V_N1: number[];
  V_N2: number[];
  V_N3: number[];
  V_N4: number[];
  h_N1: number | null;
  h_N2: number | null;
  h_N3: number | null;
  h_N4: number | null;
};
type PathPt = {
  poss: number | null;
  pidx: number | null;
  clock: string | null;
  period: number | null;
  price: number | null;
  secs: number | null;
  diff: number | null;
  p_terminal: number | null;
  path_bin_end: string | null;
  h_N1: number | null;
  h_N2: number | null;
  h_N3: number | null;
  h_N4: number | null;
  h_E2: number | null;
};
type Example = {
  trade_id: string;
  event_id: string;
  split: string;
  n: number;
  path: PathPt[];
};
type HistBin = { h: number; n: number };
type Dash = {
  program: string;
  banner: string;
  schema_version: string;
  created_utc: string;
  verdict: Record<string, string>;
  gates: Record<string, Gate>;
  counts: { rows: number; trades: number; path_valid_end: number; path_invalid_end: number; splits: Record<string, { rows: number; trades: number }> };
  questions: Record<string, string | Record<string, number | null> | null>;
  selected: Record<string, Record<string, string | number | boolean | null>>;
  accounting: Record<string, string | number>;
  interior: Record<string, InteriorFam>;
  local: { overall?: { median?: number; p90?: number; max?: number }; flip_01_rate?: number | null; families?: Record<string, { overall?: { median?: number; p90?: number; max?: number }; flip_01_rate?: number | null }> };
  temporal: Record<string, Record<string, { median_abs_dh?: number; p90_abs_dh?: number; mean_abs_dh?: number; reversals?: number; n_pairs?: number }>>;
  path: {
    empirical: Record<string, Record<string, { n: number; rates: Record<string, number | null> }>>;
    modeled_mean: Record<string, Record<string, { rates: Record<string, number>; sum: number }>>;
    status: string;
  };
  models: ModelRow[];
  surfaces: Surface[];
  contrast: Contrast[];
  curves: Curve[];
  histograms: Record<string, Record<string, HistBin[]>>;
  examples: Example[];
  layers: Record<string, string>;
  oos_results: { headline: string };
};

const TABS = [
  "Overview",
  "Data Integrity",
  "Path Distributions",
  "Predictive Models",
  "Objective Families",
  "Exposure Surface",
  "Interior Solutions",
  "Stability",
  "Trade Paths",
  "OOS Results",
  "Verdict",
] as const;

function fmt(v: number | null | undefined, d = 3): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toFixed(d);
}
function gradeClass(s: string): string {
  if (s === "PASS" || s === "YES") return "pass";
  if (s === "FAIL" || s === "NOT AUTHORIZED" || s === "NO") return "neg";
  if (s === "WARNING" || s === "UNOBSERVED" || s === "PARTIAL" || s === "INCONCLUSIVE") return "warn";
  return "muted";
}
function heatColor(h: number): string {
  const t = Math.max(0, Math.min(1, h));
  const r = Math.round(224 * (1 - t) + 61 * t);
  const g = Math.round(93 * (1 - t) + 186 * t);
  const b = Math.round(93 * (1 - t) + 122 * t);
  return `rgb(${r},${g},${b})`;
}

function Poly({
  values,
  color,
  min,
  max,
}: {
  values: (number | null)[];
  color: string;
  min: number;
  max: number;
}) {
  const w = 800;
  const h = 200;
  const pts = values
    .map((v, i) => {
      if (v === null || v === undefined) return null;
      const x = (i / Math.max(1, values.length - 1)) * w;
      const y = h - ((v - min) / Math.max(1e-9, max - min)) * (h - 16) - 8;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .filter(Boolean)
    .join(" ");
  return <polyline fill="none" stroke={color} strokeWidth="1.6" points={pts} />;
}

export default function App() {
  const [dash, setDash] = useState<Dash | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tab, setTab] = useState<(typeof TABS)[number]>("Overview");
  const [exIdx, setExIdx] = useState(0);
  const [split, setSplit] = useState("OOS");
  const [fam, setFam] = useState("N1");
  const [curveIdx, setCurveIdx] = useState(0);
  const [band, setBand] = useState("price_60");
  const [hz, setHz] = useState("end");

  useEffect(() => {
    fetch("/data/dashboard.json")
      .then((r) => {
        if (!r.ok) throw new Error(`dashboard.json ${r.status}`);
        return r.json();
      })
      .then(setDash)
      .catch((e: Error) => setErr(e.message));
  }, []);

  const ex = dash?.examples[exIdx];
  const curve = dash?.curves[curveIdx];
  const curveMin = useMemo(() => {
    if (!curve) return 0;
    const all = [...curve.V_N1, ...curve.V_N2, ...curve.V_N3, ...curve.V_N4];
    return Math.min(...all);
  }, [curve]);
  const curveMax = useMemo(() => {
    if (!curve) return 1;
    const all = [...curve.V_N1, ...curve.V_N2, ...curve.V_N3, ...curve.V_N4];
    return Math.max(...all);
  }, [curve]);

  if (err) return <div className="err">Failed to load static artifact: {err}</div>;
  if (!dash) return <div className="err">Loading DRE V3 research artifact…</div>;

  const hist = (dash.histograms[fam] || {})[split] || [];
  const maxBar = Math.max(1, ...hist.map((b) => b.n));
  const clocks = ["early", "mid", "late"] as const;
  const prices = [...new Set(dash.surfaces.filter((s) => s.split === split && s.family === fam).map((s) => s.price_lo))].sort((a, b) => a - b);

  return (
    <div className="app">
      <div className="banner">{dash.banner}</div>
      <div className="top">
        <div className="brand">
          DRE V3
          <small>Nonlinear exposure-value experiment · {dash.schema_version}</small>
        </div>
        <div className="ctrl">
          <label>Example trade</label>
          <select value={exIdx} onChange={(e) => setExIdx(Number(e.target.value))}>
            {dash.examples.map((e, i) => (
              <option key={e.trade_id} value={i}>
                {e.split} · {e.event_id}
              </option>
            ))}
          </select>
        </div>
        <div className="ctrl">
          <label>Split</label>
          <select value={split} onChange={(e) => setSplit(e.target.value)}>
            <option>TRAIN</option>
            <option>VALIDATION</option>
            <option>OOS</option>
          </select>
        </div>
        <div className="ctrl">
          <label>Family</label>
          <select value={fam} onChange={(e) => setFam(e.target.value)}>
            <option>N1</option>
            <option>N2</option>
            <option>N3</option>
            <option>N4</option>
            <option>E2</option>
            <option>E3</option>
          </select>
        </div>
      </div>
      <div className="tabs">
        {TABS.map((t) => (
          <button key={t} className={tab === t ? "on" : ""} onClick={() => setTab(t)}>
            {t}
          </button>
        ))}
      </div>
      <div className="main">
        {tab === "Overview" && (
          <>
            <div>
              <span className="layer obs">OBSERVED DATA</span>
              <span className="layer mod">MODELED PROBABILITIES</span>
              <span className="layer th">THEORETICAL EXPOSURE</span>
            </div>
            <h2>Headline</h2>
            <div className="row">
              <div className="card">
                <div className="k">Nonlinear-exposure hypothesis</div>
                <div className={`v ${gradeClass(dash.verdict.HEADLINE)}`}>{dash.verdict.HEADLINE}</div>
              </div>
              <div className="card">
                <div className="k">Live deployment</div>
                <div className="v neg">NOT AUTHORIZED</div>
              </div>
              <div className="card">
                <div className="k">Panel rows</div>
                <div className="v">{dash.counts.rows}</div>
              </div>
              <div className="card">
                <div className="k">Trades</div>
                <div className="v">{dash.counts.trades}</div>
              </div>
            </div>
            <h2>Scientific questions</h2>
            <table>
              <thead>
                <tr>
                  <th>Q</th>
                  <th>Answer</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(dash.questions)
                  .filter(([k]) => k.startsWith("Q"))
                  .map(([k, val]) => (
                    <tr key={k}>
                      <td>{k}</td>
                      <td className={gradeClass(String(val))}>{String(val)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
            <p className="caption">{dash.layers.THEORETICAL_EXPOSURE}. Candle path ≠ actual fill.</p>
          </>
        )}

        {tab === "Data Integrity" && (
          <>
            <h2>Gates</h2>
            <div className="row">
              {Object.entries(dash.gates).map(([k, g]) => (
                <div className="card" key={k}>
                  <div className="k">{k}</div>
                  <div className={`v ${gradeClass(g.status)}`}>{g.status}</div>
                </div>
              ))}
            </div>
            <h2>Frozen universe / splits</h2>
            <table>
              <thead>
                <tr>
                  <th>Split</th>
                  <th>Rows</th>
                  <th>Trades</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(dash.counts.splits).map(([k, v]) => (
                  <tr key={k}>
                    <td>{k}</td>
                    <td>{v.rows}</td>
                    <td>{v.trades}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="caption">
              Path-valid to end: {dash.counts.path_valid_end}. Last-possession / missing forward path: {dash.counts.path_invalid_end}. FIRST-80 remains 1230 / 910 / 320 / 0.
            </p>
          </>
        )}

        {tab === "Path Distributions" && (
          <>
            <h2>Observed exclusive bins</h2>
            <span className="layer obs">OBSERVED DATA</span>
            <div className="ctrl">
              <label>Horizon</label>
              <select value={hz} onChange={(e) => setHz(e.target.value)}>
                <option value="5">5 possessions</option>
                <option value="10">10 possessions</option>
                <option value="end">to game end</option>
              </select>
            </div>
            <table>
              <thead>
                <tr>
                  <th>Bin</th>
                  <th>TRAIN</th>
                  <th>VALIDATION</th>
                  <th>OOS</th>
                </tr>
              </thead>
              <tbody>
                {["EXTREME_DOWN", "SEVERE_DOWN", "MODERATE_DOWN", "STABLE", "MODERATE_REC", "STRONG_REC", "EXTREME_REC"].map((b) => (
                  <tr key={b}>
                    <td>{b}</td>
                    {(["TRAIN", "VALIDATION", "OOS"] as const).map((s) => (
                      <td key={s}>{fmt(((dash.path.empirical[hz] || {})[s] || { rates: {} }).rates[b])}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            <h2>Modeled mean probabilities</h2>
            <span className="layer mod">MODELED PROBABILITIES</span>
            <table>
              <thead>
                <tr>
                  <th>Bin</th>
                  <th>TRAIN</th>
                  <th>VALIDATION</th>
                  <th>OOS</th>
                </tr>
              </thead>
              <tbody>
                {["EXTREME_DOWN", "SEVERE_DOWN", "MODERATE_DOWN", "STABLE", "MODERATE_REC", "STRONG_REC", "EXTREME_REC"].map((b) => (
                  <tr key={b}>
                    <td>{b}</td>
                    {(["TRAIN", "VALIDATION", "OOS"] as const).map((s) => (
                      <td key={s}>{fmt((((dash.path.modeled_mean[hz] || {})[s] || { rates: {} }).rates || {})[b])}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="caption">Downside-first exclusive bins. Normalization status: {dash.path.status}. Candle-path outcomes, not fills.</p>
          </>
        )}

        {tab === "Predictive Models" && (
          <>
            <span className="layer mod">MODELED PROBABILITIES</span>
            <p className="caption">Predictive information is not an exposure policy. TRAIN fit only; OOS is evaluation.</p>
            <table>
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Split</th>
                  <th>n</th>
                  <th>AUC</th>
                  <th>Brier</th>
                  <th>Logloss</th>
                  <th>ECE</th>
                </tr>
              </thead>
              <tbody>
                {dash.models
                  .filter((m) => m.split === split)
                  .map((m) => (
                    <tr key={`${m.model}-${m.split}`}>
                      <td>{m.model}</td>
                      <td>{m.split}</td>
                      <td>{m.n}</td>
                      <td>{fmt(m.auc)}</td>
                      <td>{fmt(m.brier)}</td>
                      <td>{fmt(m.logloss)}</td>
                      <td>{fmt(m.ece)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </>
        )}

        {tab === "Objective Families" && (
          <>
            <span className="layer th">THEORETICAL EXPOSURE</span>
            <h2>VALIDATION-selected parameters</h2>
            <table>
              <thead>
                <tr>
                  <th>Family</th>
                  <th>Selection</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(dash.selected).map(([k, rec]) => (
                  <tr key={k}>
                    <td>{k}</td>
                    <td>{Object.entries(rec).map(([kk, vv]) => `${kk}=${String(vv)}`).join(" · ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="caption">
              W0={String(dash.accounting.W0_cents)}¢ · X_yes={String(dash.accounting.X_yes)} · X_no={String(dash.accounting.X_no)} · {String(dash.accounting.label)}
            </p>
            <h2>Value(h) curves — representative states</h2>
            {dash.curves.length > 0 && (
              <div className="ctrl">
                <label>State</label>
                <select value={curveIdx} onChange={(e) => setCurveIdx(Number(e.target.value))}>
                  {dash.curves.map((c, i) => (
                    <option key={`${c.trade_id}-${i}`} value={i}>
                      {c.split} · {fmt(c.current_price, 1)}¢ · Q{c.period} · p={fmt(c.p_terminal)}
                    </option>
                  ))}
                </select>
              </div>
            )}
            {curve && (
              <>
                <div className="chart">
                  <svg viewBox="0 0 800 200" preserveAspectRatio="none">
                    <Poly values={curve.V_N1} color="#c8a25a" min={curveMin} max={curveMax} />
                    <Poly values={curve.V_N2} color="#5aa0c8" min={curveMin} max={curveMax} />
                    <Poly values={curve.V_N3} color="#3dba7a" min={curveMin} max={curveMax} />
                    <Poly values={curve.V_N4} color="#e05d5d" min={curveMin} max={curveMax} />
                  </svg>
                </div>
                <p className="caption">
                  Gold N1 · Blue N2 · Green N3 · Red N4. h* N1={fmt(curve.h_N1, 2)} N2={fmt(curve.h_N2, 2)} N3={fmt(curve.h_N3, 2)} N4={fmt(curve.h_N4, 2)}.
                  Look for a sharp interior peak, a flat plateau, or a corner.
                </p>
              </>
            )}
          </>
        )}

        {tab === "Exposure Surface" && (
          <>
            <span className="layer th">THEORETICAL EXPOSURE</span>
            <h2>h* histogram — {fam} / {split}</h2>
            <div className="bars">
              {hist.map((b) => {
                const cls = b.h === 0 ? "zero" : b.h === 1 ? "one" : "int";
                return <div key={b.h} className={`bar ${cls}`} style={{ height: `${(100 * b.n) / maxBar}%` }} title={`${b.h}: ${b.n}`} />;
              })}
            </div>
            <p className="caption">Red = h=0 · Gold = interior · Green = h=1. Theoretical retained exposure, not executed size.</p>
            <h2>CurrentPrice × GameClock heatmap — mean h*</h2>
            <div className="heat">
              <div className="hd" />
              {clocks.map((c) => (
                <div className="hd" key={c}>
                  {c}
                </div>
              ))}
              {prices.map((plo) => (
                <RowHeat key={plo} plo={plo} clocks={clocks} cells={dash.surfaces.filter((s) => s.split === split && s.family === fam && s.price_lo === plo)} />
              ))}
            </div>
            <h2>Same-price state contrast</h2>
            <div className="ctrl">
              <label>Price band</label>
              <select value={band} onChange={(e) => setBand(e.target.value)}>
                <option value="price_60">60¢</option>
                <option value="price_50">50¢</option>
                <option value="price_70">70¢</option>
              </select>
            </div>
            <table>
              <thead>
                <tr>
                  <th>Slice</th>
                  <th>n</th>
                  <th>emp settle</th>
                  <th>mean h N1</th>
                  <th>mean h N4</th>
                  <th>mean h E2</th>
                </tr>
              </thead>
              <tbody>
                {dash.contrast
                  .filter((c) => c.split === split && c.band === band)
                  .flatMap((c) =>
                    (["early", "late", "leading", "trailing"] as const).map((lab) => {
                      const sl = c[lab] || { n: 0 };
                      return (
                        <tr key={lab}>
                          <td>{lab}</td>
                          <td>{sl.n}</td>
                          <td>{fmt(sl.emp_settle)}</td>
                          <td>{fmt(sl.mean_h_N1)}</td>
                          <td>{fmt(sl.mean_h_N4)}</td>
                          <td>{fmt(sl.mean_h_E2)}</td>
                        </tr>
                      );
                    }),
                  )}
              </tbody>
            </table>
          </>
        )}

        {tab === "Interior Solutions" && (
          <>
            <h2>Interior rates by family</h2>
            <table>
              <thead>
                <tr>
                  <th>Family</th>
                  <th>Split</th>
                  <th>n</th>
                  <th>mean h</th>
                  <th>median h</th>
                  <th>P(0)</th>
                  <th>P(1)</th>
                  <th>Interior</th>
                  <th>Stability</th>
                </tr>
              </thead>
              <tbody>
                {["N1", "N2", "N3", "N4", "N2_LINEAR", "E2", "E3"].map((f) => {
                  const rec = dash.interior[f] || {};
                  return (["TRAIN", "VALIDATION", "OOS"] as const).map((s) => {
                    const st = rec[s] || {};
                    return (
                      <tr key={`${f}-${s}`}>
                        <td>{f}</td>
                        <td>{s}</td>
                        <td>{st.n ?? "—"}</td>
                        <td>{fmt(st.mean_h)}</td>
                        <td>{fmt(st.median_h)}</td>
                        <td>{fmt(st.corner_zero)}</td>
                        <td>{fmt(st.corner_one)}</td>
                        <td>{fmt(st.interior_rate)}</td>
                        <td>{s === "OOS" ? rec.stability : ""}</td>
                      </tr>
                    );
                  });
                })}
              </tbody>
            </table>
            <p className="caption">Primary endpoint. TRAIN interior that collapses OOS is failure. Corners are an allowed scientific result.</p>
          </>
        )}

        {tab === "Stability" && (
          <>
            <h2>Local perturbation of h*</h2>
            <div className="row">
              <div className="card">
                <div className="k">N1 median |Δh|</div>
                <div className="v">{fmt(dash.local.overall?.median)}</div>
              </div>
              <div className="card">
                <div className="k">N1 P90</div>
                <div className="v">{fmt(dash.local.overall?.p90)}</div>
              </div>
              <div className="card">
                <div className="k">N1 flip 0↔1</div>
                <div className="v">{fmt(dash.local.flip_01_rate)}</div>
              </div>
              <div className="card">
                <div className="k">N4 median |Δh|</div>
                <div className="v">{fmt(dash.local.families?.N4?.overall?.median)}</div>
              </div>
            </div>
            <h2>Temporal |Δh*| between possessions</h2>
            <table>
              <thead>
                <tr>
                  <th>Family</th>
                  <th>Split</th>
                  <th>pairs</th>
                  <th>mean |Δh|</th>
                  <th>median</th>
                  <th>P90</th>
                  <th>reversals</th>
                </tr>
              </thead>
              <tbody>
                {["N1", "N2", "N3", "N4", "E2"].map((f) =>
                  (["TRAIN", "VALIDATION", "OOS"] as const).map((s) => {
                    const st = (dash.temporal[f] || {})[s] || {};
                    return (
                      <tr key={`${f}-${s}`}>
                        <td>{f}</td>
                        <td>{s}</td>
                        <td>{st.n_pairs ?? "—"}</td>
                        <td>{fmt(st.mean_abs_dh)}</td>
                        <td>{fmt(st.median_abs_dh)}</td>
                        <td>{fmt(st.p90_abs_dh)}</td>
                        <td>{st.reversals ?? "—"}</td>
                      </tr>
                    );
                  }),
                )}
              </tbody>
            </table>
            <p className="caption">Primary h* is unsmoothed. A 1¢ flip from 1 to 0 is instability, not an execution signal.</p>
          </>
        )}

        {tab === "Trade Paths" && ex && (
          <>
            <span className="layer th">THEORETICAL EXPOSURE</span>
            <h2>
              {ex.event_id} · {ex.split} · {ex.n} possessions
            </h2>
            <div className="chart">
              <svg viewBox="0 0 800 200" preserveAspectRatio="none">
                <Poly values={ex.path.map((p) => p.price)} color="#c8a25a" min={0} max={100} />
                <Poly values={ex.path.map((p) => (p.h_N1 == null ? null : p.h_N1 * 100))} color="#5aa0c8" min={0} max={100} />
                <Poly values={ex.path.map((p) => (p.h_N4 == null ? null : p.h_N4 * 100))} color="#e05d5d" min={0} max={100} />
              </svg>
            </div>
            <p className="caption">Gold = current yes-bid ¢. Blue = 100×h* N1. Red = 100×h* N4. Not an order path.</p>
            <table>
              <thead>
                <tr>
                  <th>poss</th>
                  <th>clock</th>
                  <th>Q</th>
                  <th>price</th>
                  <th>score</th>
                  <th>p_term</th>
                  <th>path bin</th>
                  <th>h N1</th>
                  <th>h N4</th>
                  <th>h E2</th>
                </tr>
              </thead>
              <tbody>
                {ex.path.map((p, i) => (
                  <tr key={i}>
                    <td>{p.poss}</td>
                    <td>{p.clock}</td>
                    <td>{p.period}</td>
                    <td>{fmt(p.price, 1)}</td>
                    <td>{fmt(p.diff, 1)}</td>
                    <td>{fmt(p.p_terminal)}</td>
                    <td>{p.path_bin_end}</td>
                    <td>{fmt(p.h_N1, 2)}</td>
                    <td>{fmt(p.h_N4, 2)}</td>
                    <td>{fmt(p.h_E2, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {tab === "OOS Results" && (
          <>
            <h2>OOS interior vs baselines</h2>
            <table>
              <thead>
                <tr>
                  <th>Family</th>
                  <th>mean h</th>
                  <th>interior</th>
                  <th>P(0)</th>
                  <th>P(1)</th>
                  <th>stability</th>
                </tr>
              </thead>
              <tbody>
                {["N1", "N2", "N3", "N4", "E2", "E3"].map((f) => {
                  const st = (dash.interior[f] || {}).OOS || {};
                  return (
                    <tr key={f}>
                      <td>{f}</td>
                      <td>{fmt(st.mean_h)}</td>
                      <td>{fmt(st.interior_rate)}</td>
                      <td>{fmt(st.corner_zero)}</td>
                      <td>{fmt(st.corner_one)}</td>
                      <td>{(dash.interior[f] || {}).stability}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="caption">Headline: {dash.oos_results.headline}. E2 is frozen DRE V2 target delta. Not an executable policy.</p>
          </>
        )}

        {tab === "Verdict" && (
          <>
            <h2>Research verdict</h2>
            <div className="row">
              {Object.entries(dash.verdict).map(([k, val]) => (
                <div className="card" key={k}>
                  <div className="k">{k.replaceAll("_", " ")}</div>
                  <div className={`v ${gradeClass(val)}`}>{val}</div>
                </div>
              ))}
            </div>
            <p className="caption">
              Allowed tokens only. Execution evidence is UNOBSERVED. Live deployment is NOT AUTHORIZED. Theoretical exposure ≠ executed exposure.
            </p>
          </>
        )}
      </div>
    </div>
  );
}

function RowHeat({
  plo,
  clocks,
  cells,
}: {
  plo: number;
  clocks: readonly string[];
  cells: Surface[];
}) {
  return (
    <>
      <div className="hd">
        {plo}–{plo + 5}
      </div>
      {clocks.map((c) => {
        const cell = cells.find((x) => x.clock === c);
        if (!cell) return <div className="cell" key={c}>—</div>;
        return (
          <div className="cell" key={c} style={{ background: heatColor(cell.mean_h), color: "#0b0d10" }}>
            {fmt(cell.mean_h, 2)}
          </div>
        );
      })}
    </>
  );
}
