import { useEffect, useState } from "react";

type Dash = {
  program: string;
  banner: string;
  schema_version: string;
  research_date: string;
  central_question: string;
  verdict: { HEADLINE: string; name?: string; flags: Record<string, boolean>; note?: string; d_ceiling?: string };
  gates: Record<string, { status: string }>;
  counts: { rows: number; trades: number };
  distribution: { by_split?: Record<string, { TRADE_BALANCED?: { mean?: number; p50?: number; max_abs?: number; P_abs_ge?: Record<string, number> } }> };
  concentration: {
    by_split?: Record<string, { top10_share?: number; shares?: Array<{ frac: number; share?: number; n_top?: number }> }>;
    concentration_not_evidence?: string;
  };
  rank: { by_split?: Record<string, { spread_hi_minus_lo?: number; deciles?: Array<{ decile: number; n_trades: number; mean_pi?: number; mean_sir?: number }>; spearman_sir_pi?: number }>; replication?: { token?: string; ok?: boolean } };
  residual: { by_split?: Record<string, { spread_hi_minus_lo?: number; spearman_sir_r?: number; deciles?: Array<{ decile: number; mean_r?: number; n_trades: number }> }>; replication?: { token?: string; ok?: boolean } };
  extremes: {
    by_split?: Record<
      string,
      { tails?: Array<{ k: number; positive?: { n_trades?: number; mean_r?: number }; negative?: { n_trades?: number; mean_r?: number } }> }
    >;
  };
  persistence: { by_split?: Record<string, { n_ever_5?: number; median_duration_k5?: number; persistent_n?: number; ephemeral_n?: number }> };
  path: { by_split?: Record<string, { n_signals?: number; mean_min_p?: number; mean_last_p?: number }>; disclaimer?: string; role?: string };
  limitations: string[];
  concentration_not_evidence?: string;
  material_inventory_note?: string;
};

const TABS = [
  "Overview",
  "SIR Distribution",
  "Concentration",
  "Rank Separation",
  "Residual-on-Residual",
  "Extreme States",
  "Persistence",
  "Forward Path (diagnostic)",
  "Limitations",
  "Verdict",
] as const;

