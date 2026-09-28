import { useEffect, useMemo, useState } from "react";

type Gate = { status: string };
type Cell = {
  split?: string;
  level?: string;
  payoff?: string;
  slice?: string;
  weighting?: string;
  n_rows?: number;
  n_unique_trades?: number;
  n_unique_games?: number;
  mean_pi?: number | null;
  p_settle_yes?: number | null;
  p10?: number | null;
  p50?: number | null;
  p90?: number | null;
  adequate?: boolean;
  price_bin_5?: number;
  price_bin_10?: number;
  clock_bin_l2?: string;
  score_bin_l2?: string;
  n_hat_bin_l2?: string;
  mean_h?: number | null;
  occ_mean_pi?: number | null;
};
type Contrast = {
  spec?: { id?: string };
  by_split?: Record<string, { effect_b_minus_a?: number | null; adequate?: boolean; a?: { TRADE_BALANCED?: { mean_pi?: number; p_settle_yes?: number }; n_unique_trades?: number }; b?: { TRADE_BALANCED?: { mean_pi?: number; p_settle_yes?: number }; n_unique_trades?: number } }>;
};
type Example = {
  trade_id: string;
  event_id: string;
  split: string;
  n: number;
  y_settle_yes: number | null;
  pi_terminal: number | null;
  path: Array<{ pidx: number | null; clock: string | null; price_cents: number | null; n_hat: number | null; v_mtm: number | null; diff: number | null }>;
  label: string;
};
type Dash = {
  program: string;
  banner: string;
  schema_version: string;
  created_utc: string;
  research_date: string;
  central_question: string;
  verdict: { HEADLINE: string; flags: Record<string, boolean>; tokens?: Record<string, string>; m1_beats_m0?: boolean; note?: string };
  gates: Record<string, Gate>;
  counts: { rows: number; trades: number; games?: number; splits: Record<string, { rows: number; trades: number; games?: number }> };
  universe: { universe: number; panel_eligible: number; unresolved_n: number; note?: string };
  pace: { r_x?: { mean?: number; median?: number }; train_league_mean_team_poss?: number; chronology?: string; rx_identity?: string };
  clock_l2?: Record<string, string[]>;
  surfaces: Cell[];
  hazard: Cell[];
  hazard_accounting?: { n_at_risk?: number; n_already_in_branch?: number };
  contrasts: Contrast[];
  replication: { contrasts?: Array<{ id: string; token: string; ratio_oos_over_train?: number | null; train_effect?: number | null; oos_effect?: number | null }> };
  m01: { m1_beats_m0?: boolean; by_split?: Record<string, { mae_m0_trade_balanced?: number; mae_m1_trade_balanced?: number; delta_mae_m0_minus_m1?: number; mae_m0_occupancy?: number }> };
  gradients: Array<{ split?: string; coordinate?: string; delta_emp?: number; p_low_cents?: number; p_high_cents?: number; low_label?: string; high_label?: string; price_bin_5?: number; n_unique_trades_low?: number; n_unique_trades_high?: number }>;
  gamma: Record<string, { gamma_emp?: number | null; slope_50s?: { delta_emp?: number }; slope_70s?: { delta_emp?: number } }>;
  lambda: Record<string, { mean_trade_balanced?: number; n_trades?: number; n_steps?: number; surface_source?: string; paths?: string; verdict_input?: boolean }>;
  volatility?: { by_split?: Record<string, { mean_trade_balanced?: number }> };
  ledger: { n: number; unresolved: number; V_mtm_entry_cents: number; cards: Array<{ trade_id: string; dataset_split?: string; game_date?: string; unresolved?: boolean; y_settle_yes?: number | null; pi_terminal?: number | null; A1_team?: string; V_mtm_entry_cents?: number }> };
  candle_ledger_rows?: number;
  examples: Example[];
  layers: Record<string, string>;
  limitations: string[];
  identity?: string;
};

const TABS = [
  "Overview",
  "Trade Ledger",
  "Candle Path",
  "Prior-Informed Remaining",
  "State Vector",
  "Conditional Payoff",
  "Hazard",
  "Empirical Gradient / Curvature",
  "Path Lambda",
  "Limitations",
  "Verdict",
] as const;

function fmt(v: number | null | undefined, d = 3): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toFixed(d);
}
function grade(s: string): string {
  if (s === "PASS" || s === "ROBUST" || s === "A") return "pass";
  if (s === "FAIL" || s === "NOT AUTHORIZED" || s === "D") return "neg";
  if (s === "PARTIAL" || s === "INCONCLUSIVE" || s === "B" || s === "C") return "warn";
  return "muted";
}

