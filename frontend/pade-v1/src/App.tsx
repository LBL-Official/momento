import { useEffect, useMemo, useState } from "react";

type GateB = { status: string; first80: number; matched: number; unmatched: number };
type GateC = { status: string; ok: number; fail: number };
type GateD = { status: string; n_possessions: number; ambiguous: number; ambiguous_pct: number; mean_poss_per_game: number };
type ModelRow = {
  family: string;
  target: string;
  target_label: string;
  split: string;
  n: number;
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
  p_min40_k5: number | null;
  p_min40_end: number | null;
  p_rec10_k5: number | null;
  p_jump40: number | null;
  p_settle: number | null;
};
type Example = {
  event_id: string;
  ticker: string;
  nba_game_id: string;
  split: string;
  entry_ts: number;
  a1: string;
  ot?: boolean;
  candles: { ts: number; bid: number | null; low: number | null; high: number | null }[];
  possessions: { idx: number; period: number; clock: string; elapsed: number; wall: number; off: string; sh: number; sa: number; result: string }[];
  path: {
    possessions_since_entry: number;
    price: number | null;
    d: number | null;
    v3: number | null;
    a: number | null;
    age: number | null;
    diff: number | null;
    off: boolean | null;
    period: number | null;
    clock: string | null;
    conf: string | null;
  }[];
};
type Dash = {
  program: string;
  banner: string;
  created_utc: string;
  verdict: Record<string, string | number | null>;
  gates: { A: string; B: GateB; C: GateC; D: GateD; E: { status: string; counts: Record<string, number> }; F: string; G: string; H: string };
  counts: Record<string, number>;
  alignment: { counts: Record<string, number>; pct: Record<string, number>; gap: Record<string, number | null>; poor_games: number };
  models: ModelRow[];
  remaining: Record<string, Record<string, { n: number; mae?: number; rmse?: number; bias?: number }>>;
  surfaces: Surface[];
  severe: { n: number; recover_10_end: number; recover_pct: number | null; settle_yes: number; settle_pct: number | null };
  examples: Example[];
  leakage: { feature: string; availability: string; used_as_model_feature: boolean }[];
};

const TABS = [
  "Overview",
  "Timeline",
  "Trade path",
  "Alignment",
  "Models",
  "Surface",
  "Remaining",
] as const;

function fmt(v: number | null | undefined, d = 3): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toFixed(d);
}
function pct(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return `${(100 * v).toFixed(1)}%`;
}
function tone(s: string | number | null | undefined): string {
  const t = String(s || "");
  if (t === "PASS" || t === "YES" || t === "READY FOR V2") return "pass";
  if (t === "FAIL" || t === "NO" || t === "NOT READY") return "fail";
  if (t === "WARNING" || t === "PARTIAL" || t === "INCONCLUSIVE") return "warn";
  return "";
}

function Card({ k, v, cls }: { k: string; v: string | number; cls?: string }) {
  return (
    <div className="card">
      <div className="k">{k}</div>
      <div className={`v ${cls || ""}`}>{v}</div>
    </div>
  );
}

function Bars({ items }: { items: { label: string; n: number; color?: string }[] }) {
  const m = Math.max(1, ...items.map((x) => x.n));
  return (
    <div className="bars">
      {items.map((x) => (
        <div key={x.label} className="bar" style={{ height: `${(100 * x.n) / m}%`, background: x.color || "#c8a25a" }}>
          <span>{x.label}</span>
        </div>
      ))}
    </div>
  );
}

