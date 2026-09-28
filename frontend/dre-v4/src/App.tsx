import { useEffect, useMemo, useState } from "react";

type Gate = { status: string; n?: number; items?: string[]; fails?: string[]; observed?: unknown };
type SliceSide = {
  n?: number;
  trades?: number;
  games?: number;
  p_settle?: number | null;
  p_rec10?: number | null;
  p_det10?: number | null;
  dd?: { median?: number | null; mean?: number | null; p10?: number | null; p90?: number | null };
  ue?: { median?: number | null; mean?: number | null };
  path_class?: Record<string, number>;
};
type Contrast = {
  name?: string;
  a?: SliceSide;
  b?: SliceSide;
  delta?: Record<string, number | null>;
  adequate?: boolean;
  material?: boolean;
  excluded_reason?: string | null;
};
type ModelRow = {
  family?: string;
  target?: string;
  kind?: string;
  split: string;
  n?: number;
  auc?: number | null;
  brier?: number | null;
  logloss?: number | null;
};
type PathPt = {
  poss: number | null;
  pidx: number | null;
  clock: string | null;
  period: number | null;
  elapsed: number | null;
  gsr: number | null;
  age: number | null;
  price: number | null;
  bid: number | null;
  ask: number | null;
  diff: number | null;
  regime: string | null;
  path_class_5: string | null;
  dd_5: number | null;
  ue_5: number | null;
  order_10_5: string | null;
  stale: number | null;
};
type Example = {
  trade_id: string;
  event_id: string;
  split: string;
  n: number;
  entry_price: number | null;
  entry_clock: string | null;
  y_settle_yes: number | null;
  unresolved: boolean;
  path: PathPt[];
  label: string;
};
type ClockBlock = {
  field?: string;
  note?: string;
  clock_horizon_basis?: string;
  age_seconds?: Record<string, number>;
  position_age_wall_s?: Record<string, number>;
  stale_share?: number;
  elapsed?: Record<string, number>;
  remaining?: Record<string, number>;
  possession_index?: Record<string, number>;
  possessions_since_entry?: Record<string, number>;
};
type Dash = {
  program: string;
  banner: string;
  schema_version: string;
  created_utc: string;
  research_date: string;
  verdict: Record<string, string>;
  questions: Record<string, string>;
  gates: Record<string, Gate>;
  counts: {
    rows: number;
    trades: number;
    games?: number;
    splits: Record<string, { rows: number; trades: number; games?: number }>;
  };
  universe: {
    universe: number;
    panel_eligible: number;
    panel_rows: number;
    model_eligible_rows: number;
    path_label_eligible_end: number;
    unresolved_n: number;
    unresolved?: unknown;
    note?: string;
  };
  clocks: { wall: ClockBlock; game: ClockBlock; possession: ClockBlock; not_collapsed?: boolean };
  path: {
    empirical: Record<string, Record<string, { n: number; rates: Record<string, number | null> }>>;
    status: string;
    classes: string[];
  };
  regimes: Record<string, Record<string, number | null>>;
  models: ModelRow[];
  incremental: Record<string, { d_auc?: number | null; d_brier?: number | null; auc?: number | null; b0_auc?: number | null }>;
  matched: {
    primary_spec?: Record<string, number | string>;
    primary_oos_early_late_60?: Contrast;
    oos_60_5_slices?: Record<string, Contrast>;
    oos_nn_1c_60?: { n?: number; early_vs_late?: Contrast };
    robust_early_late_60?: Record<string, Contrast>;
    n_excluded?: number;
    excluded_head?: Array<Record<string, string | number>>;
    label?: string;
  };
  transitions: {
    note?: string;
    by_split?: Record<string, Record<string, { regimes: string[]; probs: Array<Array<number | null>>; n_transitions: number }>>;
  };
  robustness: {
    seasonal?: Record<string, Contrast>;
    concentration?: { n_rows?: number; n_games?: number; top_game_share?: number | null; top5_share?: number | null; top_event?: string | null };
    persist_direction?: boolean;
    concentrated?: boolean;
    bin_agree?: number;
  };
  bootstrap?: { status?: string; n_games?: number; settle_delta?: { mean?: number; p05?: number; p95?: number }; median_dd_delta?: { mean?: number; p05?: number; p95?: number } };
  negative_control?: { d_auc?: number | null; auc?: number | null; b0_auc?: number | null };
  examples: Example[];
  layers: Record<string, string>;
  limitations: string[];
};

