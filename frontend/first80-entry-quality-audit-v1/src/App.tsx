import { Fragment, useEffect, useState } from "react";

type Surv = { n: number; k: number; pct: number | null; ci95: (number | null)[] };
type Sum = {
  filter?: string;
  class?: string;
  kind?: string;
  n: number;
  survivors?: number;
  stops?: number;
  leaks?: number;
  survival: Surv;
  surv?: number | null;
  ci?: (number | null)[];
  ev?: number | null;
  gross_ev_8040_cents: number | null;
  lo?: number;
  hi?: number;
  threshold_cents?: number;
  subset?: string;
  pct_of_universe?: number | null;
  mean_subsequent_path_t1_t10?: number | null;
};
type Ev = { sport: string; id: string; ticker: string; date: string; prev: number | null; entry: number | null; jump: number | null; over: number | null; cls: string; access: string; phase: string; survived: boolean; stopped: boolean; window: { m: number; c: number }[] };
type Dash = {
  banner: string;
  verdict: [string, string];
  pbp_join: string;
  game_clock: string;
  reproduction: Record<string, { ok: boolean }>;
  baseline: Record<string, { n: number; surv: number; survivors: number; stops: number }>;
  high_access_rule: Record<string, number>;
  filters: Record<string, Sum[]>;
  jump_sweep: Record<string, Sum[]>;
  classes: Record<string, Sum[]>;
  jump_hist: Record<string, { lo: number; hi: number; n: number }[]>;
  overshoot_hist: Record<string, { lo: number; hi: number; n: number }[]>;
  overshoot_sweep: Record<string, Sum[]>;
  late_matrix: Record<string, { contract_phase: string; jump_bucket: string; n: number; survival: Surv; mean_overshoot?: number | null }[]>;
  shock: Record<string, { quantile: number; n: number; survival: Surv; mean_jump: number | null }[]>;
  splits: Record<string, { split: string; universe: string; n: number; survival: Surv }[]>;
  inspector: Record<string, Ev[]>;
  actual_fill_experiment: string;
};

const VIEWS = [
  ["baseline", "Baseline"],
  ["jumps", "Jump / overshoot"],
  ["waterfall", "Accessibility waterfall"],
  ["late", "Contract-time heatmap"],
  ["shock", "Shock score"],
  ["inspector", "Event inspector"],
] as const;

function fmt(n?: number | null, d = 2) {
  return n == null || Number.isNaN(n) ? "—" : n.toFixed(d);
}

function survPct(r?: { survival?: Surv; surv?: number | null } | null) {
  return r?.survival?.pct ?? r?.surv ?? null;
}

