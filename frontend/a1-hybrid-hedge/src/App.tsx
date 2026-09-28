import { useEffect, useMemo, useState } from "react";

type Metrics = {
  n?: number;
  mean?: number;
  median?: number;
  std?: number;
  p01?: number;
  p05?: number;
  es05?: number;
  max_dd?: number;
  worst?: number;
  win_rate?: number;
  inc_vs_original?: number;
  tail_p05_vs_original?: number;
  catastrophic_rate?: number;
  bootstrap_iid?: { ci95_lo?: number; ci95_hi?: number };
};

type Surf = {
  H: number;
  band: string;
  persist_k: number;
  fallback: string;
  split: string;
  n: number;
  close_hits: number;
  in_band: number;
  gaps: number;
  modeled_fill_rate_causal?: number | null;
  jump_through_rate?: number | null;
  avg_obs_hedge?: number | null;
  original: Metrics;
  hold: Metrics;
  theoretical_hybrid: Metrics;
  theoretical_replace: Metrics;
  conservative_causal: Metrics;
  lookahead_persist: Metrics;
};

type Sport = {
  n: number;
  split_n: Record<string, number>;
  date_min: string;
  date_max: string;
  experiment_a: {
    reproduction: { ok: boolean; n: number; hold: number; stop: number; v1: number };
    hold: Metrics;
    stop_80_40: Metrics;
    v1_threshold_h40: Metrics;
    by_split: Record<string, { n: number; hold: Metrics; stop: Metrics; v1: Metrics }>;
  };
  surface_full_exact: Surf[];
  surface_val_exact: Surf[];
  named_full: Surf[];
  fallback_full: Surf[];
  prob_full: Array<Metrics & { H: number; band: string; q: number; label: string }>;
  partial_full: Array<Metrics & { H: number; band: string; partial: number; label: string }>;
  gaps: Array<Record<string, unknown>>;
  val_pareto: Array<{ H: number; mean: number; p05: number; inc: number; pareto: boolean }>;
  plateau: { width: number; h_lo: number | null; h_hi: number | null; best_h: number | null };
  locked_h: number;
  lock_reason: string;
  locked: Record<string, Surf | null>;
  neighbors: Surf[];
  verdict: string;
  verdict_note: string;
  surface_sym_val: Surf[];
};

type Dash = {
  banner: string;
  meta: Record<string, unknown>;
  sports: Record<string, Sport>;
  audit_preview: Array<Record<string, unknown>>;
  audit_rows: number;
};

const VIEWS = [
  ["verdict", "Verdict"],
  ["baseline", "Baseline"],
  ["surface", "Hedge surface"],
  ["frontier", "Efficient frontier"],
  ["gaps", "Gaps"],
  ["prob", "Prob / partial"],
  ["fallback", "Fallback"],
  ["stability", "Train / VAL / OOS"],
  ["audit", "Audit"],
] as const;

function fmt(n?: number | null, d = 2) {
  return n == null || Number.isNaN(n) ? "—" : n.toFixed(d);
}
function signed(n?: number | null) {
  if (n == null || Number.isNaN(n)) return "—";
  const s = n > 0 ? "+" : "";
  return s + n.toFixed(2);
}

function LineChart({
  series,
  yLabel,
}: {
  series: { name: string; pts: { x: number; y: number }[] }[];
  yLabel: string;
}) {
  const w = 720;
  const h = 240;
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
  const colors = ["#c8a25a", "#6ea8d6", "#3dba7a", "#e05d5d", "#9b7ed9"];
  return (
    <div className="chart">
      <svg viewBox={`0 0 ${w} ${h}`}>
        <line x1={pad.l} y1={y(0)} x2={w - pad.r} y2={y(0)} stroke="#232a33" />
        <text x={8} y={16} fill="#8b98a5" fontSize="10">
          {yLabel}
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
        · modeled ¢ / contract · not a confirmed fill
      </div>
    </div>
  );
}

