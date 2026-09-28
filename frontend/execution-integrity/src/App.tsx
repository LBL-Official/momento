import { useEffect, useState } from "react";

type Desc = {
  n?: number;
  gross_expectancy?: number;
  win_rate?: number;
  p05?: number;
  evidence?: string;
  sample_status?: string;
  bootstrap?: { ci95_lo?: number; ci95_hi?: number };
};
type Row = { path_class: string; n: number; frequency: number; mean_pnl: number | null; contribution_to_total_ev: number };
type Sport = {
  n: number;
  date_min: string;
  date_max: string;
  split_n: Record<string, number>;
  reproduction: { ok: boolean; hold: number; stop: number; v1: number };
  expectancy: Record<string, Desc>;
  e2: Record<string, Desc>;
  decomposition: { rows: Row[]; total_ev: number; reconstructed_ev: number; identity_ok: boolean };
  waterfall: Record<string, number | boolean>;
  opportunity_counts: Record<string, number>;
  occupancy_counts: Record<string, number>;
  concentration: Record<string, number | string | null>;
  counterfactual: Record<string, number | string>;
  by_split: Record<string, { n: number; e1: Desc; stop: Desc; sample_flag?: string }>;
  invariants: Array<{ id: string; ok: boolean }>;
};
type Dash = {
  banner: string;
  meta: Record<string, unknown>;
  sports: Record<string, Sport>;
  pyramid: Record<string, string>;
  audit_preview: Array<Record<string, unknown>>;
  audit_rows: number;
};

const VIEWS = [
  ["pyramid", "Evidence pyramid"],
  ["payoff", "Payoff"],
  ["waterfall", "Expectancy waterfall"],
  ["opp", "Opportunity integrity"],
  ["models", "Execution models"],
  ["drill", "Trade drilldown"],
] as const;

function fmt(n?: number | null, d = 2) {
  return n == null || Number.isNaN(n) ? "—" : n.toFixed(d);
}

