import { useEffect, useMemo, useState } from "react";
import { NavLink, Route, Routes, useNavigate, useParams } from "react-router-dom";

type Json = Record<string, unknown>;

async function loadJson<T>(path: string): Promise<T> {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${path} ${r.status}`);
  return r.json() as Promise<T>;
}

function fmt(n?: number | null, d = 3) {
  return n == null || Number.isNaN(n) ? "—" : n.toFixed(d);
}
function pct(n?: number | null) {
  return n == null || Number.isNaN(n) ? "—" : `${(n * 100).toFixed(1)}%`;
}

function Card({ k, v, cls }: { k: string; v: string; cls?: string }) {
  return (
    <div className="card">
      <div className="k">{k}</div>
      <div className={`v ${cls ?? ""}`}>{v}</div>
    </div>
  );
}

function useData<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    loadJson<T>(path)
      .then(setData)
      .catch((e: Error) => setErr(e.message));
  }, [path]);
  return { data, err };
}

const NAV = [
  ["/", "Overview"],
  ["/dataset", "Dataset"],
  ["/baseline", "Baseline"],
  ["/features", "Feature store"],
  ["/game", "Game explorer"],
  ["/possession", "Possession explorer"],
  ["/market", "Market explorer"],
  ["/coupling", "Coupling"],
  ["/correlation", "Correlation"],
  ["/pca", "PCA"],
  ["/umap", "UMAP"],
  ["/clusters", "Clusters"],
  ["/models", "Models"],
  ["/ablation", "Ablation"],
  ["/buckets", "Trade buckets"],
  ["/survive", "Survive thresholds"],
  ["/chrono", "Chronological + OOS"],
  ["/walkforward", "Walk-forward"],
  ["/economics", "Economics"],
  ["/portfolio", "Portfolio"],
  ["/registry", "Experiment registry"],
  ["/trade", "Trade explorer"],
];

export default function App() {
  return (
    <div className="app">
      <nav className="nav">
        <div className="brand">
          NBA RE V2
          <small>Test 2 · possession-normalized</small>
        </div>
        {NAV.map(([to, label]) => (
          <NavLink key={to} to={to} end={to === "/"}>
            {label}
          </NavLink>
        ))}
      </nav>
      <main className="main">
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/dataset" element={<Dataset />} />
          <Route path="/baseline" element={<Baseline />} />
          <Route path="/features" element={<Features />} />
          <Route path="/game" element={<FamilyExplorer family="game_state" title="Game state" />} />
          <Route path="/possession" element={<FamilyExplorer family="possession_path" title="Possession path" />} />
          <Route path="/market" element={<FamilyExplorer family="market" title="Market" />} />
          <Route path="/coupling" element={<FamilyExplorer family="coupling" title="Coupling" />} />
          <Route path="/correlation" element={<Correlation />} />
          <Route path="/pca" element={<Pca />} />
          <Route path="/umap" element={<UmapPage />} />
          <Route path="/clusters" element={<Clusters />} />
          <Route path="/models" element={<Models />} />
          <Route path="/ablation" element={<Ablation />} />
          <Route path="/buckets" element={<Buckets />} />
          <Route path="/survive" element={<Survive />} />
          <Route path="/chrono" element={<Chrono />} />
          <Route path="/walkforward" element={<WalkForward />} />
          <Route path="/economics" element={<Economics />} />
          <Route path="/portfolio" element={<Portfolio />} />
          <Route path="/registry" element={<Registry />} />
          <Route path="/trade" element={<TradeList />} />
          <Route path="/trade/:id" element={<TradeDetail />} />
        </Routes>
      </main>
    </div>
  );
}

function Overview() {
  const { data, err } = useData<Json>("/data/summary.json");
  if (err) return <Missing err={err} />;
  if (!data) return <p className="muted">Loading…</p>;
  return (
    <>
      <h1>Overview</h1>
      <p className="notice">
        Research only. Spec verdict B / NO FILTER. Does not overwrite Path Engine V1 or Game Path Engine V2. Does not
        change live FIRST01. Frozen 80/40 definition unchanged.
      </p>
      <div className="row">
        <Card k="Spec verdict A–D" v="B" cls="badge B" />
        <Card k="Production" v="NO FILTER" cls="badge NO" />
        <Card k="Unconditional q" v={pct(data.q_unconditional as number)} />
        <Card k="Unconditional EV" v={`${fmt(data.ev_unconditional as number)} R`} />
      </div>
      <p>{String(data.reason ?? "")}</p>
      <h2>Frozen first-80</h2>
      <div className="row">
        <Card k="First-80" v={String((data.frozen as Json)?.first80 ?? "—")} />
        <Card k="Survive 40" v={String((data.frozen as Json)?.survivors ?? "—")} />
        <Card k="Close-path 40" v={String((data.frozen as Json)?.Y_40_CLOSE ?? "—")} />
      </div>
    </>
  );
}

function Dataset() {
  const { data, err } = useData<Json>("/data/observations_summary.json");
  const poss = useData<Json>("/data/possession_validation.json");
  const ov = useData<Json>("/data/overlay_summary.json");
  if (err) return <Missing err={err} />;
  return (
    <>
      <h1>Dataset</h1>
      <pre className="mono tiny">{JSON.stringify({ observations: data, possessions: poss.data, overlay: ov.data }, null, 2)}</pre>
    </>
  );
}

function Baseline() {
  const { data, err } = useData<Json>("/data/phase1_gate.json");
  const leak = useData<Json>("/data/leakage_audit.json");
  if (err) return <Missing err={err} />;
  return (
    <>
      <h1>Baseline / Phase 1</h1>
      <p>Primary analysis set = GPE V2 HIGH ∪ MEDIUM. Full 1,230 ledger is always written.</p>
      <pre className="mono tiny">{JSON.stringify({ phase1: data, leakage: leak.data }, null, 2)}</pre>
    </>
  );
}

function Features() {
  const { data, err } = useData<{ rows: { feature_name: string; feature_family: string; observed_or_derived: string }[] }>(
    "/data/feature_metadata.json",
  );
  const sum = useData<Json>("/data/features_summary.json");
  if (err) return <Missing err={err} />;
  return (
    <>
      <h1>Feature store</h1>
      <p className="tiny">Causal only. source_ts ≤ ENTRY_DECISION_TIME. No L2.</p>
      <pre className="mono tiny">{JSON.stringify(sum.data, null, 2)}</pre>
      <table>
        <thead>
          <tr>
            <th>Feature</th>
            <th>Family</th>
            <th>Observed / derived</th>
          </tr>
        </thead>
        <tbody>
          {(data?.rows ?? []).slice(0, 200).map((r) => (
            <tr key={r.feature_name}>
              <td className="mono">{r.feature_name}</td>
              <td>{r.feature_family}</td>
              <td>{r.observed_or_derived}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function FamilyExplorer({ family, title }: { family: string; title: string }) {
  const { data, err } = useData<{ rows: { feature_name: string; feature_family: string }[] }>("/data/feature_metadata.json");
  if (err) return <Missing err={err} />;
  const rows = (data?.rows ?? []).filter((r) => r.feature_family.includes(family) || r.feature_name.includes(family === "market" ? "mkt_" : family));
  return (
    <>
      <h1>{title}</h1>
      <p className="tiny">{rows.length} columns. Windows 1/3/5/10/20/30 possessions are all computed; none assumed optimal.</p>
      <ul>
        {rows.map((r) => (
          <li key={r.feature_name} className="mono">
            {r.feature_name}
          </li>
        ))}
      </ul>
    </>
  );
}

function Correlation() {
  const { data, err } = useData<{ high_corr_pairs: { a: string; b: string; r: number }[]; missingness: Record<string, number>; n_train: number }>(
    "/data/diagnostics.json",
  );
  if (err) return <Missing err={err} />;
  return (
    <>
      <h1>Correlation / missingness</h1>
      <p>TRAIN only. |r| ≥ 0.9 pairs shown. DISCOVERED AFTER MULTIPLE SEARCHES.</p>
      <p className="tiny">n_train={data?.n_train}</p>
      <table>
        <thead>
          <tr>
            <th>A</th>
            <th>B</th>
            <th>r</th>
          </tr>
        </thead>
        <tbody>
          {(data?.high_corr_pairs ?? []).map((p) => (
            <tr key={`${p.a}|${p.b}`}>
              <td className="mono">{p.a}</td>
              <td className="mono">{p.b}</td>
              <td>{fmt(p.r)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function Pca() {
  const { data, err } = useData<{ points: { pc1: number; pc2: number; Y_40_CLOSE: number; split: string }[]; note: string }>(
    "/data/pca_points.json",
  );
  if (err) return <Missing err={err} />;
  const pts = data?.points ?? [];
  return (
    <>
      <h1>PCA</h1>
      <p className="notice">{data?.note ?? "Visualization only. Not evidence. UMAP is not used as proof."}</p>
      <Scatter pts={pts} />
    </>
  );
}

function UmapPage() {
  const { data, err } = useData<{ points: { x: number; y: number; Y_40_CLOSE: number; split: string }[]; note: string }>(
    "/data/umap_points.json",
  );
  if (err) return <Missing err={err} />;
  const pts = (data?.points ?? []).map((p) => ({ pc1: p.x, pc2: p.y, Y_40_CLOSE: p.Y_40_CLOSE, split: p.split }));
  return (
    <>
      <h1>UMAP</h1>
      <p className="notice">{data?.note ?? "Exploratory visualization only. Not proof of tradable clusters."}</p>
      <Scatter pts={pts} />
    </>
  );
}

function Scatter({ pts }: { pts: { pc1: number; pc2: number; Y_40_CLOSE: number; split: string }[] }) {
  if (!pts.length) return <p className="muted">No PCA points.</p>;
  const xs = pts.map((p) => p.pc1);
  const ys = pts.map((p) => p.pc2);
  const minx = Math.min(...xs);
  const maxx = Math.max(...xs);
  const miny = Math.min(...ys);
  const maxy = Math.max(...ys);
  const sx = (v: number) => ((v - minx) / (maxx - minx || 1)) * 700 + 10;
  const sy = (v: number) => 210 - ((v - miny) / (maxy - miny || 1)) * 190;
  return (
    <svg className="eq" viewBox="0 0 720 220">
      {pts.map((p, i) => (
        <circle
          key={i}
          cx={sx(p.pc1)}
          cy={sy(p.pc2)}
          r={p.split === "OOS" ? 2.4 : 1.8}
          fill={p.Y_40_CLOSE ? "#e05d5d" : "#3dba7a"}
          opacity={p.split === "TRAIN" ? 0.55 : 0.9}
        />
      ))}
    </svg>
  );
}

function Clusters() {
  const { data, err } = useData<Json>("/data/clusters.json");
  if (err) return <Missing err={err} />;
  const rows = ((data?.results as Json[]) ?? []).filter((r) => r.algo === "kmeans");
  return (
    <>
      <h1>Clusters</h1>
      <p>K-Means / GMM / hierarchical. Silhouette is not a trading result. UMAP is not proof.</p>
      <p className="tiny">
        best k={String(data?.best_k_by_train_q_range)} bootstrap ARI={fmt(data?.bootstrap_ari_mean as number)}
      </p>
      <table>
        <thead>
          <tr>
            <th>k</th>
            <th>silhouette</th>
            <th>TRAIN q range</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={String(r.k)}>
              <td>{String(r.k)}</td>
              <td>{fmt(r.silhouette as number)}</td>
              <td>{fmt(r.train_q_range as number)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h2>OOS persistence</h2>
      <pre className="mono tiny">{JSON.stringify(data?.oos_persistence, null, 2)}</pre>
    </>
  );
}

function Models() {
  const { data, err } = useData<{ results: Json[] }>("/data/models.json");
  if (err) return <Missing err={err} />;
  return (
    <>
      <h1>Models</h1>
      <p>Model 0 = q̂ 26.02%. TRAIN=BUILD, VAL=CHOOSE, OOS=VERIFY. No Platt on VALIDATION.</p>
      <table>
        <thead>
          <tr>
            <th>Model</th>
            <th>Features</th>
            <th>VAL Brier</th>
            <th>VAL AUC</th>
            <th>OOS Brier</th>
            <th>OOS AUC</th>
          </tr>
        </thead>
        <tbody>
          {(data?.results ?? []).map((r) => (
            <tr key={`${r.model}|${r.feature_set}`}>
              <td>{String(r.model)}</td>
              <td>{String(r.feature_set)}</td>
              <td>{fmt((r.validation as Json)?.brier as number)}</td>
              <td>{fmt((r.validation as Json)?.auc as number)}</td>
              <td>{fmt((r.oos as Json)?.brier as number)}</td>
              <td>{fmt((r.oos as Json)?.auc as number)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function Ablation() {
  const { data, err } = useData<{ results: Json[] }>("/data/models.json");
  if (err) return <Missing err={err} />;
  const rows = (data?.results ?? []).filter((r) => r.model === "l2_logistic");
  return (
    <>
      <h1>Family ablation</h1>
      <p>Mandatory: game state / path / market state / path / coupling / game+market / full.</p>
      <table>
        <thead>
          <tr>
            <th>Family</th>
            <th>VAL Brier</th>
            <th>OOS Brier</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={String(r.feature_set)}>
              <td>{String(r.feature_set)}</td>
              <td>{fmt((r.validation as Json)?.brier as number)}</td>
              <td>{fmt((r.oos as Json)?.brier as number)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function Buckets() {
  const { data, err } = useData<{ results: Json[] }>("/data/models.json");
  if (err) return <Missing err={err} />;
  const filters: Json[] = (data?.results ?? []).flatMap((r) =>
    ((r.filters_val as Json[]) ?? []).map((f) => ({ ...f, model: r.model, feature_set: r.feature_set })),
  );
  return (
    <>
      <h1>Trade buckets / filters</h1>
      <p>Acceptance ≥ 50% required for a production candidate. Thresholds chosen on VAL only.</p>
      <table>
        <thead>
          <tr>
            <th>Model</th>
            <th>Family</th>
            <th>t</th>
            <th>accept</th>
            <th>q</th>
            <th>EV</th>
            <th>beats</th>
          </tr>
        </thead>
        <tbody>
          {filters.slice(0, 80).map((f, i) => (
            <tr key={i}>
              <td>{String(f.model)}</td>
              <td>{String(f.feature_set)}</td>
              <td>{fmt(f.threshold as number)}</td>
              <td>{pct(f.acceptance_rate as number)}</td>
              <td>{pct(f.actual_q as number)}</td>
              <td className={(f.ev as number) > 0.219 ? "pos" : ""}>{fmt(f.ev as number)}</td>
              <td>{String(f.beats)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function Survive() {
  const { data, err } = useData<{ rows: Json[] }>("/data/survive_thresholds.json");
  if (err) return <Missing err={err} />;
  return (
    <>
      <h1>Survive-probability thresholds</h1>
      <p>P_survive = 1 − q̂. VAL inspects; OOS is frozen. Not a production filter.</p>
      <table>
        <thead>
          <tr>
            <th>t</th>
            <th>VAL n</th>
            <th>VAL acc</th>
            <th>VAL survive</th>
            <th>OOS n</th>
            <th>OOS acc</th>
            <th>OOS survive</th>
          </tr>
        </thead>
        <tbody>
          {(data?.rows ?? []).map((r, i) => {
            const v = r.val as Json;
            const o = r.oos as Json;
            return (
              <tr key={i}>
                <td>{fmt(v.p_survive_min as number, 2)}</td>
                <td>{String(v.n)}</td>
                <td>{pct(v.acceptance as number)}</td>
                <td>{pct(v.survive as number)}</td>
                <td>{String(o.n)}</td>
                <td>{pct(o.acceptance as number)}</td>
                <td>{pct(o.survive as number)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </>
  );
}

function WalkForward() {
  const { data, err } = useData<{ folds: Json[]; note: string }>("/data/walk_forward.json");
  if (err) return <Missing err={err} />;
  return (
    <>
      <h1>Walk-forward</h1>
      <p>{data?.note ?? "TRAIN+VAL only. Final OOS untouched."}</p>
      <table>
        <thead>
          <tr>
            <th>Validate month</th>
            <th>n train</th>
            <th>n val</th>
            <th>Brier</th>
            <th>Model 0 Brier</th>
            <th>AUC</th>
          </tr>
        </thead>
        <tbody>
          {(data?.folds ?? []).map((f) => (
            <tr key={String(f.validate_month)}>
              <td>{String(f.validate_month)}</td>
              <td>{String(f.n_train)}</td>
              <td>{String(f.n_val)}</td>
              <td>{fmt(f.brier as number)}</td>
              <td>{fmt(f.model0_brier as number)}</td>
              <td>{fmt(f.auc as number)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function Chrono() {
  const ch = useData<Json>("/data/chronological.json");
  const sel = useData<Json>("/data/selection.json");
  if (ch.err) return <Missing err={ch.err} />;
  return (
    <>
      <h1>Chronological + OOS</h1>
      <p>No random K-fold across dates. OOS is VERIFY once.</p>
      <pre className="mono tiny">{JSON.stringify({ chronological: ch.data, selection: sel.data }, null, 2)}</pre>
    </>
  );
}

function Economics() {
  const { data, err } = useData<Json>("/data/economics.json");
  if (err) return <Missing err={err} />;
  const rows = (data?.rows as Json[]) ?? [];
  return (
    <>
      <h1>Economics</h1>
      <p>
        EV = 1 − 3q. Unconditional EV {fmt(data?.ev_unconditional as number)} R. Research fee estimate:{" "}
        {String(data?.research_fee_estimate)}
      </p>
      <table>
        <thead>
          <tr>
            <th>Model</th>
            <th>Family</th>
            <th>Split</th>
            <th>q</th>
            <th>EV</th>
            <th>Brier</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td>{String(r.model)}</td>
              <td>{String(r.feature_set)}</td>
              <td>{String(r.split)}</td>
              <td>{pct(r.q as number)}</td>
              <td>{fmt(r.ev as number)}</td>
              <td>{fmt(r.brier as number)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function Portfolio() {
  const { data, err } = useData<Json>("/data/portfolio.json");
  if (err) return <Missing err={err} />;
  return (
    <>
      <h1>Portfolio</h1>
      <p>Research concurrency. Not live capital. Not optimized on OOS.</p>
      <pre className="mono tiny">{JSON.stringify(data, null, 2)}</pre>
    </>
  );
}

function Registry() {
  const { data, err } = useData<{ rows: Json[] }>("/data/experiment_registry.json");
  if (err) return <Missing err={err} />;
  return (
    <>
      <h1>Experiment registry</h1>
      <p>Append-only. Failed hypotheses stay. DISCOVERED AFTER MULTIPLE SEARCHES is marked.</p>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Class</th>
            <th>VAL Brier</th>
            <th>OOS Brier</th>
          </tr>
        </thead>
        <tbody>
          {(data?.rows ?? []).map((r) => (
            <tr key={String(r.experiment_id)}>
              <td className="mono">{String(r.experiment_id)}</td>
              <td>{String(r.class)}</td>
              <td>{fmt(((r.results as Json)?.validation as Json)?.brier as number)}</td>
              <td>{fmt(((r.results as Json)?.oos as Json)?.brier as number)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

type Trade = {
  observation_id: string;
  ticker?: string;
  game_date?: string;
  dataset_split?: string;
  Y_40_CLOSE?: number;
  alignment_confidence?: string;
  possession_id?: string;
  score_differential?: number;
  mkt_yes_bid_cents?: number;
};

function TradeList() {
  const { data, err } = useData<{ rows: Trade[] }>("/data/trades_index.json");
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [split, setSplit] = useState("ALL");
  const rows = useMemo(() => {
    const qq = q.toUpperCase();
    return (data?.rows ?? []).filter((r) => {
      if (split !== "ALL" && r.dataset_split !== split) return false;
      if (qq && !(r.ticker ?? "").toUpperCase().includes(qq) && !(r.observation_id ?? "").toUpperCase().includes(qq))
        return false;
      return true;
    });
  }, [data, q, split]);
  if (err) return <Missing err={err} />;
  return (
    <>
      <h1>Trade explorer</h1>
      <p className="tiny">Select a first-80. After-entry path is never a live feature.</p>
      <div className="row">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="ticker / id" />
        <select value={split} onChange={(e) => setSplit(e.target.value)}>
          <option>ALL</option>
          <option>TRAIN</option>
          <option>VALIDATION</option>
          <option>OOS</option>
        </select>
        <span className="tiny">{rows.length} shown</span>
      </div>
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Ticker</th>
            <th>Split</th>
            <th>Y40</th>
            <th>Align</th>
            <th>Score Δ</th>
            <th>Bid ¢</th>
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 250).map((r) => (
            <tr key={r.observation_id} onClick={() => nav(`/trade/${encodeURIComponent(r.observation_id)}`)} style={{ cursor: "pointer" }}>
              <td>{r.game_date}</td>
              <td className="mono">{r.ticker}</td>
              <td>{r.dataset_split}</td>
              <td className={r.Y_40_CLOSE ? "neg" : "pos"}>{r.Y_40_CLOSE}</td>
              <td>{r.alignment_confidence}</td>
              <td>{fmt(r.score_differential, 1)}</td>
              <td>{fmt(r.mkt_yes_bid_cents, 1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function TradeDetail() {
  const { id } = useParams();
  const [bundle, setBundle] = useState<Json | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (!id) return;
    fetch(`/api/trade/${encodeURIComponent(id)}`)
      .then((r) => {
        if (!r.ok) throw new Error(`API ${r.status} — start api_server.py on :8788`);
        return r.json();
      })
      .then(setBundle)
      .catch((e: Error) => setErr(e.message));
  }, [id]);
  if (err) return <Missing err={err} />;
  if (!bundle) return <p className="muted">Loading trade…</p>;
  const at = (bundle.at_entry_possessions as Json[]) ?? [];
  const after = (bundle.after_entry_possessions as Json[]) ?? [];
  return (
    <>
      <h1>Trade {id}</h1>
      <p className="notice">{String(bundle.visual_split)}</p>
      <div className="split">
        <div className="pane">
          <h2>At entry (features)</h2>
          <PossTable rows={at} />
        </div>
        <div className="pane after">
          <h2>After entry — not a live feature</h2>
          <PossTable rows={after} />
        </div>
      </div>
      <h2>Features at ENTRY_DECISION_TIME</h2>
      <pre className="mono tiny">{JSON.stringify(bundle.features, null, 2)}</pre>
    </>
  );
}

function PossTable({ rows }: { rows: Json[] }) {
  return (
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Q</th>
          <th>Team</th>
          <th>Result</th>
          <th>Pts</th>
          <th>Score</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((p) => (
          <tr key={String(p.possession_id)}>
            <td>{String(p.possession_sequence)}</td>
            <td>{String(p.period)}</td>
            <td>{String(p.possession_team)}</td>
            <td>{String(p.possession_result)}</td>
            <td>{String(p.points_scored)}</td>
            <td>
              {String(p.home_score_end)}–{String(p.away_score_end)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Missing({ err }: { err: string }) {
  return (
    <>
      <h1>Artifact missing</h1>
      <p className="err">{err}</p>
      <p className="muted">Run `research_engine_v2_test2/run_pipeline.py` then refresh. Trade explorer also needs `api_server.py` on port 8788.</p>
    </>
  );
}
