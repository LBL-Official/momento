import { useEffect, useState } from "react";

type StratumRec = {
  n_cells?: number;
  row_count_train?: number;
  unique_trade_count_sum?: number;
  median_unique_trade_count?: number;
  median_N_EFF_TRADE?: number;
};

type Dash = {
  program: string;
  banner: string;
  schema_version: string;
  research_date: string;
  central_question: string;
  prominent: string;
  support_not_independence: string;
  r_bar_formula: string;
  synthesis: {
    token?: string;
    flags?: Record<string, boolean>;
    note?: string;
    questions?: Record<string, string>;
    inputs?: Record<string, number | null>;
  };
  gates: Record<string, { status: string }>;
  counts: { rows: number; trades: number };
  cell_stratum_occupancy?: Record<string, StratumRec | string>;
  support_preview?: Record<string, StratumRec>;
  rel_a: {
    by_split?: Record<
      string,
      {
        overall?: { spearman_abs_da_vs_unique_trades?: number; P_abs_ge?: Record<string, number>; mean_abs_da?: number };
        by_stratum?: Record<string, { n?: number; n_trades?: number; mean_abs_da?: number; median_abs_da?: number }>;
      }
    >;
  };
  rel_b: {
    by_split?: Record<
      string,
      {
        abs_ge_5?: {
          n_rows?: number;
          n_trades?: number;
          median_TRAIN_unique_trades?: number;
          median_N_EFF_TRADE?: number;
          scoring_path?: Record<string, number>;
          support_distribution?: Record<string, number>;
        };
        abs_ge_10?: { n_rows?: number; median_TRAIN_unique_trades?: number; median_N_EFF_TRADE?: number; scoring_path?: Record<string, number> };
        baseline_abs_lt_1?: { median_TRAIN_unique_trades?: number; median_N_EFF_TRADE?: number; scoring_path?: Record<string, number> };
      }
    >;
  };
  exposure: { by_split?: Record<string, { mean_fraction_sparse?: number; spearman_abs_da_vs_min_support?: number; n_trades?: number }> };
  shift: {
    tv_train_oos?: number;
    tv_train_val?: number;
    by_split?: Record<
      string,
      { pct_on_train_observed_m1?: number; scoring_path_rates?: Record<string, number>; rare_cell_row_share_by_stratum?: Record<string, number> }
    >;
  };
  stability: {
    by_split?: Record<
      string,
      {
        overall?: { spearman_mean_da_r_bar?: number; high_low?: { status?: string; spread_hi_minus_lo_r_bar?: number; n_lo?: number; n_hi?: number } };
        by_min_support_stratum?: Record<string, { n_trades?: number; spearman_mean_da_r_bar?: number }>;
      }
    >;
  };
  bootstrap?: { oos_spearman_mean_da_r_bar?: { mean?: number; p05?: number; p95?: number; meaning?: string } };
  map_integrity?: { n_m0?: number; n_m1?: number; m0_m1_calls?: number };
  four_fields?: string[];
  four_field_defs?: Record<string, string>;
  limitations: string[];
};

const TABS = [
  "Overview",
  "Independent Support",
  "Cell Geometry",
  "SIR vs Support",
  "Extreme SIR Sources",
  "Trade Support Exposure",
  "Distribution Shift",
  "Temporal Stability",
  "Support-Stratified Replication",
  "Structural Synthesis",
  "Limitations",
] as const;

const STRATA = ["0", "1", "2-4", "5-9", "10-19", "20-49", "50+"];
const SPLITS = ["TRAIN", "VALIDATION", "OOS"] as const;
const FOUR_TABS = new Set<(typeof TABS)[number]>(["Independent Support", "Cell Geometry", "Extreme SIR Sources", "Distribution Shift"]);

function fmt(v: number | null | undefined, d = 3): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toFixed(d);
}

function FourFields({ dash }: { dash: Dash }) {
  const defs = dash.four_field_defs || {};
  return (
    <div className="four">
      {(dash.four_fields || ["EXACT_CELL_EXISTS", "TRAIN_UNIQUE_TRADE_SUPPORT", "N_EFF_TRADE", "SCORING_PATH"]).map((f) => (
        <div className="card" key={f}>
          <div className="k">{f}</div>
          <div className="v small">{defs[f] || f}</div>
        </div>
      ))}
    </div>
  );
}