const TABS = [
  "Overview",
  "Research Question",
  "State Panel",
  "Three Clocks",
  "Price-Matched States",
  "Forward Distributions",
  "Path Classes",
  "Transition Matrices",
  "Model Comparison",
  "Robustness",
  "Negative Controls",
  "Trade Explorer",
  "Limitations",
  "Verdict",
] as const;

function fmt(v: number | null | undefined, d = 3): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toFixed(d);
}
function gradeClass(s: string): string {
  if (s === "PASS" || s === "YES" || s === "ROBUST") return "pass";
  if (s === "FAIL" || s === "NOT AUTHORIZED" || s === "NO") return "neg";
  if (s === "WARNING" || s === "UNOBSERVED" || s === "PARTIAL" || s === "INCONCLUSIVE") return "warn";
  return "muted";
}
function heat(p: number | null | undefined): string {
  if (p === null || p === undefined || Number.isNaN(p)) return "transparent";
  const t = Math.max(0, Math.min(1, p));
  const r = Math.round(36 + 188 * t);
  const g = Math.round(40 + 20 * (1 - t));
  const b = Math.round(48);
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
  const [hz, setHz] = useState("5");
  const [pair, setPair] = useState("early_vs_late");
  const [th, setTh] = useState("1");

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
  const prices = useMemo(() => (ex ? ex.path.map((p) => p.price) : []), [ex]);
  const ages = useMemo(() => (ex ? ex.path.map((p) => p.age) : []), [ex]);
  const gsr = useMemo(() => (ex ? ex.path.map((p) => p.gsr) : []), [ex]);

  if (err) return <div className="err">Failed to load static artifact: {err}</div>;
  if (!dash) return <div className="err">Loading DRE V4 research artifact…</div>;

  const prim = dash.matched.primary_oos_early_late_60 || {};
  const slices = dash.matched.oos_60_5_slices || {};
  const trans = ((dash.transitions.by_split || {})[split] || {})[th];
  const pathRates = (dash.path.empirical[hz] || {})[split] || { n: 0, rates: {} };
  const maxBar = Math.max(1, ...dash.path.classes.map((c) => pathRates.rates[c] || 0));

  return (
    <div className="app">
      <div className="banner">{dash.banner}</div>
      <div className="top">
        <div className="brand">
          DRE V4
          <small>State-transition distributions · {dash.schema_version} · {dash.research_date}</small>
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
          <label>Horizon</label>
          <select value={hz} onChange={(e) => setHz(e.target.value)}>
            <option value="1">1 possession</option>
            <option value="3">3 possessions</option>
            <option value="5">5 possessions</option>
            <option value="10">10 possessions</option>
            <option value="end">to end</option>
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
              <span className="layer mod">MODEL OUTPUT</span>
              <span className="layer th">THEORETICAL INFERENCE</span>
              <span className="layer un">UNOBSERVED EXECUTION</span>
            </div>
            <div className="note">LIVE DEPLOYMENT: NOT AUTHORIZED · CANDLE PATH ≠ ACTUAL FILL · FORWARD DISTRIBUTION ≠ TRADABLE EDGE</div>
            <h2>Headline</h2>
            <div className="row">
              <div className="card">
                <div className="k">Price-matched state asymmetry</div>
                <div className={`v ${gradeClass(dash.verdict.PRICE_MATCHED_STATE_ASYMMETRY || dash.verdict.HEADLINE)}`}>
                  {dash.verdict.PRICE_MATCHED_STATE_ASYMMETRY || dash.verdict.HEADLINE}
                </div>
              </div>
              <div className="card">
                <div className="k">Live deployment</div>
                <div className="v neg">NOT AUTHORIZED</div>
              </div>
              <div className="card">
                <div className="k">Universe</div>
                <div className="v">{dash.universe.universe}</div>
              </div>
              <div className="card">
                <div className="k">Panel rows</div>
                <div className="v">{dash.counts.rows}</div>
              </div>
              <div className="card">
                <div className="k">Unresolved</div>
                <div className="v">{dash.universe.unresolved_n}</div>
              </div>
            </div>
            <p className="caption">{dash.layers.UNOBSERVED_EXECUTION}</p>
          </>
        )}

        {tab === "Research Question" && (
          <>
            <h2>Scientific question</h2>
            <p className="caption">
              Conditional on the current Kalshi market state, do different observed basketball states produce materially different
              forward distributions of candle-path movement and terminal outcomes?
            </p>
            <div className="note">PREDICTIVE STATE ≠ THEORETICAL EXPOSURE POLICY ≠ EXECUTABLE TRADING POLICY</div>
            <table>
              <thead>
                <tr>
                  <th>Q</th>
                  <th>Answer</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(dash.questions).map(([k, val]) => (
                  <tr key={k}>
                    <td>{k}</td>
                    <td className={gradeClass(String(val))}>{String(val)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="caption">Q10 default is NO. A future execution experiment is required before any trading claim.</p>
          </>
        )}

        {tab === "State Panel" && (
          <>
            <span className="layer obs">OBSERVED DATA</span>
            <h2>Universe accounting</h2>
            <div className="row">
              <div className="card"><div className="k">Universe</div><div className="v">{dash.universe.universe}</div></div>
              <div className="card"><div className="k">Panel eligible</div><div className="v">{dash.universe.panel_eligible}</div></div>
              <div className="card"><div className="k">Model-eligible rows</div><div className="v">{dash.universe.model_eligible_rows}</div></div>
              <div className="card"><div className="k">Path-label end</div><div className="v">{dash.universe.path_label_eligible_end}</div></div>
              <div className="card"><div className="k">Unresolved</div><div className="v">{dash.universe.unresolved_n}</div></div>
            </div>
            <p className="caption">{dash.universe.note}</p>
            <h2>Gates</h2>
            <div className="row">
              {Object.entries(dash.gates).map(([k, g]) => (
                <div className="card" key={k}>
                  <div className="k">Gate {k}</div>
                  <div className={`v ${gradeClass(g.status)}`}>{g.status}</div>
                </div>
              ))}
            </div>
            <h2>Splits</h2>
            <table>
              <thead>
                <tr>
                  <th>Split</th>
                  <th>Rows</th>
                  <th>Trades</th>
                  <th>Games</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(dash.counts.splits).map(([k, v]) => (
                  <tr key={k}>
                    <td>{k}</td>
                    <td>{v.rows}</td>
                    <td>{v.trades}</td>
                    <td>{v.games ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {tab === "Three Clocks" && (
          <>
            <span className="layer obs">OBSERVED DATA</span>
            <h2>Clocks are not collapsed</h2>
            <table>
              <thead>
                <tr>
                  <th>Clock</th>
                  <th>Field</th>
                  <th>Median</th>
                  <th>P10</th>
                  <th>P90</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Wall / market age</td>
                  <td>{dash.clocks.wall.field}</td>
                  <td>{fmt(dash.clocks.wall.age_seconds?.median, 1)}</td>
                  <td>{fmt(dash.clocks.wall.age_seconds?.p10, 1)}</td>
                  <td>{fmt(dash.clocks.wall.age_seconds?.p90, 1)}</td>
                </tr>
                <tr>
                  <td>Game elapsed</td>
                  <td>{dash.clocks.game.field}</td>
                  <td>{fmt(dash.clocks.game.elapsed?.median, 1)}</td>
                  <td>{fmt(dash.clocks.game.elapsed?.p10, 1)}</td>
                  <td>{fmt(dash.clocks.game.elapsed?.p90, 1)}</td>
                </tr>
                <tr>
                  <td>Possession since entry</td>
                  <td>{dash.clocks.possession.field}</td>
                  <td>{fmt(dash.clocks.possession.possessions_since_entry?.median, 1)}</td>
                  <td>{fmt(dash.clocks.possession.possessions_since_entry?.p10, 1)}</td>
                  <td>{fmt(dash.clocks.possession.possessions_since_entry?.p90, 1)}</td>
                </tr>
              </tbody>
            </table>
            <p className="caption">
              Stale share (age ≥ 60s): {fmt(dash.clocks.wall.stale_share)}. {dash.clocks.game.note}
            </p>
          </>
        )}

        {tab === "Price-Matched States" && (
          <>
            <span className="layer th">THEORETICAL INFERENCE</span>
            <div className="note">RESEARCH DISTRIBUTION — NOT A TRADING INSTRUCTION</div>
            <h2>Primary: 5¢ bin [60,65) · early vs late · 5 possessions</h2>
            <div className="row">
              <div className="card"><div className="k">Adequate</div><div className={`v ${prim.adequate ? "pass" : "warn"}`}>{String(prim.adequate)}</div></div>
              <div className="card"><div className="k">Material</div><div className={`v ${prim.material ? "pass" : "warn"}`}>{String(prim.material)}</div></div>
              <div className="card"><div className="k">Early n / trades</div><div className="v">{prim.a?.n} / {prim.a?.trades}</div></div>
              <div className="card"><div className="k">Late n / trades</div><div className="v">{prim.b?.n} / {prim.b?.trades}</div></div>
            </div>
            <table>
              <thead>
                <tr>
                  <th>Object</th>
                  <th>Early</th>
                  <th>Late</th>
                  <th>|Δ|</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>P(settle)</td>
                  <td>{fmt(prim.a?.p_settle)}</td>
                  <td>{fmt(prim.b?.p_settle)}</td>
                  <td>{fmt(prim.delta?.p_settle)}</td>
                </tr>
                <tr>
                  <td>P(rec ≥ 10¢ / 5p)</td>
                  <td>{fmt(prim.a?.p_rec10)}</td>
                  <td>{fmt(prim.b?.p_rec10)}</td>
                  <td>{fmt(prim.delta?.p_rec10)}</td>
                </tr>
                <tr>
                  <td>P(det ≥ 10¢ / 5p)</td>
                  <td>{fmt(prim.a?.p_det10)}</td>
                  <td>{fmt(prim.b?.p_det10)}</td>
                  <td>{fmt(prim.delta?.p_det10)}</td>
                </tr>
                <tr>
                  <td>Median DD_5</td>
                  <td>{fmt(prim.a?.dd?.median, 2)}</td>
                  <td>{fmt(prim.b?.dd?.median, 2)}</td>
                  <td>{fmt(prim.delta?.median_dd, 2)}</td>
                </tr>
                <tr>
                  <td>Wasserstein(DD_5)</td>
                  <td colSpan={2}>{fmt(prim.delta?.wasserstein_dd, 2)}</td>
                  <td>{fmt(prim.delta?.ks_dd)}</td>
                </tr>
              </tbody>
            </table>
            <h2>Other OOS 60¢ slices</h2>
            <div className="ctrl">
              <label>Slice pair</label>
              <select value={pair} onChange={(e) => setPair(e.target.value)}>
                {Object.keys(slices).map((k) => (
                  <option key={k}>{k}</option>
                ))}
              </select>
            </div>
            {slices[pair] && (
              <table>
                <thead>
                  <tr>
                    <th>Side</th>
                    <th>n</th>
                    <th>trades</th>
                    <th>P(settle)</th>
                    <th>P(rec10)</th>
                    <th>P(det10)</th>
                    <th>median DD</th>
                  </tr>
                </thead>
                <tbody>
                  {(["a", "b"] as const).map((side) => {
                    const sl = slices[pair][side];
                    return (
                      <tr key={side}>
                        <td>{side}</td>
                        <td>{sl?.n}</td>
                        <td>{sl?.trades}</td>
                        <td>{fmt(sl?.p_settle)}</td>
                        <td>{fmt(sl?.p_rec10)}</td>
                        <td>{fmt(sl?.p_det10)}</td>
                        <td>{fmt(sl?.dd?.median, 2)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
            <p className="caption">Excluded slices (below min sample): {dash.matched.n_excluded}. {dash.matched.label}</p>
          </>
        )}

        {tab === "Forward Distributions" && (
          <>
            <span className="layer obs">OBSERVED DATA</span>
            <h2>Primary contrast quantile sketch</h2>
            <table>
              <thead>
                <tr>
                  <th>Quantile</th>
                  <th>Early DD_5</th>
                  <th>Late DD_5</th>
                </tr>
              </thead>
              <tbody>
                <tr><td>P10</td><td>{fmt(prim.a?.dd?.p10, 2)}</td><td>{fmt(prim.b?.dd?.p10, 2)}</td></tr>
                <tr><td>Median</td><td>{fmt(prim.a?.dd?.median, 2)}</td><td>{fmt(prim.b?.dd?.median, 2)}</td></tr>
                <tr><td>P90</td><td>{fmt(prim.a?.dd?.p90, 2)}</td><td>{fmt(prim.b?.dd?.p90, 2)}</td></tr>
                <tr><td>Mean UE_5</td><td>{fmt(prim.a?.ue?.mean, 2)}</td><td>{fmt(prim.b?.ue?.mean, 2)}</td></tr>
              </tbody>
            </table>
            <p className="caption">Observed candle-path extrema. Repeated candles are allowed. No interpolation. Not fills.</p>
          </>
        )}

        {tab === "Path Classes" && (
          <>
            <span className="layer obs">OBSERVED DATA</span>
            <h2>Exclusive path-class rates · {hz} · {split}</h2>
            <div className="bars">
              {dash.path.classes.map((c) => (
                <div key={c} className="bar" style={{ height: `${(100 * (pathRates.rates[c] || 0)) / maxBar}%` }} title={`${c}: ${fmt(pathRates.rates[c])}`} />
              ))}
            </div>
            <table>
              <thead>
                <tr>
                  <th>Class</th>
                  <th>TRAIN</th>
                  <th>VALIDATION</th>
                  <th>OOS</th>
                </tr>
              </thead>
              <tbody>
                {dash.path.classes.map((c) => (
                  <tr key={c}>
                    <td>{c}</td>
                    {(["TRAIN", "VALIDATION", "OOS"] as const).map((s) => (
                      <td key={s}>{fmt(((dash.path.empirical[hz] || {})[s] || { rates: {} }).rates[c])}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="caption">Normalization {dash.path.status}. Downside-first exclusive taxonomy. ΣP = 1.</p>
          </>
        )}

        {tab === "Transition Matrices" && (
          <>
            <span className="layer obs">OBSERVED DATA</span>
            <div className="ctrl">
              <label>Steps</label>
              <select value={th} onChange={(e) => setTh(e.target.value)}>
                <option value="1">+1 possession</option>
                <option value="3">+3 possessions</option>
                <option value="5">+5 possessions</option>
              </select>
            </div>
            <p className="caption">{dash.transitions.note}</p>
            {trans && (
              <div className="heat" style={{ gridTemplateColumns: `120px repeat(${trans.regimes.length}, 1fr)` }}>
                <div className="hd" />
                {trans.regimes.map((r) => (
                  <div className="hd" key={r}>{r}</div>
                ))}
                {trans.regimes.map((from, i) => (
                  <Row key={from} from={from} probs={trans.probs[i]} labels={trans.regimes} />
                ))}
              </div>
            )}
            <p className="caption">n transitions = {trans?.n_transitions ?? "—"}. Empirical occupancy, not a Markov proof.</p>
          </>
        )}

        {tab === "Model Comparison" && (
          <>
            <span className="layer mod">MODEL OUTPUT</span>
            <p className="caption">Nested B0–M5. TRAIN fit only. Small AUC deltas are not discoveries. The discovery bar is matched-price distributional separation.</p>
            <table>
              <thead>
                <tr>
                  <th>Family</th>
                  <th>Target</th>
                  <th>n</th>
                  <th>AUC</th>
                  <th>Brier</th>
                  <th>Logloss</th>
                </tr>
              </thead>
              <tbody>
                {dash.models
                  .filter((m) => m.split === split)
                  .map((m) => (
                    <tr key={`${m.family}-${m.target}-${m.split}`}>
                      <td>{m.family}</td>
                      <td>{m.target}</td>
                      <td>{m.n}</td>
                      <td>{fmt(m.auc)}</td>
                      <td>{fmt(m.brier)}</td>
                      <td>{fmt(m.logloss)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
            <h2>OOS incremental vs B0</h2>
            <table>
              <thead>
                <tr>
                  <th>Key</th>
                  <th>ΔAUC</th>
                  <th>ΔBrier</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(dash.incremental).map(([k, v]) => (
                  <tr key={k}>
                    <td>{k}</td>
                    <td>{fmt(v.d_auc)}</td>
                    <td>{fmt(v.d_brier)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {tab === "Robustness" && (
          <>
            <span className="layer th">THEORETICAL INFERENCE</span>
            <h2>Price-bin width at 60¢ early vs late (OOS)</h2>
            <table>
              <thead>
                <tr>
                  <th>Width</th>
                  <th>Adequate</th>
                  <th>Material</th>
                  <th>|Δ settle|</th>
                  <th>Wasserstein DD</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(dash.matched.robust_early_late_60 || {}).map(([w, sl]) => (
                  <tr key={w}>
                    <td>{w}¢</td>
                    <td>{String(sl.adequate)}</td>
                    <td>{String(sl.material)}</td>
                    <td>{fmt(sl.delta?.p_settle)}</td>
                    <td>{fmt(sl.delta?.wasserstein_dd, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <h2>Seasonal OOS slices</h2>
            <table>
              <thead>
                <tr>
                  <th>Window</th>
                  <th>Adequate</th>
                  <th>Material</th>
                  <th>|Δ settle|</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(dash.robustness.seasonal || {}).map(([k, sl]) => (
                  <tr key={k}>
                    <td>{k}</td>
                    <td>{String(sl.adequate)}</td>
                    <td>{String(sl.material)}</td>
                    <td>{fmt(sl.delta?.p_settle)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <h2>Concentration / bootstrap</h2>
            <div className="row">
              <div className="card"><div className="k">Top game share</div><div className="v">{fmt(dash.robustness.concentration?.top_game_share)}</div></div>
              <div className="card"><div className="k">Top-5 share</div><div className="v">{fmt(dash.robustness.concentration?.top5_share)}</div></div>
              <div className="card"><div className="k">Bootstrap settle Δ</div><div className="v">{fmt(dash.bootstrap?.settle_delta?.mean)}</div></div>
              <div className="card"><div className="k">P05–P95</div><div className="v">{fmt(dash.bootstrap?.settle_delta?.p05)} / {fmt(dash.bootstrap?.settle_delta?.p95)}</div></div>
            </div>
            <p className="caption">Direction persist={String(dash.robustness.persist_direction)} · concentrated={String(dash.robustness.concentrated)} · bin_agree={String(dash.robustness.bin_agree)}</p>
          </>
        )}

        {tab === "Negative Controls" && (
          <>
            <span className="layer mod">MODEL OUTPUT</span>
            <h2>Price-dominated 40-cross (y_min_le_40_k5)</h2>
            <div className="row">
              <div className="card"><div className="k">B0 AUC</div><div className="v">{fmt(dash.negative_control?.b0_auc)}</div></div>
              <div className="card"><div className="k">M3 AUC</div><div className="v">{fmt(dash.negative_control?.auc)}</div></div>
              <div className="card"><div className="k">ΔAUC M3−B0</div><div className="v">{fmt(dash.negative_control?.d_auc)}</div></div>
            </div>
            <p className="caption">
              A small incremental lift is a useful negative result: price already dominates some short-horizon objects.
              That is not a failure of DRE V4.
            </p>
          </>
        )}

        {tab === "Trade Explorer" && ex && (
          <>
            <span className="layer obs">OBSERVED DATA</span>
            <div className="note">OBSERVED CANDLE PATH — NOT FILL HISTORY</div>
            <h2>
              {ex.event_id} · {ex.split} · {ex.n} possessions · entry {fmt(ex.entry_price, 1)}¢
            </h2>
            <div className="chart">
              <svg viewBox="0 0 800 200" preserveAspectRatio="none">
                <Poly values={prices} color="#c8a25a" min={0} max={100} />
                <Poly values={gsr.map((v) => (v == null ? null : (v / 2880) * 100))} color="#5aa0c8" min={0} max={100} />
                <Poly values={ages.map((v) => (v == null ? null : Math.min(100, v)))} color="#e05d5d" min={0} max={100} />
              </svg>
            </div>
            <p className="caption">Gold = yes-bid ¢. Blue = remaining clock scaled. Red = market age (capped 100s). Not an order path.</p>
            <table>
              <thead>
                <tr>
                  <th>poss</th>
                  <th>clock</th>
                  <th>Q</th>
                  <th>price</th>
                  <th>age</th>
                  <th>score</th>
                  <th>regime</th>
                  <th>path_5</th>
                  <th>DD5</th>
                  <th>order</th>
                </tr>
              </thead>
              <tbody>
                {ex.path.map((p, i) => (
                  <tr key={i}>
                    <td>{p.poss}</td>
                    <td>{p.clock}</td>
                    <td>{p.period}</td>
                    <td>{fmt(p.price, 1)}</td>
                    <td>{fmt(p.age, 0)}</td>
                    <td>{fmt(p.diff, 1)}</td>
                    <td>{p.regime}</td>
                    <td>{p.path_class_5}</td>
                    <td>{fmt(p.dd_5, 1)}</td>
                    <td>{p.order_10_5}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {tab === "Limitations" && (
          <>
            <h2>What this experiment cannot claim</h2>
            <ul>
              {dash.limitations.map((x) => (
                <li key={x} className="caption">{x}</li>
              ))}
            </ul>
            <div className="note">No recommended stop, hedge, sell, hold, size, maker fill, or IOC fill is produced.</div>
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
              Execution evidence is UNOBSERVED. Live deployment is NOT AUTHORIZED. Forward distribution ≠ tradable edge.
            </p>
          </>
        )}
      </div>
    </div>
  );
}

function Row({ from, probs, labels }: { from: string; probs: Array<number | null>; labels: string[] }) {
  return (
    <>
      <div className="hd">{from}</div>
      {labels.map((lab, j) => {
        const p = probs[j];
        return (
          <div className="cell" key={lab} style={{ background: heat(p), color: "#e6edf3" }}>
            {fmt(p, 2)}
          </div>
        );
      })}
    </>
  );
}
