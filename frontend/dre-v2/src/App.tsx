import { useEffect, useMemo, useState } from "react";

type Gate = { status: string; detail?: Record<string, unknown> };
type ModelRow = {
  family: string;
  layer?: string;
  target: string;
  target_label: string;
  split: string;
  n: number;
  n_excluded?: number;
  games?: number;
  auc: number | null;
  brier: number | null;
  logloss: number | null;
  ece: number | null;
  status: string;
};
type Surface = {
  split: string;
  price_lo: number;
  price_hi: number;
  n: number;
  mean_p_settle?: number | null;
  mean_p_rec?: number | null;
  mean_p_down?: number | null;
  mean_ev_mtm?: number | null;
  emp_settle?: number | null;
  emp_rec10_k5?: number | null;
  emp_det10_end?: number | null;
  mean_h_A?: number | null;
  mean_h_D?: number | null;
};
type Emp = {
  split: string;
  price_lo: number;
  price_hi: number;
  n: number;
  p_settle: number | null;
  p_rec10_k5: number | null;
  p_det10_end: number | null;
  p_min50_k5: number | null;
  p_jump40: number | null;
};
type Slice = {
  n: number;
  mean_price?: number | null;
  emp_settle?: number | null;
  emp_rec10_k5?: number | null;
  emp_det10_end?: number | null;
  mean_p_settle_B0?: number | null;
  mean_p_settle_M3?: number | null;
  mean_h_B0_A?: number | null;
  mean_h_M3_A?: number | null;
};
type Contrast = {
  split: string;
  band: string;
  price_lo: number;
  price_hi: number;
  early: Slice;
  late: Slice;
  leading: Slice;
  trailing: Slice;
  offense: Slice;
  defense: Slice;
};
type PathPt = {
  poss: number | null;
  pidx: number | null;
  real: number | null;
  clock: string | null;
  period: number | null;
  price: number | null;
  age: number | null;
  conf: string | null;
  det: number | null;
  dd: number | null;
  rec: number | null;
  diff: number | null;
  off: boolean | null;
  p_yes: number | null;
  p_rec: number | null;
  p_down: number | null;
  hA: number | null;
  hD: number | null;
  edge: number | null;
  uniq: number | null;
};
type Example = {
  trade_id: string;
  event_id: string;
  nba_game_id: string | null;
  split: string;
  n: number;
  path: PathPt[];
};
type Dash = {
  program: string;
  banner: string;
  created_utc: string;
  schema_version: string;
  verdict: Record<string, string>;
  gates: Record<string, Gate>;
  counts: Record<string, number | Record<string, unknown>>;
  models: ModelRow[];
  incremental_oos: Record<string, number | null>;
  surfaces: Surface[];
  emp_surfaces: Emp[];
  asymmetry: { contrasts: Contrast[]; asymmetry_exists_oos: boolean; notes: string[] };
  regimes: Record<string, unknown>[];
  selected: Record<string, { lam_d?: number | null; lam_r?: number | null; gamma?: number | null; val_score?: number | null }>;
  oos_policy: Record<string, { n?: number; mean_h?: number | null; frac_h_eq_1?: number | null; frac_interior?: number | null; mean_realized_h_times_continuation_cents?: number | null }>;
  rem_ablation: { settlement_oos_verdict: string };
  unresolved: { universe: number; panel_eligible_trades: number; unresolved_n: number; unresolved: { event_id: string; reason: string }[] };
  examples: Example[];
  leakage: { feature_name: string; availability: string; used_as_model_feature: boolean; passes_no_lookahead: boolean }[];
  corner_note: string;
};

const TABS = [
  "Overview",
  "Multi-clock",
  "Trade path",
  "Distributions",
  "Exposure",
  "Model lab",
  "Asymmetry",
  "Limitations",
] as const;

