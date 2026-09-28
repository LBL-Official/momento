import { useEffect, useState } from "react";

type Surv = { n: number; k: number; pct: number | null; ci95: (number | null)[]; sample_flag?: string | null };
type Slim = {
  n: number | null;
  surv: number | null;
  ci: (number | null)[] | null;
  stops?: number | null;
  flag?: string | null;
  mean_mae?: number | null;
  median_mae?: number | null;
  mean_mfe?: number | null;
  class?: string | null;
  lo?: number | null;
  hi?: number | null;
  minutes?: number | null;
  share?: number | null;
  kind?: string | null;
  quantile?: number | null;
  cluster?: number | null;
  H?: number | null;
  split?: string | null;
  ev?: number | null;
};
type PathPt = { m: number; n: number; mean_bid: number | null };
type Dist = { n: number; median: number | null; mean?: number | null; availability: string };
type Dash = {
  banner: string;
  verdict: [string, string];
  reproduction: Record<string, { ok: boolean; n: number; survivors: number; stops: number; leaks: number; surv_pct: number }>;
  persist: Record<string, Slim[]>;
  mae: Record<string, Slim[]>;
  entry_price: Record<string, Slim[]>;
  barriers: Record<string, { n: number; p90_before_40: Surv; p95_before_40: Surv; p99_before_40: Surv }>;
  event_study: Record<string, Record<string, { n: number; path: PathPt[] }>>;
  vol: Record<string, Slim[]>;
  approach: Record<string, Slim[]>;
  winners: Record<string, Slim[]>;
  losers: Record<string, Record<string, Dist | number>>;
  winners_entry: Record<string, Record<string, Dist | number>>;
  time_res: Record<string, Slim[]>;
  season: Record<string, Slim[]>;
  capital: Record<string, { median_cents_per_minute: number; winners_median: number; stops_median: number; label: string }[]>;
  models: Record<string, { eval?: { split: string; n: number; logistic_auc: number | null; tree_acc: number | null; base_rate: number | null; flag: string | null }[]; logistic_coefs?: { feature: string; logistic_coef: number }[] }>;
  clusters: Record<string, Slim[]>;
  corr_labels: string[];
  corr: Record<string, (number | null)[][]>;
  conditional: Record<string, Slim[]>;
  hedge: Record<string, Slim[]>;
  unknowns: string[];
};

const VIEWS = [
  ["baseline", "Baseline"],
  ["persist", "Persistence"],
  ["mae", "MAE"],
  ["mfe", "MFE / barriers"],
  ["anatomy", "Winner vs loser"],
  ["study", "Event study"],
  ["vol", "Volatility"],
  ["approach", "Approach"],
  ["price", "Entry price"],
  ["time", "Time to resolution"],
  ["season", "Season"],
  ["depend", "Dependence"],
  ["compare", "NBA vs NCAAB"],
  ["unknowns", "Unknowns"],
] as const;

function fmt(n?: number | null, d = 2) {
  return n == null || Number.isNaN(n) ? "—" : n.toFixed(d);
}

function Card({ k, v, cls }: { k: string; v: string; cls?: string }) {
  return (
    <div className="card">
      <div className="k">{k}</div>
      <div className={`v ${cls ?? ""}`}>{v}</div>
    </div>
  );
}