function PathChart({ ex, hover, setHover }: { ex: Example; hover: number | null; setHover: (i: number | null) => void }) {
  const pts = ex.path.filter((p) => p.price != null);
  if (!pts.length) return <div className="muted">No as-of prices on this trade path.</div>;
  const w = 900;
  const h = 220;
  const xmin = 0;
  const xmax = Math.max(1, ...pts.map((p) => p.possessions_since_entry));
  const ys = pts.map((p) => p.price as number);
  const ymin = Math.min(0, ...ys) - 2;
  const ymax = Math.max(100, ...ys) + 2;
  const x = (v: number) => 24 + ((v - xmin) / (xmax - xmin)) * (w - 40);
  const y = (v: number) => h - 20 - ((v - ymin) / (ymax - ymin)) * (h - 36);
  const d = pts.map((p, i) => `${i ? "L" : "M"}${x(p.possessions_since_entry)},${y(p.price as number)}`).join(" ");
  return (
    <div className="chart">
      <svg viewBox={`0 0 ${w} ${h}`} onMouseLeave={() => setHover(null)}>
        <line x1="24" y1={y(80)} x2={w - 12} y2={y(80)} stroke="#c8a25a" strokeDasharray="4 4" strokeWidth="1" />
        <line x1="24" y1={y(40)} x2={w - 12} y2={y(40)} stroke="#e05d5d" strokeDasharray="4 4" strokeWidth="1" />
        <path d={d} fill="none" stroke="#e6edf3" strokeWidth="1.6" />
        {pts.map((p, i) => (
          <circle
            key={i}
            cx={x(p.possessions_since_entry)}
            cy={y(p.price as number)}
            r={hover === i ? 4 : 2}
            fill={p.conf === "HIGH" ? "#3dba7a" : p.conf === "MEDIUM" ? "#c8a25a" : "#e0a14a"}
            onMouseEnter={() => setHover(i)}
          />
        ))}
      </svg>
    </div>
  );
}

function CandleChart({ ex }: { ex: Example }) {
  const cs = ex.candles.filter((c) => c.bid != null);
  if (!cs.length) return <div className="muted">No candles in window.</div>;
  const w = 900;
  const h = 220;
  const t0 = cs[0].ts;
  const t1 = cs[cs.length - 1].ts;
  const ys = cs.map((c) => c.bid as number);
  const ymin = Math.min(0, ...ys) - 2;
  const ymax = Math.max(100, ...ys) + 2;
  const x = (t: number) => 24 + ((t - t0) / Math.max(1, t1 - t0)) * (w - 40);
  const y = (v: number) => h - 20 - ((v - ymin) / (ymax - ymin)) * (h - 36);
  const d = cs.map((c, i) => `${i ? "L" : "M"}${x(c.ts)},${y(c.bid as number)}`).join(" ");
  const entryX = x(ex.entry_ts);
  return (
    <div className="chart">
      <svg viewBox={`0 0 ${w} ${h}`}>
        <line x1={entryX} y1="8" x2={entryX} y2={h - 12} stroke="#c8a25a" strokeWidth="1.2" />
        <path d={d} fill="none" stroke="#8ec8ff" strokeWidth="1.4" />
        {ex.possessions
          .filter((p) => p.wall >= t0 && p.wall <= t1)
          .map((p) => (
            <line key={p.idx} x1={x(p.wall)} y1={h - 18} x2={x(p.wall)} y2={h - 8} stroke="#3d5a4a" strokeWidth="1" />
          ))}
      </svg>
    </div>
  );
}