export default function App() {
  const [dash, setDash] = useState<Dash | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tab, setTab] = useState<(typeof TABS)[number]>("Overview");

  useEffect(() => {
    fetch("/data/dashboard.json")
      .then((r) => {
        if (!r.ok) throw new Error(`dashboard.json ${r.status}`);
        return r.json();
      })
      .then(setDash)
      .catch((e: Error) => setErr(e.message));
  }, []);

  if (err) return <div className="err">Failed to load static artifact: {err}</div>;
  if (!dash) return <div className="err">Loading DRE V7 research artifact…</div>;

  const boot = dash.bootstrap?.oos_spearman_mean_da_r_bar || {};

  return (
    <div className="app">
      <div className="banner">{dash.banner}</div>
      <div className="note">{dash.prominent}</div>
      <div className="top">
        <div className="brand">
          DRE V7
          <small>Structural support · {dash.schema_version} · {dash.research_date}</small>
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
        {FOUR_TABS.has(tab) && <FourFields dash={dash} />}

        {tab === "Overview" && (
          <>
            <div className="note">Δα_state ≠ EDGE · CONDITIONAL INFORMATION ≠ EXECUTION · REPEATED POSSESSIONS ≠ INDEPENDENT OUTCOMES · LIVE DEPLOYMENT: NOT AUTHORIZED</div>
            <h2>Central question</h2>
            <p>{dash.central_question}</p>
            <div className="row">
              <div className="card">
                <div className="k">Synthesis token</div>
                <div className="v warn">{dash.synthesis.token}</div>
              </div>
              <div className="card">
                <div className="k">Maps / refit</div>
                <div className="v">{dash.map_integrity?.n_m0}/{dash.map_integrity?.n_m1} · m0_m1={dash.map_integrity?.m0_m1_calls}</div>
              </div>
              <div className="card">
                <div className="k">Panel</div>
                <div className="v">{dash.counts.rows} / {dash.counts.trades}</div>
              </div>
              <div className="card">
                <div className="k">Live</div>
                <div className="v neg">NOT AUTHORIZED</div>
              </div>
            </div>
            <h2>Gates</h2>
            <table>
              <thead><tr><th>Gate</th><th>Status</th></tr></thead>
              <tbody>
                {Object.entries(dash.gates).map(([k, g]) => (
                  <tr key={k}><td>{k}</td><td className={g.status === "PASS" ? "pass" : "warn"}>{g.status}</td></tr>
                ))}
              </tbody>
            </table>
            <p className="caption">{dash.support_not_independence}</p>
          </>
        )}

        {tab === "Independent Support" && (
          <>
            <div className="note">CELL_GEOMETRY_DIAGNOSTIC · UNIQUE_TRADE_SUPPORT ≠ independence · N_eff ≠ sample size</div>
            <table>
              <thead>
                <tr>
                  <th>stratum</th>
                  <th>n cells</th>
                  <th>TRAIN rows</th>
                  <th>TRAIN_UNIQUE_TRADE_SUPPORT sum</th>
                  <th>median unique trades</th>
                  <th>median N_EFF_TRADE</th>
                  <th>EXACT_CELL_EXISTS</th>
                </tr>
              </thead>
              <tbody>
                {STRATA.map((s) => {
                  const occ = dash.cell_stratum_occupancy?.[s];
                  const o = occ && typeof occ === "object" ? occ : {};
                  const p = dash.support_preview?.[s] || {};
                  return (
                    <tr key={s}>
                      <td>{s}</td>
                      <td>{o.n_cells ?? p.n_cells ?? "—"}</td>
                      <td>{o.row_count_train ?? p.row_count_train ?? "—"}</td>
                      <td>{p.unique_trade_count_sum ?? "—"}</td>
                      <td>{fmt(p.median_unique_trade_count)}</td>
                      <td>{fmt(p.median_N_EFF_TRADE)}</td>
                      <td>{s === "0" ? "false / missing" : "true on TRAIN-observed cells"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="caption">These four fields are never merged into one support chip. A well-populated cell can still have low unique-trade support.</p>
          </>
        )}

        {tab === "Cell Geometry" && (
          <>
            <div className="note">EXACT_CELL_EXISTS ≠ TRAIN_UNIQUE_TRADE_SUPPORT ≠ N_EFF_TRADE ≠ SCORING_PATH</div>
            <table>
              <thead>
                <tr>
                  <th>split</th>
                  <th>SCORING_PATH M1_EXACT</th>
                  <th>SCORING_PATH M0_FALLBACK</th>
                  <th>SCORING_PATH GLOBAL</th>
                  <th>pct on TRAIN M1</th>
                </tr>
              </thead>
              <tbody>
                {SPLITS.map((s) => {
                  const r = dash.shift.by_split?.[s];
                  return (
                    <tr key={s}>
                      <td>{s}</td>
                      <td>{fmt(r?.scoring_path_rates?.M1_EXACT)}</td>
                      <td>{fmt(r?.scoring_path_rates?.M0_FALLBACK)}</td>
                      <td>{fmt(r?.scoring_path_rates?.GLOBAL_FALLBACK)}</td>
                      <td>{fmt(r?.pct_on_train_observed_m1)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="caption">M0 fallback is a scoring path, not a support magnitude. Exact-cell existence is not unique-trade support.</p>
          </>
        )}

        {tab === "SIR vs Support" && (
          <>
            <div className="note">Relationship A · STATE_OCCUPANCY_WEIGHTED DIAGNOSTIC</div>
            <table>
              <thead><tr><th>stratum</th><th>n rows</th><th>n trades</th><th>mean |da|</th><th>median |da|</th></tr></thead>
              <tbody>
                {STRATA.map((s) => {
                  const r = dash.rel_a.by_split?.OOS?.by_stratum?.[s];
                  return (
                    <tr key={s}>
                      <td>{s}</td>
                      <td>{r?.n ?? "—"}</td>
                      <td>{r?.n_trades ?? "—"}</td>
                      <td>{fmt(r?.mean_abs_da)}</td>
                      <td>{fmt(r?.median_abs_da)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="caption">
              OOS Spearman(|da|, unique TRAIN trades) {fmt(dash.rel_a.by_split?.OOS?.overall?.spearman_abs_da_vs_unique_trades)}
              {" · "}TRAIN {fmt(dash.rel_a.by_split?.TRAIN?.overall?.spearman_abs_da_vs_unique_trades)}
            </p>
          </>
        )}

        {tab === "Extreme SIR Sources" && (
          <>
            <div className="note">Relationship B · CELL_GEOMETRY_DIAGNOSTIC · forensic, not predictive</div>
            <div className="row">
              <div className="card">
                <div className="k">OOS |da|≥5 n trades</div>
                <div className="v">{dash.rel_b.by_split?.OOS?.abs_ge_5?.n_trades}</div>
              </div>
              <div className="card">
                <div className="k">TRAIN_UNIQUE_TRADE_SUPPORT median</div>
                <div className="v">{fmt(dash.rel_b.by_split?.OOS?.abs_ge_5?.median_TRAIN_unique_trades)}</div>
              </div>
              <div className="card">
                <div className="k">N_EFF_TRADE median</div>
                <div className="v">{fmt(dash.rel_b.by_split?.OOS?.abs_ge_5?.median_N_EFF_TRADE)}</div>
              </div>
              <div className="card">
                <div className="k">Baseline |da|&lt;1 unique trades</div>
                <div className="v">{fmt(dash.rel_b.by_split?.OOS?.baseline_abs_lt_1?.median_TRAIN_unique_trades)}</div>
              </div>
            </div>
            <h2>SCORING_PATH on OOS |da|≥5 (separate from support)</h2>
            <table>
              <thead><tr><th>path</th><th>n rows</th></tr></thead>
              <tbody>
                {Object.entries(dash.rel_b.by_split?.OOS?.abs_ge_5?.scoring_path || {}).map(([k, n]) => (
                  <tr key={k}><td>{k}</td><td>{n}</td></tr>
                ))}
              </tbody>
            </table>
            <h2>TRAIN unique-trade stratum occupancy of OOS |da|≥5 rows</h2>
            <table>
              <thead><tr><th>stratum</th><th>n rows</th></tr></thead>
              <tbody>
                {STRATA.map((s) => (
                  <tr key={s}><td>{s}</td><td>{dash.rel_b.by_split?.OOS?.abs_ge_5?.support_distribution?.[s] ?? "—"}</td></tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {tab === "Trade Support Exposure" && (
          <>
            <div className="note">Relationship C · TRADE_BALANCED · one residual per trade</div>
            <p className="caption">{dash.r_bar_formula}</p>
            <table>
              <thead><tr><th>split</th><th>n trades</th><th>mean frac sparse</th><th>Spearman(|mean_da|, min support)</th></tr></thead>
              <tbody>
                {SPLITS.map((s) => (
                  <tr key={s}>
                    <td>{s}</td>
                    <td>{dash.exposure.by_split?.[s]?.n_trades ?? "—"}</td>
                    <td>{fmt(dash.exposure.by_split?.[s]?.mean_fraction_sparse)}</td>
                    <td>{fmt(dash.exposure.by_split?.[s]?.spearman_abs_da_vs_min_support)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {tab === "Distribution Shift" && (
          <>
            <div className="note">TV and scoring-path rates · not edge</div>
            <div className="row">
              <div className="card"><div className="k">TV TRAIN–VAL</div><div className="v">{fmt(dash.shift.tv_train_val)}</div></div>
              <div className="card"><div className="k">TV TRAIN–OOS</div><div className="v">{fmt(dash.shift.tv_train_oos)}</div></div>
              <div className="card"><div className="k">OOS on TRAIN M1 cells</div><div className="v">{fmt(dash.shift.by_split?.OOS?.pct_on_train_observed_m1)}</div></div>
            </div>
            <table>
              <thead>
                <tr>
                  <th>split</th>
                  <th>SCORING_PATH M1_EXACT</th>
                  <th>SCORING_PATH M0_FALLBACK</th>
                  <th>SCORING_PATH GLOBAL</th>
                  <th>rare 0</th>
                  <th>rare 1</th>
                  <th>rare 2–4</th>
                </tr>
              </thead>
              <tbody>
                {SPLITS.map((s) => {
                  const r = dash.shift.by_split?.[s];
                  return (
                    <tr key={s}>
                      <td>{s}</td>
                      <td>{fmt(r?.scoring_path_rates?.M1_EXACT)}</td>
                      <td>{fmt(r?.scoring_path_rates?.M0_FALLBACK)}</td>
                      <td>{fmt(r?.scoring_path_rates?.GLOBAL_FALLBACK)}</td>
                      <td>{fmt(r?.rare_cell_row_share_by_stratum?.["0"])}</td>
                      <td>{fmt(r?.rare_cell_row_share_by_stratum?.["1"])}</td>
                      <td>{fmt(r?.rare_cell_row_share_by_stratum?.["2-4"])}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </>
        )}

        {tab === "Temporal Stability" && (
          <>
            <div className="note">TEMPORAL_STABILITY_DIAGNOSTIC · TRADE_BALANCED</div>
            <table>
              <thead><tr><th>split</th><th>Spearman(mean_da, r_bar)</th><th>high–low</th><th>n_lo / n_hi</th></tr></thead>
              <tbody>
                {SPLITS.map((s) => {
                  const r = dash.stability.by_split?.[s]?.overall;
                  return (
                    <tr key={s}>
                      <td>{s}</td>
                      <td>{fmt(r?.spearman_mean_da_r_bar)}</td>
                      <td>{r?.high_low?.status ?? "—"}</td>
                      <td>{r?.high_low?.n_lo ?? "—"} / {r?.high_low?.n_hi ?? "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="caption">
              OOS bootstrap mean {fmt(boot.mean)} · p05 {fmt(boot.p05)} · p95 {fmt(boot.p95)}. {boot.meaning}
            </p>
          </>
        )}

        {tab === "Support-Stratified Replication" && (
          <>
            <div className="note">Within locked min-support strata · no new letters</div>
            <table>
              <thead><tr><th>stratum</th><th>OOS n</th><th>Spearman</th></tr></thead>
              <tbody>
                {STRATA.map((s) => {
                  const r = dash.stability.by_split?.OOS?.by_min_support_stratum?.[s];
                  return (
                    <tr key={s}>
                      <td>{s}</td>
                      <td>{r?.n_trades ?? "—"}</td>
                      <td>{fmt(r?.spearman_mean_da_r_bar)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </>
        )}

        {tab === "Structural Synthesis" && (
          <>
            <div className="row">
              <div className="card">
                <div className="k">Token</div>
                <div className="v warn">{dash.synthesis.token}</div>
              </div>
            </div>
            <table>
              <thead><tr><th>flag</th><th>on</th></tr></thead>
              <tbody>
                {Object.entries(dash.synthesis.flags || {}).map(([k, on]) => (
                  <tr key={k}><td>{k}</td><td>{String(on)}</td></tr>
                ))}
              </tbody>
            </table>
            <h2>Questions (structural only)</h2>
            <ol>
              {Object.entries(dash.synthesis.questions || {}).map(([k, q]) => (
                <li key={k}><strong>{k}.</strong> {q}</li>
              ))}
            </ol>
            <p>{dash.synthesis.note}</p>
            <div className="note">LIVE DEPLOYMENT: NOT AUTHORIZED</div>
          </>
        )}

        {tab === "Limitations" && (
          <ul>
            {dash.limitations.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