function Heat({
  rows,
}: {
  rows: { contract_phase: string; jump_bucket: string; n: number; survival: Surv }[];
}) {
  const phases = [">180m_to_close", "120-180m", "60-120m", "30-60m", "15-30m", "5-15m", "0-5m"];
  const jumps = ["<5", "5-10", "10-20", "20-30", ">=30"];
  const cell = (ph: string, jb: string) => rows.find((r) => r.contract_phase === ph && r.jump_bucket === jb);
  return (
    <div className="heat" style={{ gridTemplateColumns: `120px repeat(${jumps.length}, 1fr)` }}>
      <div className="cell muted">phase \ jump</div>
      {jumps.map((j) => (
        <div key={j} className="cell muted">
          {j}
        </div>
      ))}
      {phases.map((ph) => (
        <Fragment key={ph}>
          <div className="cell muted">{ph}</div>
          {jumps.map((j) => {
            const c = cell(ph, j);
            const p = c?.survival.pct;
            const tone = p == null ? "transparent" : p >= 80 ? "#1d3a2a" : p >= 70 ? "#1d1810" : "#2a1616";
            return (
              <div key={`${ph}-${j}`} className="cell" style={{ background: c && c.n ? tone : "transparent" }}>
                {c && c.n ? (
                  <>
                    n={c.n}
                    <br />
                    {fmt(p)}%
                  </>
                ) : (
                  "—"
                )}
              </div>
            );
          })}
        </Fragment>
      ))}
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

function Hist({ bins }: { bins: { lo: number; hi: number; n: number }[] }) {
  const m = Math.max(1, ...bins.map((b) => b.n));
  return (
    <div className="chart">
      <div className="bars">
        {bins.map((b) => (
          <div key={b.lo} className="bar" style={{ height: `${(100 * b.n) / m}%` }} title={`${b.lo}–${b.hi}: ${b.n}`} />
        ))}
      </div>
      <div className="caption">
        {bins[0]?.lo} → {bins[bins.length - 1]?.hi} · candle proxy, not a fill
      </div>
    </div>
  );
}

function Path({ w }: { w: { m: number; c: number }[] }) {
  if (!w.length) return null;
  const width = 640;
  const height = 180;
  const pad = { l: 36, r: 8, t: 10, b: 20 };
  const xs = w.map((p) => p.m);
  const ys = w.map((p) => p.c);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(50, ...ys);
  const maxY = Math.max(100, ...ys);
  const x = (v: number) => pad.l + ((v - minX) / (maxX - minX || 1)) * (width - pad.l - pad.r);
  const y = (v: number) => height - pad.b - ((v - minY) / (maxY - minY || 1)) * (height - pad.t - pad.b);
  return (
    <div className="chart">
      <svg viewBox={`0 0 ${width} ${height}`}>
        <line x1={x(0)} y1={pad.t} x2={x(0)} y2={height - pad.b} stroke="#5a3d14" />
        <line x1={pad.l} y1={y(80)} x2={width - pad.r} y2={y(80)} stroke="#3dba7a" strokeDasharray="4 3" />
        <polyline fill="none" stroke="#c8a25a" strokeWidth="1.6" points={w.map((p) => `${x(p.m)},${y(p.c)}`).join(" ")} />
      </svg>
      <div className="caption">T−10 → T+10 bid close. Gold line = path. Green = 80¢. Vertical = T0.</div>
    </div>
  );
}

export default function App() {
  const [dash, setDash] = useState<Dash | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [sport, setSport] = useState<"nba" | "ncaab">("ncaab");
  const [view, setView] = useState<(typeof VIEWS)[number][0]>("baseline");
  const [evId, setEvId] = useState(0);

  useEffect(() => {
    fetch("/data/dashboard.json")
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then(setDash)
      .catch((e: Error) => setErr(e.message));
  }, []);

  if (err) return <div className="main">Failed to load dashboard.json ({err})</div>;
  if (!dash) return <div className="main muted">Loading…</div>;

  const events = dash.inspector[sport] ?? [];
  const ev = events[evId] ?? events[0];
  const base = dash.baseline[sport];
  const ha = dash.filters[sport].find((r) => r.filter === "High accessibility proxy only");

  return (
    <div className="app">
      <div className="banner">{dash.banner}</div>
      <div className="top">
        <div className="brand">
          FIRST80 ENTRY QUALITY AUDIT V1
          <small>
            Verdict {dash.verdict[0]} · PBP {dash.pbp_join} · clock {dash.game_clock} · no arming
          </small>
        </div>
        <div className="ctrl">
          <label>Sport</label>
          <select value={sport} onChange={(e) => { setSport(e.target.value as typeof sport); setEvId(0); }}>
            <option value="ncaab">NCAAB</option>
            <option value="nba">NBA</option>
          </select>
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
        {view === "baseline" && (
          <>
            <p className="muted">{dash.verdict[1]}</p>
            <div className="row">
              <Card k="NBA survival" v={`${dash.baseline.nba.surv.toFixed(2)}%`} />
              <Card k="NCAAB survival" v={`${dash.baseline.ncaab.surv.toFixed(2)}%`} />
              <Card k={`${sport} HIGH_ACCESS`} v={`${fmt(survPct(ha))}%`} cls="warn" />
              <Card k="NBA gate" v={dash.reproduction.nba.ok ? "PASS" : "FAIL"} cls={dash.reproduction.nba.ok ? "pos" : "neg"} />
              <Card k="NCAAB gate" v={dash.reproduction.ncaab.ok ? "PASS" : "FAIL"} cls={dash.reproduction.ncaab.ok ? "pos" : "neg"} />
            </div>
            <p className="muted">
              Frozen {sport}: {base.survivors}/{base.n} survivors, {base.stops} close-40 stops. HIGH_ACCESS is a priori
              (jump&lt;{dash.high_access_rule.max_jump_cents}¢, close&lt;{dash.high_access_rule.max_close_cents}, persist≥
              {dash.high_access_rule.min_persist_78_85}, approach steps≥{dash.high_access_rule.min_up_steps_5m}). Not fit to P&L.
            </p>
            <h2>Primary class</h2>
            <table>
              <thead>
                <tr>
                  <th>Class</th>
                  <th>N</th>
                  <th>Survival</th>
                  <th>EV proxy ¢</th>
                </tr>
              </thead>
              <tbody>
                {dash.classes[sport]
                  .filter((r) => r.kind === "primary_class")
                  .map((r) => (
                    <tr key={r.class}>
                      <td>{r.class}</td>
                      <td>{r.n}</td>
                      <td>{fmt(r.survival.pct)}</td>
                      <td>{fmt(r.gross_ev_8040_cents)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </>
        )}

        {view === "jumps" && (
          <>
            <h2>Jump_1m distribution (¢)</h2>
            <Hist bins={dash.jump_hist[sport]} />
            <h2>Entry close − 80 (overshoot)</h2>
            <Hist bins={dash.overshoot_hist[sport]} />
            <h2>Survival by entry close bucket</h2>
            <table>
              <thead>
                <tr>
                  <th>Close</th>
                  <th>N</th>
                  <th>Survival</th>
                </tr>
              </thead>
              <tbody>
                {dash.overshoot_sweep[sport]
                  .filter((r) => r.kind === "close_bucket")
                  .map((r) => (
                    <tr key={`${r.lo}`}>
                      <td>
                        {r.lo}–{r.hi}
                      </td>
                      <td>{r.n}</td>
                      <td>{fmt(survPct(r))}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
            <h2>Survival by entry-minute bid high</h2>
            <table>
              <thead>
                <tr>
                  <th>High</th>
                  <th>N</th>
                  <th>Survival</th>
                </tr>
              </thead>
              <tbody>
                {dash.overshoot_sweep[sport]
                  .filter((r) => r.kind === "high_bucket")
                  .map((r) => (
                    <tr key={`h-${r.lo}`}>
                      <td>
                        {r.lo}–{r.hi}
                      </td>
                      <td>{r.n}</td>
                      <td>{fmt(survPct(r))}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
            <h2>Jump threshold remaining universe</h2>
            <table>
              <thead>
                <tr>
                  <th>Keep jump &lt; T</th>
                  <th>N</th>
                  <th>% univ</th>
                  <th>Survival</th>
                  <th>Mean T+1..T+10 close</th>
                </tr>
              </thead>
              <tbody>
                {(dash.jump_sweep[sport] ?? [])
                  .filter((r) => r.subset === "remaining")
                  .map((r) => (
                    <tr key={r.threshold_cents}>
                      <td>{r.threshold_cents}¢</td>
                      <td>{r.n}</td>
                      <td>{fmt(r.pct_of_universe)}</td>
                      <td>{fmt(survPct(r))}</td>
                      <td>{fmt(r.mean_subsequent_path_t1_t10)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </>
        )}

        {view === "waterfall" && (
          <>
            <p className="muted">Structural filters defined a priori. This is accessibility validation, not strategy search.</p>
            <table>
              <thead>
                <tr>
                  <th>Filter</th>
                  <th>N</th>
                  <th>Survival</th>
                  <th>CI</th>
                  <th>EV ¢</th>
                </tr>
              </thead>
              <tbody>
                {dash.filters[sport].map((r) => (
                  <tr key={r.filter} className={r.filter === "Frozen baseline" || r.filter === "High accessibility proxy only" ? "hl" : undefined}>
                    <td>{r.filter}</td>
                    <td>{r.n}</td>
                    <td>{fmt(survPct(r))}</td>
                    <td>
                      {fmt(r.survival?.ci95?.[0] ?? r.ci?.[0])}–{fmt(r.survival?.ci95?.[1] ?? r.ci?.[1])}
                    </td>
                    <td>{fmt(r.ev ?? r.gross_ev_8040_cents)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <h2>TRAIN / VAL / OOS (frozen HIGH_ACCESS)</h2>
            <table>
              <thead>
                <tr>
                  <th>Split</th>
                  <th>Universe</th>
                  <th>N</th>
                  <th>Survival</th>
                </tr>
              </thead>
              <tbody>
                {dash.splits[sport].map((r, i) => (
                  <tr key={i}>
                    <td>{r.split}</td>
                    <td>{r.universe}</td>
                    <td>{r.n}</td>
                    <td>{fmt(r.survival.pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {view === "late" && (
          <>
            <p className="muted">
              NOT game clock. Minutes until Kalshi market close. PBP join {dash.pbp_join}.
            </p>
            <Heat rows={dash.late_matrix[sport]} />
            <table>
              <thead>
                <tr>
                  <th>Phase</th>
                  <th>Jump</th>
                  <th>N</th>
                  <th>Survival</th>
                </tr>
              </thead>
              <tbody>
                {dash.late_matrix[sport]
                  .filter((r) => r.n > 0)
                  .map((r, i) => (
                    <tr key={i}>
                      <td>{r.contract_phase}</td>
                      <td>{r.jump_bucket}</td>
                      <td>{r.n}</td>
                      <td>{fmt(r.survival.pct)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </>
        )}

        {view === "shock" && (
          <>
            <p className="muted">ENTRY_SHOCK_SCORE quintiles. Edges frozen on TRAIN. Descriptive, not a live filter.</p>
            <table>
              <thead>
                <tr>
                  <th>Q</th>
                  <th>N</th>
                  <th>Mean jump</th>
                  <th>Survival</th>
                </tr>
              </thead>
              <tbody>
                {dash.shock[sport].map((r) => (
                  <tr key={r.quantile}>
                    <td>Q{r.quantile}</td>
                    <td>{r.n}</td>
                    <td>{fmt(r.mean_jump)}</td>
                    <td>{fmt(r.survival.pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {view === "inspector" && ev && (
          <>
            <div className="ctrl" style={{ maxWidth: 520 }}>
              <label>Largest jumps (top {events.length})</label>
              <select value={String(evId)} onChange={(e) => setEvId(Number(e.target.value))}>
                {events.map((e, i) => (
                  <option key={e.id + e.ticker} value={i}>
                    {e.date} {e.ticker} jump {fmt(e.jump, 1)} → {fmt(e.entry, 1)}
                  </option>
                ))}
              </select>
            </div>
            <div className="row">
              <Card k="Prev → entry" v={`${fmt(ev.prev, 1)} → ${fmt(ev.entry, 1)}`} />
              <Card k="Jump" v={`${fmt(ev.jump, 1)}¢`} cls="warn" />
              <Card k="Class" v={ev.cls} />
              <Card k="Outcome" v={ev.survived ? "survive" : ev.stopped ? "stop" : "leak"} />
            </div>
            <Path w={ev.window} />
            <p className="muted">
              {ev.access} · contract phase {ev.phase} · candle path, not a fill
            </p>
            <h2>Largest jumps</h2>
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Ticker</th>
                  <th>Prev</th>
                  <th>Entry</th>
                  <th>Jump</th>
                  <th>Over</th>
                  <th>Phase</th>
                  <th>Class</th>
                  <th>Out</th>
                </tr>
              </thead>
              <tbody>
                {events.slice(0, 25).map((e, i) => (
                  <tr key={e.id + e.ticker} className={i === evId ? "hl" : undefined} onClick={() => setEvId(i)}>
                    <td>{e.date}</td>
                    <td>{e.ticker}</td>
                    <td>{fmt(e.prev, 1)}</td>
                    <td>{fmt(e.entry, 1)}</td>
                    <td>{fmt(e.jump, 1)}</td>
                    <td>{fmt(e.over, 1)}</td>
                    <td>{e.phase}</td>
                    <td>{e.cls}</td>
                    <td>{e.survived ? "survive" : e.stopped ? "stop" : "leak"}</td>
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