export default function App() {
  const [dash, setDash] = useState<Dash | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tab, setTab] = useState<(typeof TABS)[number]>("Overview");
  const [exI, setExI] = useState(0);
  const [hover, setHover] = useState<number | null>(null);
  const [split, setSplit] = useState("OOS");
  const [target, setTarget] = useState("y_min_le_40_k5");

  useEffect(() => {
    fetch("/data/dashboard.json")
      .then((r) => {
        if (!r.ok) throw new Error(`dashboard.json ${r.status}`);
        return r.json();
      })
      .then(setDash)
      .catch((e: Error) => setErr(e.message));
  }, []);

  const ex = dash?.examples[exI];
  const hoverRow = ex && hover != null ? ex.path.filter((p) => p.price != null)[hover] : null;
  const targets = useMemo(() => {
    if (!dash) return [];
    return [...new Set(dash.models.map((m) => m.target))];
  }, [dash]);
  const modelView = useMemo(() => {
    if (!dash) return [];
    return dash.models.filter((m) => m.split === split && m.target === target);
  }, [dash, split, target]);

  if (err) return <div className="err">{err}</div>;
  if (!dash) return <div className="err">Loading PADE V1…</div>;

  const confItems = ["HIGH", "MEDIUM", "LOW", "UNRESOLVED"].map((k) => ({
    label: k,
    n: dash.alignment.counts[k] || 0,
    color: k === "HIGH" ? "#3dba7a" : k === "MEDIUM" ? "#c8a25a" : k === "LOW" ? "#e0a14a" : "#e05d5d",
  }));

  return (
    <div className="app">
      <div className="banner">{dash.banner}</div>
      <div className="top">
        <div className="brand">
          MOMENTO — POSSESSION-ADJUSTED DETERIORATION ENGINE V1
          <small>State layer research · not a trading dashboard · {dash.created_utc}</small>
        </div>
        {(tab === "Timeline" || tab === "Trade path") && dash.examples.length > 0 && (
          <div className="ctrl">
            <label>Example game</label>
            <select value={exI} onChange={(e) => { setExI(Number(e.target.value)); setHover(null); }}>
              {dash.examples.map((e, i) => (
                <option key={e.event_id} value={i}>
                  {e.split} {e.a1} {e.event_id}
                </option>
              ))}
            </select>
          </div>
        )}
        {tab === "Models" && (
          <>
            <div className="ctrl">
              <label>Split</label>
              <select value={split} onChange={(e) => setSplit(e.target.value)}>
                {["TRAIN", "VALIDATION", "OOS"].map((s) => (
                  <option key={s}>{s}</option>
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
          </>
        )}
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
            <h2>Verdict</h2>
            <div className="row">
              {Object.entries(dash.verdict)
                .filter(([k]) => !k.startsWith("oos_"))
                .map(([k, v]) => (
                  <Card key={k} k={k.replaceAll("_", " ")} v={String(v)} cls={tone(v)} />
                ))}
            </div>
            <h2>OOS headline — P(min ≤ 40 within 5 possessions)</h2>
            <div className="row">
              <Card k="B2 Brier" v={fmt(dash.verdict.oos_brier_B2_min40_k5 as number)} />
              <Card k="M3 Brier" v={fmt(dash.verdict.oos_brier_M3_min40_k5 as number)} />
              <Card k="M5 Brier" v={fmt(dash.verdict.oos_brier_M5_min40_k5 as number)} />
              <Card k="B2 AUC" v={fmt(dash.verdict.oos_auc_B2_min40_k5 as number)} />
              <Card k="M3 AUC" v={fmt(dash.verdict.oos_auc_M3_min40_k5 as number)} />
              <Card k="M5 AUC" v={fmt(dash.verdict.oos_auc_M5_min40_k5 as number)} />
            </div>
            <p className="caption">
              Grade C model comparison. Possession value is YES only if M3 beats B2 on both OOS Brier and AUC.
              Execution fills remain unobserved (grade D).
            </p>
            <h2>Gates</h2>
            <div className="row">
              <Card k="A FIRST-80" v={dash.gates.A} cls={tone(dash.gates.A)} />
              <Card k="B game IDs" v={`${dash.gates.B.status} ${dash.gates.B.matched}/1230`} cls={tone(dash.gates.B.status)} />
              <Card k="C PBP" v={`${dash.gates.C.status} ${dash.gates.C.ok}`} cls={tone(dash.gates.C.status)} />
              <Card k="D possessions" v={`${dash.gates.D.status} ${dash.gates.D.n_possessions}`} cls={tone(dash.gates.D.status)} />
              <Card k="E alignment" v={dash.gates.E.status} cls={tone(dash.gates.E.status)} />
              <Card k="F market leak" v={dash.gates.F} cls={tone(dash.gates.F)} />
              <Card k="G game leak" v={dash.gates.G} cls={tone(dash.gates.G)} />
              <Card k="H split isolation" v={dash.gates.H} cls={tone(dash.gates.H)} />
            </div>
            <h2>Panel counts</h2>
            <div className="row">
              <Card k="panel rows" v={dash.counts.panel_rows} />
              <Card k="HIGH+MEDIUM" v={dash.counts.panel_high_med} />
              <Card k="trades" v={dash.counts.trades_with_panel} />
              <Card k="possessions" v={dash.counts.possessions} />
              <Card k="train games" v={dash.counts.train_games} />
              <Card k="OOS games" v={dash.counts.oos_games} />
            </div>
            <h2>Severe temporary deterioration (≥20¢ from entry)</h2>
            <div className="row">
              <Card k="states" v={dash.severe.n} />
              <Card k="later recover ≥10¢" v={`${dash.severe.recover_10_end} (${dash.severe.recover_pct ?? "—"}%)`} />
              <Card k="settle YES" v={`${dash.severe.settle_yes} (${dash.severe.settle_pct ?? "—"}%)`} />
            </div>
          </>
        )}

        {tab === "Timeline" && ex && (
          <>
            <h2>
              {ex.event_id} · {ex.nba_game_id} · {ex.split} · A1 {ex.a1}
              {ex.ot ? " · OT" : ""}
            </h2>
            <p className="caption">
              Blue: Kalshi A1 yes-bid close (1-minute candles). Gold line: FIRST-80 entry timestamp. Green ticks:
              possession starts (observed timeActual). Evidence level A for timestamps; candle is not a fill.
            </p>
            <CandleChart ex={ex} />
            <table>
              <thead>
                <tr>
                  <th>poss</th>
                  <th>Q</th>
                  <th>clock</th>
                  <th>off</th>
                  <th>score</th>
                  <th>result</th>
                </tr>
              </thead>
              <tbody>
                {ex.possessions.slice(0, 40).map((p) => (
                  <tr key={p.idx}>
                    <td>{p.idx}</td>
                    <td>{p.period}</td>
                    <td>{p.clock}</td>
                    <td>{p.off}</td>
                    <td>
                      {p.sh}-{p.sa}
                    </td>
                    <td>{p.result}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="grade">Showing first 40 possessions. Full sequence is in 03_possessions.parquet.</p>
          </>
        )}

        {tab === "Trade path" && ex && (
          <>
            <h2>Trade × possession path · {ex.ticker}</h2>
            <p className="caption">
              X = possessions since entry. Y = as-of A1 yes-bid. Gold=80, red=40. Point color is alignment
              confidence. Hover for the state vector. Repeated prices across possessions are stale candles, not
              proof the market was unchanged.
            </p>
            <PathChart ex={ex} hover={hover} setHover={setHover} />
            <div className="hover">
              {hoverRow
                ? `poss+${hoverRow.possessions_since_entry} price=${hoverRow.price} D=${hoverRow.d} v3=${hoverRow.v3} a=${hoverRow.a} age=${hoverRow.age}s diff=${hoverRow.diff} A1_off=${hoverRow.off} Q${hoverRow.period} ${hoverRow.clock} conf=${hoverRow.conf}`
                : "Hover a point."}
            </div>
          </>
        )}

        {tab === "Alignment" && (
          <>
            <h2>Candle → timeActual as-of confidence</h2>
            <Bars items={confItems} />
            <div className="row">
              {Object.entries(dash.alignment.pct).map(([k, v]) => (
                <Card key={k} k={k} v={`${v}%`} />
              ))}
              <Card k="gap p50 (s)" v={fmt(dash.alignment.gap.p50, 1)} />
              <Card k="gap p90 (s)" v={fmt(dash.alignment.gap.p90, 1)} />
              <Card k="poor games" v={dash.alignment.poor_games} />
            </div>
            <p className="caption">
              Gate uses in-game candles only (between first and last observed timeActual).
              HIGH: last event ≤30s and next ≤90s, same period. MEDIUM: last event ≤120s. LOW: ≤600s or
              intermission. Pre-tip / post-game scan-window candles are stored as UNRESOLVED and excluded
              from the gate. Unresolved in-game rows are stored, not dropped.
            </p>
          </>
        )}

        {tab === "Models" && (
          <>
            <h2>
              Nested families · {split} · {target}
            </h2>
            <table>
              <thead>
                <tr>
                  <th>family</th>
                  <th>n</th>
                  <th>AUC</th>
                  <th>Brier</th>
                  <th>logloss</th>
                  <th>ECE</th>
                  <th>status</th>
                </tr>
              </thead>
              <tbody>
                {modelView.map((m) => (
                  <tr key={m.family}>
                    <td>{m.family}</td>
                    <td>{m.n}</td>
                    <td>{fmt(m.auc)}</td>
                    <td>{fmt(m.brier)}</td>
                    <td>{fmt(m.logloss)}</td>
                    <td>{fmt(m.ece)}</td>
                    <td>{m.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="caption">
              B0 price only · B1 + deterioration + wall age · B2 + game clock/score · M3 + possession time · M4 +
              velocity · M5 + acceleration/vol/staleness. Logistic regression, complete-case, game-level splits.
              Grade C.
            </p>
          </>
        )}

        {tab === "Surface" && (
          <>
            <h2>Empirical forward surface by current as-of price (OOS)</h2>
            <table>
              <thead>
                <tr>
                  <th>price</th>
                  <th>n</th>
                  <th>P(min≤40 | 5 poss)</th>
                  <th>P(min≤40 | end)</th>
                  <th>P(rec≥10 | 5)</th>
                  <th>P(jump 40)</th>
                  <th>P(settle YES)</th>
                </tr>
              </thead>
              <tbody>
                {dash.surfaces
                  .filter((s) => s.split === "OOS")
                  .map((s) => (
                    <tr key={`${s.price_lo}`}>
                      <td>
                        {s.price_lo}–{s.price_hi}
                      </td>
                      <td>{s.n}</td>
                      <td>{pct(s.p_min40_k5)}</td>
                      <td>{pct(s.p_min40_end)}</td>
                      <td>{pct(s.p_rec10_k5)}</td>
                      <td>{pct(s.p_jump40)}</td>
                      <td>{pct(s.p_settle)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
            <p className="caption">
              Empirical rates on HIGH+MEDIUM alignment states. Not an executable stop rule. Jump is an observed
              candle gap proxy, not IOC slippage.
            </p>
          </>
        )}

        {tab === "Remaining" && (
          <>
            <h2>Remaining-possessions estimates vs realized future count</h2>
            <table>
              <thead>
                <tr>
                  <th>split</th>
                  <th>model</th>
                  <th>n</th>
                  <th>MAE</th>
                  <th>RMSE</th>
                  <th>bias</th>
                </tr>
              </thead>
              <tbody>
                {["TRAIN", "VALIDATION", "OOS"].flatMap((s) =>
                  ["R1", "R2", "R3"].map((m) => {
                    const r = dash.remaining[s]?.[m] || { n: 0 };
                    return (
                      <tr key={`${s}${m}`}>
                        <td>{s}</td>
                        <td>{m}</td>
                        <td>{r.n}</td>
                        <td>{fmt(r.mae)}</td>
                        <td>{fmt(r.rmse)}</td>
                        <td>{fmt(r.bias)}</td>
                      </tr>
                    );
                  }),
                )}
              </tbody>
            </table>
            <p className="caption">
              R1 = TRAIN historical seconds/possession × remaining game seconds. R2 = current-game pace. R3 =
              period-aware TRAIN pace. Actual remaining possessions are evaluation labels only — never features.
            </p>
            <h2>Leakage audit (excerpt)</h2>
            <table>
              <thead>
                <tr>
                  <th>field</th>
                  <th>availability</th>
                  <th>model feature?</th>
                </tr>
              </thead>
              <tbody>
                {dash.leakage.slice(0, 24).map((r) => (
                  <tr key={r.feature}>
                    <td>{r.feature}</td>
                    <td>{r.availability}</td>
                    <td>{r.used_as_model_feature ? "yes" : "no"}</td>
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