function fmt(v: number | null | undefined, d = 3): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toFixed(d);
}
function gradeClass(s: string): string {
  if (s === "PASS") return "pass";
  if (s === "FAIL" || s === "NOT AUTHORIZED") return "neg";
  if (s === "WARNING" || s === "UNOBSERVED") return "warn";
  return "muted";
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
  const [fam, setFam] = useState("M3");
  const [target, setTarget] = useState("y_settle_yes");
  const [split, setSplit] = useState("OOS");
  const [band, setBand] = useState("price_60");
  const [asymSplit, setAsymSplit] = useState("OOS");

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
  const targets = useMemo(() => {
    if (!dash) return [];
    return [...new Set(dash.models.map((m) => m.target))];
  }, [dash]);

  if (err) return <div className="err">Failed to load static artifact: {err}</div>;
  if (!dash) return <div className="err">Loading DRE V2 research artifact…</div>;

  const counts = dash.counts as Record<string, number>;

  return (
    <div className="app">
      <div className="banner">{dash.banner}</div>
      <div className="top">
        <div className="brand">
          DRE V2
          <small>Dynamic Risk Engine — offline research · {dash.schema_version}</small>
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
            <h2>Gates</h2>
            <div className="row">
              {Object.entries(dash.gates).map(([k, g]) => (
                <div className="card" key={k}>
                  <div className="k">Gate {k}</div>
                  <div className={`v ${gradeClass(g.status)}`}>{g.status}</div>
                </div>
              ))}
            </div>
            <h2>Scientific verdict</h2>
            <div className="row">
              {Object.entries(dash.verdict).map(([k, val]) => (
                <div className="card" key={k}>
                  <div className="k">{k.replaceAll("_", " ")}</div>
                  <div className={`v ${gradeClass(val)}`}>{val}</div>
                </div>
              ))}
            </div>
            <h2>Universe / panel</h2>
            <div className="row">
              <div className="card"><div className="k">Frozen universe</div><div className="v">{counts.universe ?? "—"}</div></div>
              <div className="card"><div className="k">Panel trades</div><div className="v">{counts.panel_trades}</div></div>
              <div className="card"><div className="k">Panel rows</div><div className="v">{counts.panel_rows}</div></div>
              <div className="card"><div className="k">Usable HIGH+MED</div><div className="v">{counts.usable}</div></div>
              <div className="card"><div className="k">Unresolved</div><div className="v warn">{dash.unresolved.unresolved_n}</div></div>
            </div>
            <h2>Major incremental OOS (vs B0 AUC)</h2>
            <table>
              <thead><tr><th>Contrast</th><th>Δ AUC</th></tr></thead>
              <tbody>
                {Object.entries(dash.incremental_oos).map(([k, val]) => (
                  <tr key={k}><td>{k}</td><td>{fmt(val)}</td></tr>
                ))}
              </tbody>
            </table>
            <p className="caption">
              Saturated P(min≤40 in 5 poss) is a control, not the headline. Theoretical target delta is not an execution instruction.
            </p>
          </>
        )}

        {tab === "Multi-clock" && ex && (
          <>
            <h2>Three clocks — {ex.event_id}</h2>
            <p className="caption">
              Real time, game clock, and possession index are separate. Market age shows candle staleness. Repeated prices are not independent updates.
            </p>
            <div className="chart">
              <svg viewBox="0 0 800 200" preserveAspectRatio="none">
                <Poly values={ex.path.map((p) => p.price)} color="#c8a25a" min={0} max={100} />
                <Poly values={ex.path.map((p) => (p.age == null ? null : Math.min(p.age, 180)))} color="#5aa0c8" min={0} max={180} />
              </svg>
            </div>
            <table>
              <thead>
                <tr>
                  <th>poss</th><th>idx</th><th>real ts</th><th>game clock</th><th>Q</th>
                  <th>price</th><th>age s</th><th>align</th><th>unique obs</th>
                </tr>
              </thead>
              <tbody>
                {ex.path.map((p, i) => (
                  <tr key={i}>
                    <td>{p.poss}</td>
                    <td>{p.pidx}</td>
                    <td>{p.real == null ? "—" : p.real.toFixed(0)}</td>
                    <td>{p.clock}</td>
                    <td>{p.period}</td>
                    <td>{fmt(p.price, 1)}</td>
                    <td>{fmt(p.age, 1)}</td>
                    <td>{p.conf}</td>
                    <td>{p.uniq}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {tab === "Trade path" && ex && (
          <>
            <h2>State path — {ex.trade_id}</h2>
            <div className="chart">
              <svg viewBox="0 0 800 200" preserveAspectRatio="none">
                <Poly values={ex.path.map((p) => p.price)} color="#c8a25a" min={0} max={100} />
                <Poly values={ex.path.map((p) => p.det)} color="#e05d5d" min={0} max={80} />
                <Poly values={ex.path.map((p) => p.dd)} color="#e0a14a" min={0} max={80} />
                <Poly values={ex.path.map((p) => p.diff)} color="#3dba7a" min={-30} max={30} />
              </svg>
            </div>
            <p className="caption">Gold = current yes-bid ¢. Red = deterioration. Amber = max drawdown. Green = score differential. Candle path ≠ fill.</p>
            <table>
              <thead>
                <tr>
                  <th>poss</th><th>price</th><th>det</th><th>max DD</th><th>rec from max</th>
                  <th>score</th><th>off?</th><th>h* A</th><th>h* D</th>
                </tr>
              </thead>
              <tbody>
                {ex.path.map((p, i) => (
                  <tr key={i}>
                    <td>{p.poss}</td>
                    <td>{fmt(p.price, 1)}</td>
                    <td>{fmt(p.det, 1)}</td>
                    <td>{fmt(p.dd, 1)}</td>
                    <td>{fmt(p.rec, 1)}</td>
                    <td>{p.diff}</td>
                    <td>{p.off == null ? "—" : p.off ? "Y" : "N"}</td>
                    <td>{fmt(p.hA, 2)}</td>
                    <td>{fmt(p.hD, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {tab === "Distributions" && (
          <>
            <h2>Empirical future distributions by current price</h2>
            <div className="ctrl" style={{ marginBottom: 8 }}>
              <label>Split</label>
              <select value={split} onChange={(e) => setSplit(e.target.value)}>
                <option>TRAIN</option><option>VALIDATION</option><option>OOS</option>
              </select>
            </div>
            <table>
              <thead>
                <tr>
                  <th>price</th><th>n</th><th>P(settle)</th><th>P(rec≥10 / 5p)</th>
                  <th>P(det≥10 end)</th><th>P(min≤50 / 5p)</th><th>P(jump-40 proxy)</th>
                </tr>
              </thead>
              <tbody>
                {dash.emp_surfaces.filter((s) => s.split === split).map((s) => (
                  <tr key={`${s.price_lo}`}>
                    <td>{s.price_lo}–{s.price_hi}</td>
                    <td>{s.n}</td>
                    <td>{fmt(s.p_settle)}</td>
                    <td>{fmt(s.p_rec10_k5)}</td>
                    <td>{fmt(s.p_det10_end)}</td>
                    <td>{fmt(s.p_min50_k5)}</td>
                    <td>{fmt(s.p_jump40)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {ex && (
              <>
                <h2>Selected-trade model probabilities (M3)</h2>
                <div className="chart">
                  <svg viewBox="0 0 800 200" preserveAspectRatio="none">
                    <Poly values={ex.path.map((p) => p.p_yes)} color="#c8a25a" min={0} max={1} />
                    <Poly values={ex.path.map((p) => p.p_rec)} color="#3dba7a" min={0} max={1} />
                    <Poly values={ex.path.map((p) => p.p_down)} color="#e05d5d" min={0} max={1} />
                  </svg>
                </div>
                <p className="caption">Gold P(settle YES). Green P(rec≥10 within 5 poss). Red P(det≥10 to end). Jump-40 is a candle-path proxy, not a fill failure.</p>
              </>
            )}
          </>
        )}

        {tab === "Exposure" && (
          <>
            <h2>Theoretical exposure surface — NOT EXECUTION</h2>
            <span className="tag">THEORETICAL — NOT EXECUTION</span>
            <p className="caption">{dash.corner_note}</p>
            <div className="row">
              {(["A", "B", "C", "D"] as const).map((k) => {
                const s = dash.selected[k] || {};
                const o = dash.oos_policy[k] || {};
                return (
                  <div className="card" key={k}>
                    <div className="k">Family {k}</div>
                    <div className="v">{fmt(o.mean_h, 2)}</div>
                    <div className="muted">λD={fmt(s.lam_d, 1)} λR={fmt(s.lam_r, 1)} γ={fmt(s.gamma, 1)}</div>
                    <div className="muted">OOS interior {fmt(o.frac_interior)}</div>
                  </div>
                );
              })}
            </div>
            <h2>OOS mean h* and EV by price (M3)</h2>
            <table>
              <thead>
                <tr>
                  <th>price</th><th>n</th><th>P settle</th><th>emp settle</th>
                  <th>EV mtm ¢</th><th>h* A</th><th>h* D</th>
                </tr>
              </thead>
              <tbody>
                {dash.surfaces.filter((s) => s.split === "OOS").map((s) => (
                  <tr key={s.price_lo}>
                    <td>{s.price_lo}–{s.price_hi}</td>
                    <td>{s.n}</td>
                    <td>{fmt(s.mean_p_settle)}</td>
                    <td>{fmt(s.emp_settle)}</td>
                    <td>{fmt(s.mean_ev_mtm, 2)}</td>
                    <td>{fmt(s.mean_h_A, 2)}</td>
                    <td>{fmt(s.mean_h_D, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {ex && (
              <>
                <h2>Trade h* path</h2>
                <div className="chart">
                  <svg viewBox="0 0 800 200" preserveAspectRatio="none">
                    <Poly values={ex.path.map((p) => p.hA)} color="#c8a25a" min={0} max={1} />
                    <Poly values={ex.path.map((p) => p.hD)} color="#5aa0c8" min={0} max={1} />
                    <Poly values={ex.path.map((p) => p.edge)} color="#e0a14a" min={-0.4} max={0.4} />
                  </svg>
                </div>
                <p className="caption">Gold h* Family A (usually 0/1). Blue Family D (may be interior). Amber terminal-probability edge. Not an order.</p>
              </>
            )}
          </>
        )}

        {tab === "Model lab" && (
          <>
            <h2>Nested models</h2>
            <div className="row">
              <div className="ctrl">
                <label>Family</label>
                <select value={fam} onChange={(e) => setFam(e.target.value)}>
                  {["B0", "B1", "B2", "M3", "M3_NO_REM", "M4", "M5"].map((f) => (
                    <option key={f}>{f}</option>
                  ))}
                </select>
              </div>
              <div className="ctrl">
                <label>Target</label>
                <select value={target} onChange={(e) => setTarget(e.target.value)}>
                  {targets.map((t) => (
                    <option key={t}>{t}</option>
                  ))}
                </select>
              </div>
            </div>
            <table>
              <thead>
                <tr>
                  <th>family</th><th>split</th><th>n</th><th>excl</th><th>AUC</th><th>Brier</th><th>logloss</th><th>ECE</th>
                </tr>
              </thead>
              <tbody>
                {dash.models
                  .filter((m) => m.target === target && (fam === m.family || true))
                  .filter((m) => m.target === target)
                  .map((m, i) => (
                    <tr key={i} style={{ opacity: m.family === fam ? 1 : 0.55 }}>
                      <td>{m.family}</td>
                      <td>{m.split}</td>
                      <td>{m.n}</td>
                      <td>{m.n_excluded ?? "—"}</td>
                      <td>{fmt(m.auc)}</td>
                      <td>{fmt(m.brier)}</td>
                      <td>{fmt(m.logloss)}</td>
                      <td>{fmt(m.ece)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
            <p className="caption">
              Remaining-possessions ablation settlement OOS: <b>{dash.rem_ablation.settlement_oos_verdict}</b>.
              Every advanced family is compared to B0. No OOS tuning.
            </p>
          </>
        )}

        {tab === "Asymmetry" && (
          <>
            <h2>Same price, different state</h2>
            <p className="caption">
              OOS asymmetry declared: <b className={dash.asymmetry.asymmetry_exists_oos ? "pass" : "warn"}>
                {dash.asymmetry.asymmetry_exists_oos ? "YES" : "INCONCLUSIVE"}
              </b>
              {dash.asymmetry.notes.map((n) => ` · ${n}`)}
            </p>
            <div className="row">
              <div className="ctrl">
                <label>Split</label>
                <select value={asymSplit} onChange={(e) => setAsymSplit(e.target.value)}>
                  <option>OOS</option><option>VALIDATION</option><option>TRAIN</option><option>ALL</option>
                </select>
              </div>
              <div className="ctrl">
                <label>Price band</label>
                <select value={band} onChange={(e) => setBand(e.target.value)}>
                  <option value="price_70">~70</option>
                  <option value="price_60">~60</option>
                  <option value="price_50">~50</option>
                </select>
              </div>
            </div>
            {dash.asymmetry.contrasts
              .filter((c) => c.split === asymSplit && c.band === band)
              .map((c) => (
                <table key={`${c.split}-${c.band}`}>
                  <thead>
                    <tr>
                      <th>slice</th><th>n</th><th>px</th><th>P settle</th><th>P rec</th><th>P down</th>
                      <th>P_B0</th><th>P_M3</th><th>h* B0</th><th>h* M3</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(["early", "late", "leading", "trailing", "offense", "defense"] as const).map((name) => {
                      const s = c[name];
                      return (
                        <tr key={name}>
                          <td>{name}</td>
                          <td>{s.n}</td>
                          <td>{fmt(s.mean_price, 1)}</td>
                          <td>{fmt(s.emp_settle)}</td>
                          <td>{fmt(s.emp_rec10_k5)}</td>
                          <td>{fmt(s.emp_det10_end)}</td>
                          <td>{fmt(s.mean_p_settle_B0)}</td>
                          <td>{fmt(s.mean_p_settle_M3)}</td>
                          <td>{fmt(s.mean_h_B0_A, 2)}</td>
                          <td>{fmt(s.mean_h_M3_A, 2)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              ))}
          </>
        )}

        {tab === "Limitations" && (
          <>
            <h2>Hard limitations</h2>
            <ul className="caption">
              <li>1-minute candles. Stale observations are first-class (`market_age_seconds`).</li>
              <li>No L2. No fill tape. Jump-through is a candle-path proxy only.</li>
              <li>Unresolved games are preserved, not deleted ({dash.unresolved.unresolved_n} of {dash.unresolved.universe}).</li>
              <li>Remaining-possession R2 is a biased ESTIMATE. Ablation is labeled. Model was not silently revised.</li>
              <li>Theoretical target delta ≠ executed delta. Desired h is not assumed achievable.</li>
              <li>This dashboard loads a static research artifact. It is not a live trading interface.</li>
            </ul>
            <h2>Unresolved trades</h2>
            <table>
              <thead><tr><th>event</th><th>reason</th></tr></thead>
              <tbody>
                {dash.unresolved.unresolved.map((u) => (
                  <tr key={u.event_id}><td>{u.event_id}</td><td>{u.reason}</td></tr>
                ))}
              </tbody>
            </table>
            <h2>Leakage audit (features used)</h2>
            <table>
              <thead><tr><th>feature</th><th>availability</th><th>used</th><th>no-lookahead</th></tr></thead>
              <tbody>
                {dash.leakage.filter((r) => r.used_as_model_feature).map((r) => (
                  <tr key={r.feature_name}>
                    <td>{r.feature_name}</td>
                    <td>{r.availability}</td>
                    <td>{r.used_as_model_feature ? "yes" : "no"}</td>
                    <td className={r.passes_no_lookahead ? "pass" : "fail"}>{r.passes_no_lookahead ? "PASS" : "FAIL"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>
    </div>
  );
}