function Scatter({
  pts,
}: {
  pts: { x: number; y: number; label: string; on?: boolean }[];
}) {
  if (!pts.length) return null;
  const w = 520;
  const h = 280;
  const pad = 36;
  const xs = pts.map((p) => p.x);
  const ys = pts.map((p) => p.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const x = (v: number) => pad + ((v - minX) / (maxX - minX || 1)) * (w - 2 * pad);
  const y = (v: number) => h - pad - ((v - minY) / (maxY - minY || 1)) * (h - 2 * pad);
  return (
    <div className="chart">
      <svg viewBox={`0 0 ${w} ${h}`}>
        <text x={8} y={16} fill="#8b98a5" fontSize="10">
          p05 (right-is-better) vs EV
        </text>
        {pts.map((p) => (
          <g key={p.label}>
            <circle cx={x(p.x)} cy={y(p.y)} r={p.on ? 5 : 3} fill={p.on ? "#c8a25a" : "#6ea8d6"} />
            <text x={x(p.x) + 6} y={y(p.y) + 3} fill="#8b98a5" fontSize="9">
              {p.label}
            </text>
          </g>
        ))}
      </svg>
      <div className="caption">Gold = Pareto non-dominated on VALIDATION conservative causal</div>
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
  const [sport, setSport] = useState("nba");
  const [split, setSplit] = useState("FULL");
  const [band, setBand] = useState("exact");
  const [view, setView] = useState<(typeof VIEWS)[number][0]>("verdict");

  useEffect(() => {
    fetch("/data/dashboard.json")
      .then((r) => {
        if (!r.ok) throw new Error("dashboard.json missing — run the A1 engine");
        return r.json();
      })
      .then(setDash)
      .catch((e: Error) => setErr(e.message));
  }, []);

  const s = dash?.sports[sport];
  const surf = useMemo(() => {
    if (!s) return [];
    return s.surface_full_exact.filter((r) => r.split === split && r.band === "exact");
  }, [s, split]);

  if (err) return <p className="main neg">{err}</p>;
  if (!dash || !s) return <p className="main muted">Loading A1 outputs…</p>;

  const locked = s.locked[split] ?? s.locked.FULL;
  const repro = s.experiment_a.reproduction;

  return (
    <div className="app">
      <div className="banner">{dash.banner}</div>
      <header className="top">
        <div className="brand">
          A1 HYBRID HEDGE
          <small>
            {String(dash.meta.universe_version)} · {String(dash.meta.code_version)} · hash{" "}
            {String(dash.meta.config_hash)}
          </small>
        </div>
        <div className="ctrl">
          <label>Sport / universe</label>
          <select value={sport} onChange={(e) => setSport(e.target.value)}>
            <option value="nba">NBA n={dash.sports.nba?.n}</option>
            <option value="ncaab">NCAAB P5 vs P5 n={dash.sports.ncaab?.n}</option>
          </select>
        </div>
        <div className="ctrl">
          <label>Split</label>
          <select value={split} onChange={(e) => setSplit(e.target.value)}>
            <option>FULL</option>
            <option>TRAIN</option>
            <option>VALIDATION</option>
            <option>OOS</option>
          </select>
        </div>
        <div className="ctrl">
          <label>Named band (tables)</label>
          <select value={band} onChange={(e) => setBand(e.target.value)}>
            <option value="exact">exact H</option>
            <option value="band_37_42">37–42</option>
            <option value="band_35_45">35–45</option>
            <option value="focus_17_22">17–22</option>
            <option value="focus_27_32">27–32</option>
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
        {view === "verdict" && (
          <>
            <h2>Decision</h2>
            <div className="row">
              <Card k="Verdict" v={s.verdict.replaceAll("_", " ")} cls="warn" />
              <Card k="Locked H (VAL only)" v={`${s.locked_h}¢`} />
              <Card k="Plateau" v={`${s.plateau.h_lo}–${s.plateau.h_hi}`} />
              <Card k="Universe" v={`${s.n} trades`} />
            </div>
            <p className="note">{s.verdict_note}</p>
            <p className="note">{s.lock_reason}</p>
            <p className="muted">
              Dates {s.date_min} → {s.date_max}. TRAIN {s.split_n.TRAIN} · VAL {s.split_n.VALIDATION} ·
              OOS {s.split_n.OOS}. Fill probability and persist-k are scenarios. Fees unresolved.
            </p>
          </>
        )}

        {view === "baseline" && (
          <>
            <h2>Experiment A — reproduce FIRST80</h2>
            <div className="row">
              <Card k="Gate" v={repro.ok ? "PASS" : "FAIL"} cls={repro.ok ? "pos" : "neg"} />
              <Card k="Hold EV" v={fmt(repro.hold)} />
              <Card k="80→40 EV" v={fmt(repro.stop)} />
              <Card k="V1 @40 EV" v={fmt(repro.v1)} />
            </div>
            <table>
              <thead>
                <tr>
                  <th>Split</th>
                  <th>n</th>
                  <th>Hold</th>
                  <th>80→40</th>
                  <th>V1 H=40</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(s.experiment_a.by_split).map(([k, v]) => (
                  <tr key={k}>
                    <td>{k}</td>
                    <td>{v.n}</td>
                    <td>{fmt(v.hold.mean)}</td>
                    <td>{fmt(v.stop.mean)}</td>
                    <td>{fmt(v.v1.mean)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {view === "surface" && (
          <>
            <h2>H = 10…60 exact band · {split}</h2>
            <LineChart
              yLabel="EV ¢"
              series={[
                {
                  name: "80→40",
                  pts: surf.map((r) => ({ x: r.H, y: r.original.mean ?? 0 })),
                },
                {
                  name: "Theoretical replace (fake @H)",
                  pts: surf.map((r) => ({ x: r.H, y: r.theoretical_replace.mean ?? 0 })),
                },
                {
                  name: "Conservative causal",
                  pts: surf.map((r) => ({ x: r.H, y: r.conservative_causal.mean ?? 0 })),
                },
                {
                  name: "Lookahead persist k=3",
                  pts: surf.map((r) => ({ x: r.H, y: r.lookahead_persist.mean ?? 0 })),
                },
              ]}
            />
            <LineChart
              yLabel="fill / gap"
              series={[
                {
                  name: "In-band rate",
                  pts: surf.map((r) => ({ x: r.H, y: r.modeled_fill_rate_causal ?? 0 })),
                },
                {
                  name: "Gap rate",
                  pts: surf.map((r) => ({ x: r.H, y: r.jump_through_rate ?? 0 })),
                },
              ]}
            />
            <table>
              <thead>
                <tr>
                  <th>H</th>
                  <th>In-band</th>
                  <th>Gaps</th>
                  <th>Avg obs H</th>
                  <th>Theo replace</th>
                  <th>Causal</th>
                  <th>vs 80→40</th>
                  <th>p05</th>
                </tr>
              </thead>
              <tbody>
                {surf
                  .filter((r) => r.H % 2 === 0)
                  .map((r) => (
                    <tr key={r.H} className={r.H === s.locked_h ? "hl" : ""}>
                      <td>{r.H}</td>
                      <td>{r.in_band}</td>
                      <td>{r.gaps}</td>
                      <td>{fmt(r.avg_obs_hedge)}</td>
                      <td>{fmt(r.theoretical_replace.mean)}</td>
                      <td>{fmt(r.conservative_causal.mean)}</td>
                      <td className={(r.conservative_causal.inc_vs_original ?? 0) >= 0 ? "pos" : "neg"}>
                        {signed(r.conservative_causal.inc_vs_original)}
                      </td>
                      <td>{fmt(r.conservative_causal.p05)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
            <h2>Named bands (FULL, persist k=3)</h2>
            <table>
              <thead>
                <tr>
                  <th>Band</th>
                  <th>In-band</th>
                  <th>Gaps</th>
                  <th>Causal EV</th>
                  <th>vs 80→40</th>
                </tr>
              </thead>
              <tbody>
                {s.named_full.map((r) => (
                  <tr key={r.band}>
                    <td>{r.band}</td>
                    <td>{r.in_band}</td>
                    <td>{r.gaps}</td>
                    <td>{fmt(r.conservative_causal.mean)}</td>
                    <td>{signed(r.conservative_causal.inc_vs_original)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {view === "frontier" && (
          <>
            <h2>VALIDATION Pareto — conservative causal exact</h2>
            <Scatter
              pts={s.val_pareto.map((p) => ({
                x: p.mean,
                y: p.p05,
                label: String(p.H),
                on: p.pareto,
              }))}
            />
            <table>
              <thead>
                <tr>
                  <th>H</th>
                  <th>VAL EV</th>
                  <th>p05</th>
                  <th>vs 80→40</th>
                  <th>Pareto</th>
                </tr>
              </thead>
              <tbody>
                {s.val_pareto
                  .filter((p) => p.H % 2 === 0 || p.pareto)
                  .map((p) => (
                    <tr key={p.H} className={p.pareto ? "pareto" : ""}>
                      <td>{p.H}</td>
                      <td>{fmt(p.mean)}</td>
                      <td>{fmt(p.p05)}</td>
                      <td>{signed(p.inc)}</td>
                      <td>{p.pareto ? "yes" : ""}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </>
        )}

        {view === "gaps" && (
          <>
            <h2>Experiment F — jump-through</h2>
            <p className="note">
              23→75 is a gap. Booking A2 @ 40 there is fictional. Causal book misses and falls back
              to 80→40.
            </p>
            <table>
              <thead>
                <tr>
                  <th>Split</th>
                  <th>Close hits</th>
                  <th>In-band</th>
                  <th>Gaps</th>
                  <th>Theo − causal</th>
                </tr>
              </thead>
              <tbody>
                {s.gaps
                  .filter((g) => typeof g.split === "string")
                  .map((g) => (
                    <tr key={String(g.split)}>
                      <td>{String(g.split)}</td>
                      <td>{String(g.n_close ?? "—")}</td>
                      <td>{String(g.n_in_band)}</td>
                      <td>{String(g.n_gap)}</td>
                      <td>{fmt(g.delta_theo_minus_causal as number)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </>
        )}

        {view === "prob" && (
          <>
            <h2>q and partial-fill scenarios (FULL)</h2>
            <p className="muted">These are sensitivity assumptions, not observed fill rates.</p>
            <table>
              <thead>
                <tr>
                  <th>H / band</th>
                  <th>q</th>
                  <th>EV</th>
                  <th>vs 80→40</th>
                  <th>p05</th>
                </tr>
              </thead>
              <tbody>
                {s.prob_full
                  .filter((r) => r.band === "exact" || r.band === band)
                  .map((r) => (
                    <tr key={`${r.H}-${r.band}-${r.q}`}>
                      <td>
                        {r.H} {r.band}
                      </td>
                      <td>{r.q}</td>
                      <td>{fmt(r.mean)}</td>
                      <td>{signed(r.inc_vs_original)}</td>
                      <td>{fmt(r.p05)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
            <h2>Partial completion</h2>
            <table>
              <thead>
                <tr>
                  <th>H / band</th>
                  <th>Fraction</th>
                  <th>EV</th>
                  <th>vs 80→40</th>
                </tr>
              </thead>
              <tbody>
                {s.partial_full
                  .filter((r) => r.band === "exact" || r.band === band)
                  .map((r) => (
                    <tr key={`${r.H}-${r.band}-${r.partial}`}>
                      <td>
                        {r.H} {r.band}
                      </td>
                      <td>{r.partial}</td>
                      <td>{fmt(r.mean)}</td>
                      <td>{signed(r.inc_vs_original)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </>
        )}

        {view === "fallback" && (
          <>
            <h2>Fallback sensitivity (FULL)</h2>
            <p className="note">
              Headline fallback is legacy 80→40. conservative_next_observation and settlement_only
              refuse the fictional A1 −40 fill.
            </p>
            <table>
              <thead>
                <tr>
                  <th>H</th>
                  <th>Band</th>
                  <th>Fallback</th>
                  <th>Causal EV</th>
                  <th>vs 80→40</th>
                </tr>
              </thead>
              <tbody>
                {s.fallback_full.map((r) => (
                  <tr key={`${r.H}-${r.band}-${r.fallback}`}>
                    <td>{r.H}</td>
                    <td>{r.band}</td>
                    <td>{r.fallback}</td>
                    <td>{fmt(r.conservative_causal.mean)}</td>
                    <td>{signed(r.conservative_causal.inc_vs_original)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {view === "stability" && (
          <>
            <h2>Locked H = {s.locked_h} across splits</h2>
            <table>
              <thead>
                <tr>
                  <th>Split</th>
                  <th>Causal EV</th>
                  <th>vs 80→40</th>
                  <th>p05</th>
                  <th>Max DD</th>
                  <th>IID CI</th>
                </tr>
              </thead>
              <tbody>
                {(["TRAIN", "VALIDATION", "OOS", "FULL"] as const).map((k) => {
                  const r = s.locked[k];
                  const c = r?.conservative_causal;
                  return (
                    <tr key={k} className={k === "OOS" ? "hl" : ""}>
                      <td>{k}</td>
                      <td>{fmt(c?.mean)}</td>
                      <td>{signed(c?.inc_vs_original)}</td>
                      <td>{fmt(c?.p05)}</td>
                      <td>{fmt(c?.max_dd)}</td>
                      <td>
                        {fmt(c?.bootstrap_iid?.ci95_lo)} … {fmt(c?.bootstrap_iid?.ci95_hi)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="muted">
              Selected on VALIDATION only. OOS is one locked test. Isolated 0.04¢ maxima are ignored
              in favor of plateaus.
            </p>
          </>
        )}

        {view === "audit" && (
          <>
            <h2>Trade audit preview ({dash.audit_rows} rows on disk)</h2>
            <p className="muted">Full parquet: docs/research/A1_HYBRID_HEDGE/trade_audit.parquet</p>
            <table>
              <thead>
                <tr>
                  <th>Sport</th>
                  <th>Date</th>
                  <th>H</th>
                  <th>Tier</th>
                  <th>Obs</th>
                  <th>Orig</th>
                  <th>Causal</th>
                </tr>
              </thead>
              <tbody>
                {dash.audit_preview.slice(0, 40).map((r, i) => (
                  <tr key={i}>
                    <td>{String(r.sport)}</td>
                    <td>{String(r.game_date)}</td>
                    <td>{String(r.hedge_target)}</td>
                    <td>{String(r.tier)}</td>
                    <td>{fmt(r.obs_close as number)}</td>
                    <td>{fmt(r.pnl_original as number)}</td>
                    <td>{fmt(r.pnl_conservative as number)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {locked && view === "verdict" && (
          <>
            <h2>Locked book on {split}</h2>
            <div className="row">
              <Card k="Causal EV" v={fmt(locked.conservative_causal.mean)} />
              <Card
                k="vs 80→40"
                v={signed(locked.conservative_causal.inc_vs_original)}
                cls={(locked.conservative_causal.inc_vs_original ?? 0) >= 0 ? "pos" : "neg"}
              />
              <Card k="p05" v={fmt(locked.conservative_causal.p05)} />
              <Card k="Max DD" v={fmt(locked.conservative_causal.max_dd)} />
            </div>
          </>
        )}
      </main>
    </div>
  );
}