function RateTable({ rows, extra }: { rows: Slim[]; extra?: "mae" | "share" | "minutes" | "quantile" | "cluster" }) {
  return (
    <table>
      <thead>
        <tr>
          <th>Slice</th>
          <th>N</th>
          <th>Survival</th>
          <th>CI</th>
          {extra === "mae" && <th>Median MAE</th>}
          {extra === "share" && <th>Share</th>}
          <th>Flag</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>
            <td>
              {r.class ??
                (r.minutes != null ? `≥${r.minutes}m` : null) ??
                (r.lo != null ? `${r.lo}–${r.hi}` : null) ??
                (r.quantile != null ? `Q${r.quantile}` : null) ??
                (r.cluster != null ? `C${r.cluster}` : null) ??
                r.kind}
            </td>
            <td>{r.n}</td>
            <td>{fmt(r.surv)}</td>
            <td>
              {fmt(r.ci?.[0])}–{fmt(r.ci?.[1])}
            </td>
            {extra === "mae" && <td>{fmt(r.median_mae)}</td>}
            {extra === "share" && <td>{fmt(r.share)}</td>}
            <td>{r.flag ?? ""}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Study({ paths }: { paths: Record<string, { n: number; path: PathPt[] }> }) {
  const keys = ["survivors", "stops", "gradual_jump_lt_10", "jump_ge_20"] as const;
  const colors: Record<string, string> = {
    survivors: "#3dba7a",
    stops: "#e05d5d",
    gradual_jump_lt_10: "#c8a25a",
    jump_ge_20: "#e0a14a",
  };
  const width = 720;
  const height = 220;
  const pad = { l: 36, r: 8, t: 10, b: 24 };
  const pts = keys.flatMap((k) => (paths[k]?.path ?? []).filter((p) => p.mean_bid != null));
  if (!pts.length) return <p className="muted">No event-study path.</p>;
  const minX = -5;
  const maxX = 30;
  const ys = pts.map((p) => p.mean_bid as number);
  const minY = Math.min(50, ...ys);
  const maxY = Math.max(100, ...ys);
  const x = (v: number) => pad.l + ((v - minX) / (maxX - minX || 1)) * (width - pad.l - pad.r);
  const y = (v: number) => height - pad.b - ((v - minY) / (maxY - minY || 1)) * (height - pad.t - pad.b);
  return (
    <div className="chart">
      <svg viewBox={`0 0 ${width} ${height}`}>
        <line x1={x(0)} y1={pad.t} x2={x(0)} y2={height - pad.b} stroke="#5a3d14" />
        <line x1={pad.l} y1={y(80)} x2={width - pad.r} y2={y(80)} stroke="#3dba7a" strokeDasharray="4 3" />
        {keys.map((k) => {
          const row = (paths[k]?.path ?? []).filter((p) => p.mean_bid != null);
          if (row.length < 2) return null;
          return (
            <polyline
              key={k}
              fill="none"
              stroke={colors[k]}
              strokeWidth="1.6"
              points={row.map((p) => `${x(p.m)},${y(p.mean_bid as number)}`).join(" ")}
            />
          );
        })}
      </svg>
      <div className="caption">
        Mean yes_bid_close T−5…T+30. Green=survivors, red=stops, gold=jump&lt;10, orange=jump≥20. POST-HOC, not a live signal.
      </div>
    </div>
  );
}

export default function App() {
  const [dash, setDash] = useState<Dash | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [sport, setSport] = useState<"nba" | "ncaab">("ncaab");
  const [view, setView] = useState<(typeof VIEWS)[number][0]>("baseline");

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

  const repro = dash.reproduction[sport];
  const cap = dash.capital[sport][0];

  return (
    <div className="app">
      <div className="banner">{dash.banner}</div>
      <div className="top">
        <div className="brand">
          FIRST80 UNANSWERED QUESTIONS AUDIT V2
          <small>Verdict {dash.verdict[0]} · no arming · candle path only</small>
        </div>
        <div className="ctrl">
          <label>Sport</label>
          <select value={sport} onChange={(e) => setSport(e.target.value as typeof sport)}>
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
              <Card k="NBA survival" v={`${dash.reproduction.nba.surv_pct.toFixed(2)}%`} />
              <Card k="NCAAB survival" v={`${dash.reproduction.ncaab.surv_pct.toFixed(2)}%`} />
              <Card k="NBA gate" v={dash.reproduction.nba.ok ? "PASS" : "FAIL"} cls={dash.reproduction.nba.ok ? "pos" : "neg"} />
              <Card k="NCAAB gate" v={dash.reproduction.ncaab.ok ? "PASS" : "FAIL"} cls={dash.reproduction.ncaab.ok ? "pos" : "neg"} />
            </div>
            <p className="muted">
              Frozen {sport}: {repro.survivors}/{repro.n} survivors, {repro.stops} close-40, {repro.leaks} leaks. POST-HOC
              descriptive. Not a live signal.
            </p>
          </>
        )}
        {view === "persist" && (
          <>
            <p className="muted">POST-HOC DESCRIPTIVE — NOT A LIVE ENTRY SIGNAL. Consecutive minutes at/above 80 after T0.</p>
            <h2>Require consecutive ≥ N minutes</h2>
            <RateTable rows={dash.persist[sport].filter((r) => r.kind === "require_consecutive_ge_80")} extra="minutes" />
            <h2>Consecutive buckets</h2>
            <RateTable rows={dash.persist[sport].filter((r) => r.kind === "consec_bucket")} />
          </>
        )}
        {view === "mae" && (
          <>
            <p className="muted">MAE ≥40¢ is nearly the close-40 stop itself for 80-ish entries. Winner median MAE is the non-tautological fact.</p>
            <RateTable rows={dash.mae[sport]} extra="mae" />
          </>
        )}
        {view === "mfe" && (
          <>
            <div className="row">
              <Card k="P(90 before 40)" v={`${fmt(dash.barriers[sport].p90_before_40.pct)}%`} />
              <Card k="P(95 before 40)" v={`${fmt(dash.barriers[sport].p95_before_40.pct)}%`} />
              <Card k="P(99 before 40)" v={`${fmt(dash.barriers[sport].p99_before_40.pct)}%`} />
            </div>
            <p className="muted">Candle close barriers. Not fills. P(90 before 40) exceeds terminal survival because some paths hit 90 then 40.</p>
          </>
        )}
        {view === "anatomy" && (
          <>
            <h2>Winner classes (MAE partitions of survivors)</h2>
            <RateTable rows={dash.winners[sport]} extra="share" />
            <h2>Stops vs survivors at entry vs after</h2>
            <p className="muted">
              Jump medians are the same at T0. MAE and persistence differ after T0. AVAILABLE_AT_ENTRY vs POST_ENTRY is
              mandatory.
            </p>
          </>
        )}
        {view === "study" && <Study paths={dash.event_study[sport]} />}
        {view === "vol" && (
          <>
            <p className="muted">Pre-entry 15-minute range quintiles. Edges frozen on TRAIN.</p>
            <RateTable rows={dash.vol[sport]} extra="quantile" />
          </>
        )}
        {view === "approach" && (
          <>
            <p className="muted">A priori rules, not P&amp;L-fit. STEADY_RISE n is too small — other classes absorbed gradual paths.</p>
            <RateTable rows={dash.approach[sport]} extra="share" />
          </>
        )}
        {view === "price" && (
          <>
            <p className="muted">First FIRST-80 close. Maker fill may be 80–82 rather than exactly 80. Not an execution model.</p>
            <RateTable rows={dash.entry_price[sport]} />
          </>
        )}
        {view === "time" && (
          <>
            <p className="muted">Minutes from FIRST80 until close-40 or settlement. Fast clocks are stop-enriched.</p>
            <RateTable rows={dash.time_res[sport]} />
            <p className="muted">
              {cap.label}. Median ¢/min {fmt(cap.median_cents_per_minute, 4)} · winners {fmt(cap.winners_median, 4)} · stops{" "}
              {fmt(cap.stops_median, 4)}
            </p>
          </>
        )}
        {view === "season" && (
          <>
            <p className="muted">Existing EARLY/MIDDLE/LATE on frozen candidates. NCAAB LATE is N_TOO_SMALL.</p>
            <RateTable rows={dash.season[sport]} extra="share" />
          </>
        )}
        {view === "depend" && (
          <>
            <h2>Pre-entry logistic (TRAIN fit)</h2>
            <table>
              <thead>
                <tr>
                  <th>Split</th>
                  <th>N</th>
                  <th>AUC</th>
                  <th>Tree acc</th>
                  <th>Base rate</th>
                  <th>Flag</th>
                </tr>
              </thead>
              <tbody>
                {(dash.models[sport].eval ?? []).map((r) => (
                  <tr key={r.split}>
                    <td>{r.split}</td>
                    <td>{r.n}</td>
                    <td>{fmt(r.logistic_auc)}</td>
                    <td>{fmt(r.tree_acc)}</td>
                    <td>{fmt(r.base_rate)}</td>
                    <td>{r.flag ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <h2>Entry clusters (KMeans on TRAIN)</h2>
            <RateTable rows={dash.clusters[sport]} extra="cluster" />
            <h2>Persist × jump (persist is POST-HOC)</h2>
            <RateTable rows={dash.conditional[sport]} />
          </>
        )}
        {view === "compare" && (
          <div className="two">
            <div>
              <h2>NBA persist require</h2>
              <RateTable rows={dash.persist.nba.filter((r) => r.kind === "require_consecutive_ge_80")} />
            </div>
            <div>
              <h2>NCAAB persist require</h2>
              <RateTable rows={dash.persist.ncaab.filter((r) => r.kind === "require_consecutive_ge_80")} />
            </div>
          </div>
        )}
        {view === "unknowns" && (
          <>
            <p className="muted">What historical candles cannot answer. Requires a real order or L2/PBP.</p>
            <ul>
              {dash.unknowns.map((u) => (
                <li key={u}>{u}</li>
              ))}
            </ul>
            <h2>Hedge close-opportunity (not a fill)</h2>
            <RateTable rows={dash.hedge[sport]} />
          </>
        )}
      </div>
    </div>
  );
}