function Poly({ values, color, min, max }: { values: (number | null)[]; color: string; min: number; max: number }) {
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
  const [payoff, setPayoff] = useState("pi_terminal");
  const [q, setQ] = useState("");

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
  const prices = useMemo(() => (ex ? ex.path.map((p) => p.price_cents) : []), [ex]);
  const nhats = useMemo(() => (ex ? ex.path.map((p) => p.n_hat) : []), [ex]);

  if (err) return <div className="err">Failed to load static artifact: {err}</div>;
  if (!dash) return <div className="err">Loading DRE V5 research artifact…</div>;

  const cells = dash.surfaces.filter((c) => c.split === split && c.payoff === payoff && c.level === "L3" && c.adequate);
  const cards = dash.ledger.cards.filter((c) => !q || c.trade_id.toLowerCase().includes(q.toLowerCase()) || (c.game_date || "").includes(q));
  const names: Record<string, string> = { A: "Strong state segmentation", B: "Price dominates", C: "N̂ remaining adds information", D: "Nothing replicates OOS" };

  return (
    <div className="app">
      <div className="banner">{dash.banner}</div>
      <div className="top">
        <div className="brand">
          DRE V5
          <small>Conditional payoff surfaces · {dash.schema_version} · {dash.research_date}</small>
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
          <label>Payoff</label>
          <select value={payoff} onChange={(e) => setPayoff(e.target.value)}>
            <option value="pi_terminal">π_terminal (primary)</option>
            <option value="pi_mtm">π_mtm (secondary)</option>
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
              <span className="layer obs">OBSERVED</span>
              <span className="layer mod">CONDITIONAL EXPECTED PAYOFF</span>
              <span className="layer th">EMPIRICAL SENSITIVITY</span>
              <span className="layer un">UNOBSERVED EXECUTION</span>
            </div>
            <div className="note">LIVE DEPLOYMENT: NOT AUTHORIZED · CANDLE PATH ≠ ACTUAL FILL · 100-CONTRACT LEDGER ≠ $50 PRODUCTION SIZE</div>
            <h2>Central question</h2>
            <p>{dash.central_question}</p>
            <div className="row">
              <div className="card">
                <div className="k">Headline</div>
                <div className={`v ${grade(dash.verdict.HEADLINE)}`}>
                  {dash.verdict.HEADLINE} — {names[dash.verdict.HEADLINE]}
                </div>
              </div>
              <div className="card">
                <div className="k">Live deployment</div>
                <div className="v neg">NOT AUTHORIZED</div>
              </div>
              <div className="card">
                <div className="k">Universe / panel</div>
                <div className="v">{dash.universe.universe} / {dash.counts.trades}</div>
              </div>
              <div className="card">
                <div className="k">Unresolved</div>
                <div className="v">{dash.universe.unresolved_n}</div>
              </div>
            </div>
            <h2>Four subquestions</h2>
            <p className="caption">Heterogeneity · at-risk hazard · ∇α · path Λ. TRAIN interestingness is not a discovery.</p>
            <h2>Gates</h2>
            <table>
              <thead>
                <tr>
                  <th>Gate</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(dash.gates).map(([k, g]) => (
                  <tr key={k}>
                    <td>{k}</td>
                    <td className={grade(g.status)}>{g.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="caption">{dash.identity}. Weighting PRIMARY = TRADE_BALANCED. Units = cents per contract.</p>
          </>
        )}

        {tab === "Trade Ledger" && (
          <>
            <div className="note">Buy @ 80¢ · Q=100 · V_mtm_entry = {dash.ledger.V_mtm_entry_cents} cents · CANDLE_PATH_PROXY_NOT_PROVEN_FILL</div>
            <div className="row">
              <div className="card"><div className="k">Cards</div><div className="v">{dash.ledger.n}</div></div>
              <div className="card"><div className="k">Unresolved</div><div className="v">{dash.ledger.unresolved}</div></div>
            </div>
            <div className="ctrl" style={{ margin: "12px 0" }}>
              <label>Filter ticker / date</label>
              <input value={q} onChange={(e) => setQ(e.target.value)} />
            </div>
            <table>
              <thead>
                <tr>
                  <th>trade_id</th>
                  <th>split</th>
                  <th>date</th>
                  <th>A1</th>
                  <th>π_terminal</th>
                  <th>unresolved</th>
                </tr>
              </thead>
              <tbody>
                {cards.slice(0, 80).map((c) => (
                  <tr key={c.trade_id}>
                    <td>{c.trade_id}</td>
                    <td>{c.dataset_split}</td>
                    <td>{c.game_date}</td>
                    <td>{c.A1_team}</td>
                    <td>{fmt(c.pi_terminal, 0)}</td>
                    <td>{c.unresolved ? "true" : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="caption">Showing {Math.min(80, cards.length)} of {cards.length}. Q=100 is research inventory, not production size.</p>
          </>
        )}

        {tab === "Candle Path" && (
          <>
            <div className="note">OBSERVED CANDLE PATH — NOT FILL HISTORY · candle ledger rows {dash.candle_ledger_rows ?? "—"}</div>
            {ex && (
              <>
                <p className="caption">{ex.split} · {ex.trade_id} · π={fmt(ex.pi_terminal, 0)} · Y={fmt(ex.y_settle_yes, 0)}</p>
                <div className="chart">
                  <svg viewBox="0 0 800 200" preserveAspectRatio="none">
                    <Poly values={prices} color="#c8a25a" min={0} max={100} />
                  </svg>
                </div>
                <p className="caption">A1 yes bid, cents. RESEARCH SURFACE — NOT A TRADING INSTRUCTION.</p>
              </>
            )}
          </>
        )}

        {tab === "Prior-Informed Remaining" && (
          <>
            <div className="note">n_hat_remaining_prior = max(0, R_x − possession_index). Not the observed remaining count. Not a predicted possession index.</div>
            <div className="row">
              <div className="card"><div className="k">R_x mean</div><div className="v">{fmt(dash.pace.r_x?.mean, 1)}</div></div>
              <div className="card"><div className="k">R_x median</div><div className="v">{fmt(dash.pace.r_x?.median, 1)}</div></div>
              <div className="card"><div className="k">TRAIN league mean pace</div><div className="v">{fmt(dash.pace.train_league_mean_team_poss, 1)}</div></div>
            </div>
            <p className="caption">{dash.pace.rx_identity} · {dash.pace.chronology}. 352 was an identity illustration and was not used.</p>
            {ex && (
              <div className="chart">
                <svg viewBox="0 0 800 200" preserveAspectRatio="none">
                  <Poly values={nhats} color="#5aa0c8" min={0} max={Math.max(40, ...nhats.map((x) => x || 0))} />
                </svg>
              </div>
            )}
          </>
        )}

        {tab === "State Vector" && (
          <>
            <p>X_t = basketball state + n_hat_remaining_prior + market coordinates (cents).</p>
            <p className="caption">P_A1, P_A2, rel, and CR are related market coordinates, not four independent discoveries. L2 clock: EARLY=Q1+Q2+Q3, LATE=Q4, OT separately flagged.</p>
            <pre className="note">{JSON.stringify(dash.clock_l2, null, 2)}</pre>
            <p className="caption">Inventory: V_mtm_cents = 100 × P_A1_cents. Δ_inv = 100.</p>
          </>
        )}

        {tab === "Conditional Payoff" && (
          <>
            <div className="note">PRIMARY TRADE_BALANCED · α_frozen = E[100Y−80 | X] = 100 p_settle − 80 · RESEARCH SURFACE — NOT A TRADING INSTRUCTION</div>
            <table>
              <thead>
                <tr>
                  <th>slice</th>
                  <th>price</th>
                  <th>coord</th>
                  <th>α ¢</th>
                  <th>p_settle</th>
                  <th>P10</th>
                  <th>P50</th>
                  <th>P90</th>
                  <th>rows</th>
                  <th>trades</th>
                  <th>games</th>
                </tr>
              </thead>
              <tbody>
                {cells.slice(0, 80).map((c, i) => (
                  <tr key={i}>
                    <td>{c.slice}</td>
                    <td>{c.price_bin_5 ?? c.price_bin_10}</td>
                    <td>{c.clock_bin_l2 || c.score_bin_l2 || c.n_hat_bin_l2 || "price"}</td>
                    <td>{fmt(c.mean_pi)}</td>
                    <td>{fmt(c.p_settle_yes)}</td>
                    <td>{fmt(c.p10, 0)}</td>
                    <td>{fmt(c.p50, 0)}</td>
                    <td>{fmt(c.p90, 0)}</td>
                    <td>{c.n_rows}</td>
                    <td>{c.n_unique_trades}</td>
                    <td>{c.n_unique_games}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="caption">Quantiles are empirical. A realized payoff of 0 never occurs. Occupancy means are stored separately and labeled.</p>
          </>
        )}

        {tab === "Hazard" && (
          <>
            <div className="note">At-risk only: running min so far &gt; 40¢. Already-damaged paths are out of the primary denominator.</div>
            <div className="row">
              <div className="card"><div className="k">At-risk rows</div><div className="v">{dash.hazard_accounting?.n_at_risk}</div></div>
              <div className="card"><div className="k">Already in branch</div><div className="v">{dash.hazard_accounting?.n_already_in_branch}</div></div>
            </div>
            <table>
              <thead>
                <tr>
                  <th>split</th>
                  <th>price</th>
                  <th>clock</th>
                  <th>h</th>
                  <th>trades</th>
                  <th>games</th>
                </tr>
              </thead>
              <tbody>
                {dash.hazard.filter((h) => h.split === split).slice(0, 60).map((h, i) => (
                  <tr key={i}>
                    <td>{h.split}</td>
                    <td>{h.price_bin_5 ?? h.price_bin_10}</td>
                    <td>{h.clock_bin_l2}</td>
                    <td>{fmt(h.mean_h ?? h.mean_pi)}</td>
                    <td>{h.n_unique_trades}</td>
                    <td>{h.n_unique_games}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {tab === "Empirical Gradient / Curvature" && (
          <>
            <div className="note">Ascending orientation. Discovery slopes use α_frozen. 40¢ framework excluded. Not options delta.</div>
            <div className="row">
              <div className="card"><div className="k">Γ TRAIN</div><div className="v">{fmt(dash.gamma.TRAIN?.gamma_emp)}</div></div>
              <div className="card"><div className="k">Γ OOS</div><div className="v">{fmt(dash.gamma.OOS?.gamma_emp)}</div></div>
            </div>
            <table>
              <thead>
                <tr>
                  <th>split</th>
                  <th>coord</th>
                  <th>from</th>
                  <th>to</th>
                  <th>Δ_emp</th>
                  <th>trades lo/hi</th>
                </tr>
              </thead>
              <tbody>
                {dash.gradients.filter((g) => g.split === split).slice(0, 40).map((g, i) => (
                  <tr key={i}>
                    <td>{g.split}</td>
                    <td>{g.coordinate}</td>
                    <td>{g.p_low_cents ?? g.low_label}</td>
                    <td>{g.p_high_cents ?? g.high_label}</td>
                    <td>{fmt(g.delta_emp)}</td>
                    <td>{g.n_unique_trades_low}/{g.n_unique_trades_high}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {tab === "Path Lambda" && (
          <>
            <div className="note">Scientific OOS Lambda = TRAIN-frozen α on OOS paths. Descriptive OOS Lambda is NEVER a verdict input.</div>
            <table>
              <thead>
                <tr>
                  <th>object</th>
                  <th>surface</th>
                  <th>paths</th>
                  <th>mean (trade-balanced)</th>
                  <th>trades</th>
                  <th>verdict?</th>
                </tr>
              </thead>
              <tbody>
                {["discovery_lambda", "validation_lambda", "scientific_oos_lambda", "descriptive_oos_lambda"].map((k) => {
                  const L = dash.lambda[k] || {};
                  return (
                    <tr key={k}>
                      <td>{k}</td>
                      <td>{L.surface_source}</td>
                      <td>{L.paths}</td>
                      <td>{fmt(L.mean_trade_balanced)}</td>
                      <td>{L.n_trades}</td>
                      <td>{L.verdict_input ? "yes" : "no"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="caption">Λ_path = −(α(X_t+1)−α(X_t)). Not isolated ∂α/∂τ. Last state is censored.</p>
          </>
        )}

        {tab === "Limitations" && (
          <>
            <ul>
              {dash.limitations.map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
            {Object.entries(dash.layers).map(([k, v]) => (
              <p key={k} className="caption">
                <b>{k}</b> — {v}
              </p>
            ))}
          </>
        )}

        {tab === "Verdict" && (
          <>
            <div className="row">
              <div className="card">
                <div className="k">Headline</div>
                <div className={`v ${grade(dash.verdict.HEADLINE)}`}>{dash.verdict.HEADLINE} — {names[dash.verdict.HEADLINE]}</div>
              </div>
              <div className="card">
                <div className="k">M1 beats M0</div>
                <div className="v">{String(dash.verdict.m1_beats_m0)}</div>
              </div>
            </div>
            <table>
              <thead>
                <tr>
                  <th>contrast</th>
                  <th>token</th>
                  <th>TRAIN</th>
                  <th>OOS</th>
                  <th>ratio</th>
                </tr>
              </thead>
              <tbody>
                {(dash.replication.contrasts || []).map((c) => (
                  <tr key={c.id}>
                    <td>{c.id}</td>
                    <td className={grade(c.token)}>{c.token}</td>
                    <td>{fmt(c.train_effect)}</td>
                    <td>{fmt(c.oos_effect)}</td>
                    <td>{fmt(c.ratio_oos_over_train)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <h2>M0 vs M1 OOS</h2>
            <p className="caption">
              TRADE_BALANCED MAE M0 {fmt(dash.m01.by_split?.OOS?.mae_m0_trade_balanced)} · M1 {fmt(dash.m01.by_split?.OOS?.mae_m1_trade_balanced)} · Δ {fmt(dash.m01.by_split?.OOS?.delta_mae_m0_minus_m1)}.
              Occupancy MAE is a diagnostic only ({fmt(dash.m01.by_split?.OOS?.mae_m0_occupancy)}).
            </p>
            <p>{dash.verdict.note}</p>
            <div className="note">LIVE DEPLOYMENT: NOT AUTHORIZED</div>
          </>
        )}
      </div>
    </div>
  );
}