function fmt(v: number | null | undefined, d = 3): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toFixed(d);
}
function grade(s: string): string {
  if (s === "PASS" || s === "TRUE" || s === "D") return "pass";
  if (s === "FAIL" || s === "NOT AUTHORIZED" || s === "A") return "neg";
  if (s === "PARTIAL" || s === "INCONCLUSIVE" || s === "B" || s === "C" || s === "UNCLASSIFIED_PRE_REGISTERED_OUTCOME") return "warn";
  return "muted";
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
  if (!dash) return <div className="err">Loading DRE V6 research artifact…</div>;

  const oosD = dash.distribution.by_split?.OOS?.TRADE_BALANCED || {};
  const trainD = dash.distribution.by_split?.TRAIN?.TRADE_BALANCED || {};
  const valD = dash.distribution.by_split?.VALIDATION?.TRADE_BALANCED || {};

  return (
    <div className="app">
      <div className="banner">{dash.banner}</div>
      <div className="top">
        <div className="brand">
          DRE V6
          <small>State information residual · {dash.schema_version} · {dash.research_date}</small>
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
            <div className="note">Δα_state ≠ EDGE · CONDITIONAL INFORMATION ≠ EXECUTION · CANDLE PATH ≠ FILL · LIVE DEPLOYMENT: NOT AUTHORIZED</div>
            <h2>Central question</h2>
            <p>{dash.central_question}</p>
            <div className="row">
              <div className="card">
                <div className="k">Headline</div>
                <div className={`v ${grade(dash.verdict.HEADLINE)}`}>{dash.verdict.HEADLINE} — {dash.verdict.name}</div>
              </div>
              <div className="card">
                <div className="k">Live deployment</div>
                <div className="v neg">NOT AUTHORIZED</div>
              </div>
              <div className="card">
                <div className="k">Panel</div>
                <div className="v">{dash.counts.rows} / {dash.counts.trades}</div>
              </div>
            </div>
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
            <p className="caption">V5 Verdict B is historical. Primary weighting = TRADE_BALANCED. One observation per trade.</p>
          </>
        )}

        {tab === "SIR Distribution" && (
          <>
            <div className="note">TRADE_BALANCED · P(|mean_SIR_i| ≥ k) · 1/2/5/10¢ frozen</div>
            <table>
              <thead>
                <tr>
                  <th>split</th>
                  <th>mean</th>
                  <th>P50</th>
                  <th>max |SIR|</th>
                  <th>P≥1</th>
                  <th>P≥2</th>
                  <th>P≥5</th>
                  <th>P≥10</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ["TRAIN", trainD],
                  ["VALIDATION", valD],
                  ["OOS", oosD],
                ].map(([s, d]) => {
                  const x = d as Record<string, unknown>;
                  const p = (x.P_abs_ge || {}) as Record<string, number>;
                  return (
                    <tr key={String(s)}>
                      <td>{String(s)}</td>
                      <td>{fmt(x.mean as number)}</td>
                      <td>{fmt(x.p50 as number)}</td>
                      <td>{fmt(x.max_abs as number)}</td>
                      <td>{fmt(p["1"])}</td>
                      <td>{fmt(p["2"])}</td>
                      <td>{fmt(p["5"])}</td>
                      <td>{fmt(p["10"])}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </>
        )}

        {tab === "Concentration" && (
          <>
            <div className="note">{dash.concentration_not_evidence}</div>
            <table>
              <thead>
                <tr>
                  <th>split</th>
                  <th>top 1%</th>
                  <th>top 5%</th>
                  <th>top 10%</th>
                  <th>top 25%</th>
                </tr>
              </thead>
              <tbody>
                {["TRAIN", "VALIDATION", "OOS"].map((s) => {
                  const shares = dash.concentration.by_split?.[s]?.shares || [];
                  const at = (f: number) => shares.find((x) => Math.abs(x.frac - f) < 1e-12)?.share;
                  return (
                    <tr key={s}>
                      <td>{s}</td>
                      <td>{fmt(at(0.01))}</td>
                      <td>{fmt(at(0.05))}</td>
                      <td>{fmt(at(0.1))}</td>
                      <td>{fmt(at(0.25))}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="caption">TRADE_BALANCED geometry of |mean_SIR|. Verdict uses top 10% share ≥ 40% only. Concentration is not evidence by itself.</p>
          </>
        )}

        {tab === "Rank Separation" && (
          <>
            <div className="note">TRAIN-frozen deciles of mean_SIR · TRADE_BALANCED E[Π | decile]</div>
            <div className="row">
              <div className="card">
                <div className="k">OOS spread 10−1</div>
                <div className="v">{fmt(dash.rank.by_split?.OOS?.spread_hi_minus_lo)}</div>
              </div>
              <div className="card">
                <div className="k">Replication</div>
                <div className={`v ${grade(dash.rank.replication?.token || "")}`}>{dash.rank.replication?.token}</div>
              </div>
            </div>
            <table>
              <thead>
                <tr>
                  <th>decile</th>
                  <th>n</th>
                  <th>mean SIR</th>
                  <th>mean Π</th>
                </tr>
              </thead>
              <tbody>
                {(dash.rank.by_split?.OOS?.deciles || []).map((d) => (
                  <tr key={d.decile}>
                    <td>{d.decile}</td>
                    <td>{d.n_trades}</td>
                    <td>{fmt(d.mean_sir)}</td>
                    <td>{fmt(d.mean_pi)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {tab === "Residual-on-Residual" && (
          <>
            <div className="note">PRIMARY TRADE_BALANCED · E[R̄_i | mean_SIR_i]</div>
            <div className="row">
              <div className="card">
                <div className="k">OOS residual spread</div>
                <div className="v">{fmt(dash.residual.by_split?.OOS?.spread_hi_minus_lo)}</div>
              </div>
              <div className="card">
                <div className="k">Spearman</div>
                <div className="v">{fmt(dash.residual.by_split?.OOS?.spearman_sir_r)}</div>
              </div>
              <div className="card">
                <div className="k">Replication</div>
                <div className={`v ${grade(dash.residual.replication?.token || "")}`}>{dash.residual.replication?.token}</div>
              </div>
            </div>
            <table>
              <thead>
                <tr>
                  <th>decile</th>
                  <th>n</th>
                  <th>mean R̄</th>
                </tr>
              </thead>
              <tbody>
                {(dash.residual.by_split?.OOS?.deciles || []).map((d) => (
                  <tr key={d.decile}>
                    <td>{d.decile}</td>
                    <td>{d.n_trades}</td>
                    <td>{fmt(d.mean_r)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="caption">Occupancy residual-on-residual is a STATE_OCCUPANCY_WEIGHTED DIAGNOSTIC and is not shown as the economic test.</p>
          </>
        )}

        {tab === "Extreme States" && (
          <>
            <div className="note">Frozen tails 2/5/10¢ · TRADE_BALANCED · no post-OOS search</div>
            <table>
              <thead>
                <tr>
                  <th>k</th>
                  <th>+n</th>
                  <th>+ mean R̄</th>
                  <th>−n</th>
                  <th>− mean R̄</th>
                </tr>
              </thead>
              <tbody>
                {(dash.extremes.by_split?.OOS?.tails || []).map((t) => (
                  <tr key={t.k}>
                    <td>{t.k}</td>
                    <td>{t.positive?.n_trades}</td>
                    <td>{fmt(t.positive?.mean_r)}</td>
                    <td>{t.negative?.n_trades}</td>
                    <td>{fmt(t.negative?.mean_r)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {tab === "Persistence" && (
          <>
            <div className="note">PERSISTENCE ≠ EXECUTABILITY · duration = possessions with |Δα| ≥ 5¢</div>
            <div className="row">
              <div className="card">
                <div className="k">OOS ever ≥5¢</div>
                <div className="v">{dash.persistence.by_split?.OOS?.n_ever_5}</div>
              </div>
              <div className="card">
                <div className="k">Median duration</div>
                <div className="v">{fmt(dash.persistence.by_split?.OOS?.median_duration_k5, 1)}</div>
              </div>
            </div>
          </>
        )}

        {tab === "Forward Path (diagnostic)" && (
          <>
            <div className="note">{dash.path.disclaimer} · {dash.path.role} · forbidden in headline and V6-D</div>
            <p className="caption">OOS signals {dash.path.by_split?.OOS?.n_signals} · mean subsequent min P {fmt(dash.path.by_split?.OOS?.mean_min_p)} · last P {fmt(dash.path.by_split?.OOS?.mean_last_p)}</p>
          </>
        )}

        {tab === "Limitations" && (
          <ul>
            {dash.limitations.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        )}

        {tab === "Verdict" && (
          <>
            <div className="row">
              <div className="card">
                <div className="k">Headline</div>
                <div className={`v ${grade(dash.verdict.HEADLINE)}`}>{dash.verdict.HEADLINE} — {dash.verdict.name}</div>
              </div>
            </div>
            <table>
              <thead>
                <tr>
                  <th>flag</th>
                  <th>on</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(dash.verdict.flags).map(([k, on]) => (
                  <tr key={k}>
                    <td>{k}</td>
                    <td>{String(on)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p>{dash.verdict.note}</p>
            <p className="caption">{dash.verdict.d_ceiling}</p>
            <div className="note">LIVE DEPLOYMENT: NOT AUTHORIZED</div>
          </>
        )}
      </div>
    </div>
  );
}