export default function App() {
  const [dash, setDash] = useState<Dash | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [sport, setSport] = useState("nba");
  const [view, setView] = useState<(typeof VIEWS)[number][0]>("pyramid");

  useEffect(() => {
    fetch("/data/dashboard.json")
      .then((r) => {
        if (!r.ok) throw new Error("dashboard.json missing — run the EIE");
        return r.json();
      })
      .then(setDash)
      .catch((e: Error) => setErr(e.message));
  }, []);

  if (err) return <p className="main neg">{err}</p>;
  if (!dash) return <p className="main muted">Loading…</p>;
  const s = dash.sports[sport];
  if (!s) return <p className="main muted">No sport payload.</p>;

  return (
    <div className="app">
      <div className="banner">{dash.banner}</div>
      <header className="top">
        <div className="brand">
          EXECUTION INTEGRITY
          <small>
            {String(dash.meta.dre_baseline)} · {String(dash.meta.universe_version)} ·{" "}
            {String(dash.meta.config_hash)}
          </small>
        </div>
        <div className="ctrl">
          <label>Sport</label>
          <select value={sport} onChange={(e) => setSport(e.target.value)}>
            <option value="nba">NBA n={dash.sports.nba?.n}</option>
            <option value="ncaab">NCAAB P5 n={dash.sports.ncaab?.n}</option>
          </select>
        </div>
      </header>
      <nav className="tabs">
        {VIEWS.map(([id, lab]) => (
          <button key={id} className={view === id ? "on" : ""} onClick={() => setView(id)}>
            {lab}
          </button>
        ))}
      </nav>
      <main className="main">
        {view === "pyramid" && (
          <>
            <h2>Evidence pyramid</h2>
            <p className="note">A lower level cannot silently become a higher claim.</p>
            <div className="row">
              {Object.entries(dash.pyramid).map(([k, v]) => (
                <div className="card" key={k} style={{ minWidth: 220 }}>
                  <div className="k">{k}</div>
                  <div className="v" style={{ fontSize: 13 }}>
                    {v}
                  </div>
                </div>
              ))}
            </div>
            <h2>Expectancy by layer (FULL)</h2>
            <table>
              <thead>
                <tr>
                  <th>Layer</th>
                  <th>EV</th>
                  <th>Evidence</th>
                  <th>CI</th>
                </tr>
              </thead>
              <tbody>
                {(
                  [
                    ["EV_L1_hold", "L1 hold"],
                    ["EV_80_40", "80→40"],
                    ["EV_L3_E1", "E1 hybrid"],
                    ["EV_L3_E_THEO", "Theoretical @40"],
                  ] as const
                ).map(([k, lab]) => {
                  const d = s.expectancy[k] || {};
                  return (
                    <tr key={k}>
                      <td>{lab}</td>
                      <td>{fmt(d.gross_expectancy)}</td>
                      <td>{d.evidence}</td>
                      <td>
                        {fmt(d.bootstrap?.ci95_lo)} … {fmt(d.bootstrap?.ci95_hi)}
                      </td>
                    </tr>
                  );
                })}
                <tr>
                  <td>L4 actual</td>
                  <td>—</td>
                  <td>NOT_AVAILABLE</td>
                  <td>—</td>
                </tr>
              </tbody>
            </table>
            <p className="muted">
              Gate {s.reproduction.ok ? "PASS" : "FAIL"} · hold {s.reproduction.hold} · 80→40{" "}
              {s.reproduction.stop} · V1 {s.reproduction.v1}
            </p>
          </>
        )}

        {view === "payoff" && (
          <>
            <h2>E1 path classes</h2>
            <p className="muted">
              Identity ok={String(s.decomposition.identity_ok)} · total {fmt(s.decomposition.total_ev)} ·
              recon {fmt(s.decomposition.reconstructed_ev)}
            </p>
            <table>
              <thead>
                <tr>
                  <th>Class</th>
                  <th>n</th>
                  <th>Freq</th>
                  <th>Mean</th>
                  <th>EV contrib</th>
                </tr>
              </thead>
              <tbody>
                {s.decomposition.rows.map((r) => (
                  <tr key={r.path_class}>
                    <td>{r.path_class}</td>
                    <td>{r.n}</td>
                    <td>{fmt(r.frequency, 3)}</td>
                    <td>{fmt(r.mean_pnl)}</td>
                    <td>{fmt(r.contribution_to_total_ev)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {view === "waterfall" && (
          <>
            <h2>Hold → stop → E1 (must reconcile)</h2>
            <div className="row">
              <div className="card">
                <div className="k">Hold</div>
                <div className="v">{fmt(s.waterfall.hold as number)}</div>
              </div>
              <div className="card">
                <div className="k">+ stop protection</div>
                <div className="v pos">{fmt(s.waterfall.plus_stop_protection as number)}</div>
              </div>
              <div className="card">
                <div className="k">= 80→40</div>
                <div className="v">{fmt(s.waterfall.equals_80_40 as number)}</div>
              </div>
              <div className="card">
                <div className="k">+ E1 vs stop</div>
                <div className={`v ${(s.waterfall.plus_e1_hedge_vs_stop as number) >= 0 ? "pos" : "neg"}`}>
                  {fmt(s.waterfall.plus_e1_hedge_vs_stop as number)}
                </div>
              </div>
              <div className="card">
                <div className="k">= E1</div>
                <div className="v">{fmt(s.waterfall.equals_e1 as number)}</div>
              </div>
              <div className="card">
                <div className="k">Theo − E1 (gap fiction)</div>
                <div className="v warn">{fmt(s.waterfall.theo_minus_e1_gap_fiction as number)}</div>
              </div>
            </div>
            <p className="note">Observed / modeled / illegal-promotion are different rows. L4 is absent.</p>
          </>
        )}

        {view === "opp" && (
          <>
            <h2>L2 opportunity (H=40 exact)</h2>
            <table>
              <thead>
                <tr>
                  <th>Class</th>
                  <th>n</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(s.opportunity_counts).map(([k, n]) => (
                  <tr key={k}>
                    <td>{k}</td>
                    <td>{n}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <h2>Occupancy</h2>
            <table>
              <thead>
                <tr>
                  <th>Status</th>
                  <th>n</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(s.occupancy_counts).map(([k, n]) => (
                  <tr key={k}>
                    <td>{k}</td>
                    <td>{n}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="note">GAP_THROUGH is a crossing without observed occupancy. E1 does not fill it.</p>
          </>
        )}

        {view === "models" && (
          <>
            <h2>E2 scenarios (partial = 1)</h2>
            <p className="muted">q is an assumption, not a measured fill rate.</p>
            <table>
              <thead>
                <tr>
                  <th>Scenario</th>
                  <th>EV</th>
                  <th>p05</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(s.e2).map(([k, d]) => (
                  <tr key={k}>
                    <td>{k}</td>
                    <td>{fmt(d.gross_expectancy)}</td>
                    <td>{fmt(d.p05)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="muted">E3 empirical = NOT_AVAILABLE · E4 L2/queue = NOT_AVAILABLE · L4 = NOT_AVAILABLE</p>
            <h2>Splits (E1)</h2>
            <table>
              <thead>
                <tr>
                  <th>Split</th>
                  <th>n</th>
                  <th>E1</th>
                  <th>80→40</th>
                  <th>Flag</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(s.by_split).map(([k, v]) => (
                  <tr key={k}>
                    <td>{k}</td>
                    <td>{v.n}</td>
                    <td>{fmt(v.e1.gross_expectancy)}</td>
                    <td>{fmt(v.stop.gross_expectancy)}</td>
                    <td>{v.sample_flag ?? v.e1.sample_status ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {view === "drill" && (
          <>
            <h2>Audit preview ({dash.audit_rows} rows on disk)</h2>
            <p className="muted">docs/research/EXECUTION_INTEGRITY_ENGINE/trade_level_audit.parquet</p>
            <table>
              <thead>
                <tr>
                  <th>Sport</th>
                  <th>Date</th>
                  <th>L2</th>
                  <th>Occ</th>
                  <th>E1 filled</th>
                  <th>E1 ¢</th>
                  <th>80→40</th>
                  <th>Class</th>
                </tr>
              </thead>
              <tbody>
                {dash.audit_preview
                  .filter((r) => r.sport === sport)
                  .slice(0, 35)
                  .map((r, i) => (
                    <tr key={i}>
                      <td>{String(r.sport)}</td>
                      <td>{String(r.game_date)}</td>
                      <td>{String(r.opportunity_class)}</td>
                      <td>{String(r.market_occupancy_status)}</td>
                      <td>{String(r.e1_hedge_filled)}</td>
                      <td>{fmt(r.pnl_e1 as number)}</td>
                      <td>{fmt(r.pnl_stop_80_40 as number)}</td>
                      <td>{String(r.path_class)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </>
        )}
      </main>
    </div>
  );
}
