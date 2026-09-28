import { useEffect, useMemo, useState } from "react";
import { NavLink, Route, Routes, useNavigate, useParams } from "react-router-dom";
import {
  api,
  type Candidate,
  type Dataset,
  type Experiment,
  type Hypothesis,
  type Job,
  type Model,
  type ParamDoc,
  type ParameterInput,
  type Promotion,
  type Strategy,
} from "./api";

function fmt(n?: number | null, d = 2) {
  return n == null || Number.isNaN(n) ? "—" : n.toFixed(d);
}
function evClass(n?: number | null) {
  if (n == null) return "";
  return n > 0 ? "pos" : n < 0 ? "neg" : "";
}

function linePath(ys: number[], w = 720, h = 180) {
  const min = Math.min(0, ...ys);
  const max = Math.max(0, ...ys);
  const span = max - min || 1;
  return ys
    .map((v, i) => {
      const x = (i / (ys.length - 1 || 1)) * (w - 16) + 8;
      const y = h - 12 - ((v - min) / span) * (h - 24);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

function Equity({ points }: { points?: { date: string; cumulative_usd: number }[] }) {
  if (!points?.length) return <p className="muted">No equity series on this record.</p>;
  return (
    <svg className="eq" viewBox="0 0 720 180" preserveAspectRatio="none">
      <path d={linePath(points.map((p) => p.cumulative_usd))} fill="none" stroke="#c8a25a" strokeWidth="1.5" />
    </svg>
  );
}

function Drawdown({ points }: { points?: { date: string; cumulative_usd: number }[] }) {
  if (!points?.length) return <p className="muted">No drawdown series.</p>;
  let peak = 0;
  const dd = points.map((p) => {
    peak = Math.max(peak, p.cumulative_usd);
    return p.cumulative_usd - peak;
  });
  return (
    <svg className="eq" viewBox="0 0 720 180" preserveAspectRatio="none">
      <path d={linePath(dd)} fill="none" stroke="#e05d5d" strokeWidth="1.5" />
    </svg>
  );
}

function PnlHist({ points }: { points?: { pnl_usd?: number; date?: string }[] }) {
  if (!points?.length) return <p className="muted">No P&amp;L distribution.</p>;
  const xs = points.map((p) => p.pnl_usd ?? 0);
  const lo = Math.min(...xs);
  const hi = Math.max(...xs);
  const bins = 16;
  const width = hi - lo || 1;
  const counts = Array(bins).fill(0);
  for (const x of xs) {
    const i = Math.min(bins - 1, Math.floor(((x - lo) / width) * bins));
    counts[i] += 1;
  }
  const m = Math.max(...counts, 1);
  const barW = 720 / bins;
  return (
    <svg className="eq" viewBox="0 0 720 180">
      {counts.map((c, i) => {
        const h = (c / m) * 150;
        return <rect key={i} x={i * barW + 2} y={170 - h} width={barW - 4} height={h} fill="#c8a25a" />;
      })}
    </svg>
  );
}

function SplitBars({ summary }: { summary?: Record<string, unknown> | null }) {
  const u = summary?.unconditional as Record<string, { ev_cents?: number }> | undefined;
  if (!u) return null;
  const keys = ["train", "validation", "test"] as const;
  const evs = keys.map((k) => u[k]?.ev_cents ?? 0);
  const mag = Math.max(...evs.map((x) => Math.abs(x)), 1);
  return (
    <svg className="eq" viewBox="0 0 720 180">
      {evs.map((v, i) => {
        const h = (Math.abs(v) / mag) * 70;
        const x = 80 + i * 200;
        const y = v >= 0 ? 90 - h : 90;
        return (
          <g key={keys[i]}>
            <rect x={x} y={y} width={80} height={h} fill={v >= 0 ? "#3dba7a" : "#e05d5d"} />
            <text x={x + 40} y={170} textAnchor="middle" fill="#8b98a5" fontSize="12">{keys[i].toUpperCase()}</text>
          </g>
        );
      })}
    </svg>
  );
}

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="app">
      <nav className="nav">
        <div className="brand">
          MOMENTO RESEARCH
          <small>internal console · not production</small>
        </div>
        <NavLink to="/" end>Dashboard</NavLink>
        <NavLink to="/experiments">Experiments</NavLink>
        <NavLink to="/new">New Backtest</NavLink>
        <NavLink to="/results">Results</NavLink>
        <NavLink to="/jobs">Runs / Jobs</NavLink>
        <NavLink to="/candidates">Candidates</NavLink>
        <NavLink to="/prospective">Prospective 83</NavLink>
        <NavLink to="/datasets">Datasets</NavLink>
        <NavLink to="/strategies">Strategies</NavLink>
        <NavLink to="/models">Models</NavLink>
        <NavLink to="/quality">Data Quality</NavLink>
        <NavLink to="/compare">Compare</NavLink>
        <NavLink to="/system">System</NavLink>
      </nav>
      <main className="main">{children}</main>
    </div>
  );
}

function Dashboard() {
  const [exps, setExps] = useState<Experiment[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [cands, setCands] = useState<Candidate[]>([]);
  const [sets, setSets] = useState<Dataset[]>([]);
  const [err, setErr] = useState("");
  useEffect(() => {
    Promise.all([api.experiments(), api.jobs(), api.candidates(), api.datasets()])
      .then(([e, j, c, d]) => {
        setExps(e);
        setJobs(j);
        setCands(c);
        setSets(d);
      })
      .catch((e: Error) => setErr(e.message));
  }, []);
  const active = jobs.filter((j) => j.status === "RUNNING" || j.status === "QUEUED").length;
  const ds = sets[0];
  return (
    <>
      <h1>Research desk</h1>
      <div className="notice">
        B1 is a research family. CANDIDATE ≠ approved. PRODUCTION = 0. TRADE print ≠ fill. L2 unavailable.
      </div>
      {err && <p className="err">{err}</p>}
      <div className="row">
        <div className="card"><div className="k">Active jobs</div><div className="v">{active}</div></div>
        <div className="card"><div className="k">Candidates</div><div className="v">{cands.length}</div></div>
        <div className="card"><div className="k">Robust labels</div><div className="v">{cands.filter((c) => c.status === "ROBUST" || c.status === "ROBUST_CANDIDATE").length}</div></div>
        <div className="card"><div className="k">Paper</div><div className="v">{exps.filter((e) => e.status === "PAPER").length}</div></div>
        <div className="card"><div className="k">Production</div><div className="v">0</div></div>
        <div className="card"><div className="k">B1 games</div><div className="v">{ds?.game_count ?? "—"}</div></div>
      </div>
      {ds && (
        <p className="muted">
          Dataset {ds.id}/{ds.version} · L2 {String(ds.quality.l2_status ?? "UNAVAILABLE_SOURCE")} ·
          settlement {String(ds.quality.settlement_label_coverage_pct ?? "—")}%
        </p>
      )}
      <h2>Recent experiments</h2>
      <ExpTable rows={exps.slice(0, 12)} />
    </>
  );
}

function ExpTable({ rows }: { rows: Experiment[] }) {
  return (
    <table>
      <thead>
        <tr>
          <th>Name</th><th>Status</th><th>Dataset</th><th>Hyps</th><th>Updated</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((e) => (
          <tr key={e.id}>
            <td><NavLink to={`/experiments/${e.id}`}>{e.definition.name}</NavLink><div className="muted mono">{e.id}</div></td>
            <td><span className={`badge ${e.status}`}>{e.status}</span></td>
            <td>{e.definition.dataset_id}/{e.definition.dataset_version}</td>
            <td className="mono">{e.hypothesis_count}</td>
            <td className="muted">{e.updated_at.slice(0, 19)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Experiments() {
  const [rows, setRows] = useState<Experiment[]>([]);
  useEffect(() => { api.experiments().then(setRows).catch(() => undefined); }, []);
  return (<><h1>Experiments</h1><ExpTable rows={rows} /></>);
}

const FEATURE_ALIAS: Record<string, string> = {
  vol_1m: "vol_1m_tertile",
  vol_15m: "vol_15m_tertile",
  vol_5m: "vol_5m_tertile",
};

function canonicalFeature(name: string) {
  return FEATURE_ALIAS[name] ?? name;
}

function parseParams(text: string): ParameterInput[] {
  return text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean)
    .map((l) => {
      if (l.includes(":range:")) {
        const [name, , min, max, step] = l.split(":");
        return {
          name: canonicalFeature((name || "").trim()),
          values: [],
          kind: "range",
          min: Number(min),
          max: Number(max),
          step: Number(step || 1),
        };
      }
      const [name, rest] = l.split("=");
      return {
        name: canonicalFeature((name || "").trim()),
        values: (rest || "").split(",").map((s) => s.trim()).filter(Boolean),
        kind: "list",
      };
    })
    .filter((p) => p.name && (p.kind === "range" || p.values.length));
}

function NewBacktest() {
  const nav = useNavigate();
  const [name, setName] = useState("B1 custom grid");
  const [desc, setDesc] = useState("");
  const [dataset, setDataset] = useState("B1_FIRST83/v1");
  const [strategy, setStrategy] = useState("B1");
  const [train, setTrain] = useState("2025-10-07");
  const [val, setVal] = useState("2026-05-03");
  const [testEnd, setTestEnd] = useState("2026-06-27");
  const [params, setParams] = useState("start_price_band=40_49\ninning_grp=7,8\np_max_vs_83=PEAK_AT");
  const [fees, setFees] = useState(0);
  const [slip, setSlip] = useState(0);
  const [qty, setQty] = useState(7);
  const [search, setSearch] = useState("grid");
  const [alpha, setAlpha] = useState(0.1);
  const [minTrain, setMinTrain] = useState(50);
  const [minVal, setMinVal] = useState(10);
  const [minTest, setMinTest] = useState(15);
  const [feats, setFeats] = useState<Record<string, string[]>>({});
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [catalog, setCatalog] = useState<ParamDoc[]>([]);
  const [est, setEst] = useState<number | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const parsed = useMemo(() => parseParams(params), [params]);
  const leak = train >= val;
  useEffect(() => {
    api.features().then((f) => { if (f.values) setFeats(f.values); }).catch(() => undefined);
    api.datasets().then(setDatasets).catch(() => undefined);
    api.strategies().then(setStrategies).catch(() => undefined);
    api.parameterCatalog().then(setCatalog).catch(() => undefined);
  }, []);
  useEffect(() => {
    api.estimate(parsed).then((r) => setEst(r.hypotheses)).catch(() => setEst(null));
  }, [parsed]);
  async function submit(runNow: boolean) {
    setErr("");
    if (leak) {
      setErr("Invalid split: TRAIN cut must be strictly before VAL. TEST stays locked after VAL.");
      return;
    }
    setBusy(true);
    try {
      const [dataset_id, dataset_version] = dataset.split("/");
      const st = strategies.find((s) => s.id === strategy);
      const exp = await api.createExperiment({
        name,
        description: desc,
        tags: ["console"],
        dataset_id,
        dataset_version,
        strategy_id: strategy,
        strategy_version: st?.version ?? "B1.ENGINE.1.1.0",
        feature_set: "B1.FEATURE.1.1.0",
        parameters: parsed,
        train_before: train,
        val_before: val,
        test_end: testEnd,
        execution_model: "TRADE_PRINT_MODELED",
        fees_cents: fees,
        slippage_cents: slip,
        position_qty: qty,
        capital_cents: 5000,
        search_method: search,
        fdr_method: "benjamini_hochberg",
        fdr_alpha: alpha,
        min_train: minTrain,
        min_val: minVal,
        min_test: minTest,
        random_seed: 42,
        created_by: "console",
      });
      if (runNow) {
        const job = await api.runExperiment(exp.id);
        nav(`/jobs/${job.id}`);
      } else {
        nav(`/experiments/${exp.id}`);
      }
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <h1>New backtest</h1>
      <div className="notice">
        TEST is locked after you run. Selection uses TRAIN (and VAL). A new grid’s FDR is that grid’s search space, not the imported 6,128-test q.
        Range syntax: <span className="mono">inning_exact:range:6:9:1</span>
        · aliases: vol_1m → vol_1m_tertile. Fees/slippage are recorded assumptions; B1 HOLD_TO_SETTLEMENT does not invent a fee schedule.
      </div>
      {leak && <p className="err">TRAIN ≥ VAL would leak. Fix the cuts before running.</p>}
      <div className="form-grid">
        <div><label>Name</label><input value={name} onChange={(e) => setName(e.target.value)} /></div>
        <div>
          <label>Dataset</label>
          <select value={dataset} onChange={(e) => setDataset(e.target.value)}>
            {datasets.map((d) => (
              <option key={`${d.id}/${d.version}`} value={`${d.id}/${d.version}`}>{d.id} / {d.version} ({d.game_count ?? "?"} games)</option>
            ))}
          </select>
        </div>
        <div className="span2"><label>Description</label><textarea value={desc} onChange={(e) => setDesc(e.target.value)} /></div>
        <div>
          <label>Strategy</label>
          <select value={strategy} onChange={(e) => setStrategy(e.target.value)}>
            {strategies.map((s) => (
              <option key={s.id} value={s.id}>{s.id} · {s.version} · prod {s.production_status}</option>
            ))}
          </select>
        </div>
        <div>
          <label>Execution / search</label>
          <select value={search} onChange={(e) => setSearch(e.target.value)}>
            <option value="grid">grid · TRADE_PRINT_MODELED</option>
            <option value="single">single · TRADE_PRINT_MODELED</option>
          </select>
        </div>
        <div><label>TRAIN before</label><input value={train} onChange={(e) => setTrain(e.target.value)} /></div>
        <div><label>VAL before</label><input value={val} onChange={(e) => setVal(e.target.value)} /></div>
        <div><label>TEST through (label)</label><input value={testEnd} onChange={(e) => setTestEnd(e.target.value)} /></div>
        <div><label>Fees ¢ / Slippage ¢ / qty</label>
          <div className="row">
            <input type="number" value={fees} onChange={(e) => setFees(Number(e.target.value))} />
            <input type="number" value={slip} onChange={(e) => setSlip(Number(e.target.value))} />
            <input type="number" value={qty} onChange={(e) => setQty(Number(e.target.value))} />
          </div>
        </div>
        <div><label>FDR α / min TRAIN VAL TEST</label>
          <div className="row">
            <input type="number" step="0.01" value={alpha} onChange={(e) => setAlpha(Number(e.target.value))} />
            <input type="number" value={minTrain} onChange={(e) => setMinTrain(Number(e.target.value))} />
            <input type="number" value={minVal} onChange={(e) => setMinVal(Number(e.target.value))} />
            <input type="number" value={minTest} onChange={(e) => setMinTest(Number(e.target.value))} />
          </div>
        </div>
        <div className="span2">
          <label>Parameter grid — list: name=v1,v2 · range: name:range:min:max:step. Cartesian product.</label>
          <textarea value={params} onChange={(e) => setParams(e.target.value)} />
        </div>
      </div>
      <p>Hypotheses (grid): <b className="mono">{est ?? "—"}</b> plus unconditional ALL_83 baseline.</p>
      {err && <p className="err">{err}</p>}
      <div className="row">
        <button type="button" disabled={busy || leak} onClick={() => submit(true)}>Run backtest</button>
        <button type="button" className="secondary" disabled={busy || leak} onClick={() => submit(false)}>Save draft</button>
      </div>
      <h2>Parameter catalog</h2>
      <table>
        <thead><tr><th>Name</th><th>Group</th><th>Kind</th><th>Notes</th></tr></thead>
        <tbody>
          {catalog.map((p) => (
            <tr key={p.name}><td className="mono">{p.name}</td><td>{p.group}</td><td>{p.kind}</td><td className="muted">{p.notes}</td></tr>
          ))}
        </tbody>
      </table>
      <h2>TRAIN-observed feature values</h2>
      <p className="muted">Use only keys shown. Settlement / future / L2 keys are rejected.</p>
      <table>
        <thead><tr><th>Feature</th><th>Values</th></tr></thead>
        <tbody>
          {Object.entries(feats).slice(0, 40).map(([k, vs]) => (
            <tr key={k}><td className="mono">{k}</td><td className="muted">{vs.join(", ")}</td></tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function ExperimentDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const [exp, setExp] = useState<Experiment | null>(null);
  const [hyps, setHyps] = useState<Hypothesis[]>([]);
  const [err, setErr] = useState("");
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("ALL");
  const [promos, setPromos] = useState<Promotion[]>([]);
  useEffect(() => {
    if (!id) return;
    api.experiment(id).then(setExp).catch((e: Error) => setErr(e.message));
    api.hypotheses(id).then(setHyps).catch(() => undefined);
    api.promotions(id).then(setPromos).catch(() => undefined);
  }, [id]);
  if (!exp) return <p>{err || "Loading…"}</p>;
  const uncond = exp.result_summary?.unconditional as Record<string, unknown> | undefined;
  const equity = (uncond as { equity?: { date: string; cumulative_usd: number; pnl_usd?: number }[] } | undefined)?.equity
    ?? hyps[0]?.equity;
  const filtered = hyps.filter((h) => {
    const okQ = !q || h.condition.toLowerCase().includes(q.toLowerCase());
    const cls = h.classification ?? "";
    const okS = status === "ALL" || cls === status;
    return okQ && okS;
  });
  async function run() {
    const job = await api.runExperiment(exp.id);
    nav(`/jobs/${job.id}`);
  }
  async function repro() {
    const copy = await api.reproduce(exp.id);
    nav(`/experiments/${copy.id}`);
  }
  async function promo(to: string) {
    try {
      await api.promote(exp.id, to, "console");
      setExp(await api.experiment(exp.id));
    } catch (e) {
      setErr((e as Error).message);
    }
  }
  return (
    <>
      <h1>{exp.definition.name}</h1>
      <p className="muted mono">{exp.id} · parent {exp.definition.parent_experiment_id ?? "none"}</p>
      <span className={`badge ${exp.status}`}>{exp.status}</span>
      <div className="row" style={{ marginTop: 12 }}>
        <button type="button" onClick={run}>Run</button>
        <button type="button" className="secondary" onClick={repro}>Reproduce (new experiment)</button>
        <button type="button" className="secondary" onClick={() => promo("HYPOTHESIS")}>Mark hypothesis</button>
        <button type="button" className="secondary" onClick={() => promo("CANDIDATE")}>Mark candidate</button>
        <button type="button" className="secondary" onClick={() => promo("REJECTED")}>Reject</button>
      </div>
      <p className="muted">Promotion is explicit. CANDIDATE cannot jump to PRODUCTION.</p>
      <h2>Lineage</h2>
      <table>
        <tbody>
          <tr><th>Dataset</th><td>{exp.definition.dataset_id}/{exp.definition.dataset_version}</td></tr>
          <tr><th>Strategy / model</th><td>{exp.definition.strategy_id} {exp.definition.strategy_version} · {exp.definition.feature_set}</td></tr>
          <tr><th>Search</th><td>{exp.definition.search_method} · FDR {exp.definition.fdr_method} α={exp.definition.fdr_alpha}</td></tr>
          <tr><th>Split</th><td>TRAIN &lt; {exp.definition.train_before} · VAL &lt; {exp.definition.val_before} · TEST through {exp.definition.test_end ?? "observed"}</td></tr>
          <tr><th>Execution</th><td>{exp.definition.execution_model} · fees {exp.definition.fees_cents}¢ · slip {exp.definition.slippage_cents}¢ · qty {exp.definition.position_qty ?? 7} · seed {exp.definition.random_seed}</td></tr>
          <tr><th>Tests (this experiment)</th><td className="mono">{String(exp.result_summary?.number_of_tests ?? "—")}</td></tr>
          <tr><th>Min n</th><td>TRAIN {exp.definition.min_train} · VAL {exp.definition.min_val} · TEST {exp.definition.min_test}</td></tr>
          <tr><th>Artifacts</th><td className="mono">{exp.artifact_dir ?? "—"}</td></tr>
        </tbody>
      </table>
      {!!exp.result_summary?.benchmark_40_49 && (
        <>
          <h2>Locked 40–49 benchmark (imported q from 6,128 tests)</h2>
          <BenchCard row={exp.result_summary.benchmark_40_49 as Record<string, unknown>} />
        </>
      )}
      {!!exp.result_summary?.primary && typeof exp.result_summary.primary === "object" && (
        <>
          <h2>VAL-selected primary</h2>
          <BenchCard row={exp.result_summary.primary as Record<string, unknown>} />
        </>
      )}
      {uncond && (
        <>
          <h2>Unconditional ALL_83 (TRAIN / VAL / TEST separate)</h2>
          <SplitTable summary={exp.result_summary} />
          <h2>EV by split</h2>
          <SplitBars summary={exp.result_summary} />
          <h2>Equity</h2>
          <Equity points={equity} />
          <h2>Drawdown</h2>
          <Drawdown points={equity} />
          <h2>Trade P&amp;L distribution</h2>
          <PnlHist points={equity} />
        </>
      )}
      <h2>Hypotheses</h2>
      <div className="row">
        <input placeholder="filter condition" value={q} onChange={(e) => setQ(e.target.value)} />
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          {["ALL", "CANDIDATE", "ROBUST", "CANDIDATE_THIN_VALIDATION", "OVERFIT", "REJECTED", "EXPLORATORY"].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <span className="muted">{filtered.length} / {hyps.length}</span>
      </div>
      <HypTable rows={filtered} />
      {promos.length > 0 && (
        <>
          <h2>Promotion history</h2>
          <table>
            <thead><tr><th>When</th><th>From</th><th>To</th><th>By</th><th>Reason</th></tr></thead>
            <tbody>
              {promos.map((p) => (
                <tr key={p.id}>
                  <td className="muted">{p.created_at.slice(0, 19)}</td>
                  <td>{p.from_status}</td>
                  <td>{p.to_status}</td>
                  <td>{p.created_by}</td>
                  <td>{p.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </>
  );
}

function BenchCard({ row }: { row: Record<string, unknown> }) {
  const split = (k: string) => row[k] as { n?: number; ev_cents?: number } | undefined;
  return (
    <div className="row">
      <div className="card"><div className="k">Condition</div><div className="v" style={{ fontSize: 14 }}>{String(row.condition ?? "")}</div></div>
      <div className="card"><div className="k">TRAIN n / EV</div><div className="v">{split("train")?.n ?? "—"} / <span className={evClass(split("train")?.ev_cents)}>{fmt(split("train")?.ev_cents)}</span></div></div>
      <div className="card"><div className="k">VAL n / EV</div><div className="v">{split("validation")?.n ?? "—"} / <span className={evClass(split("validation")?.ev_cents)}>{fmt(split("validation")?.ev_cents)}</span></div></div>
      <div className="card"><div className="k">TEST n / EV</div><div className="v">{split("test")?.n ?? "—"} / <span className={evClass(split("test")?.ev_cents)}>{fmt(split("test")?.ev_cents)}</span></div></div>
      <div className="card"><div className="k">q / status</div><div className="v">{fmt(row.q_value as number | undefined, 3)} <span className={`badge ${String(row.classification ?? "")}`}>{String(row.classification ?? "")}</span></div></div>
    </div>
  );
}

function SplitTable({ summary }: { summary?: Record<string, unknown> | null }) {
  const u = summary?.unconditional as Record<string, unknown> | undefined;
  if (!u) return null;
  const blocks = ["train", "validation", "test", "all"] as const;
  const pick = (key: typeof blocks[number]) => {
    const b = u[key] as Record<string, number> | undefined;
    return b ?? (u[key === "validation" ? "VAL" : key] as Record<string, number> | undefined);
  };
  return (
    <table>
      <thead>
        <tr><th>Split</th><th>N</th><th>WR</th><th>EV¢</th><th>P&L $</th></tr>
      </thead>
      <tbody>
        {blocks.map((k) => {
          const b = pick(k) || {};
          return (
            <tr key={k}>
              <td>{k.toUpperCase()}</td>
              <td className="mono">{b.n ?? "—"}</td>
              <td className="mono">{fmt(b.win_rate, 3)}</td>
              <td className={`mono ${evClass(b.ev_cents)}`}>{fmt(b.ev_cents)}</td>
              <td className={`mono ${evClass(b.pnl_usd)}`}>{fmt(b.pnl_usd)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function HypTable({ rows }: { rows: Hypothesis[] }) {
  const sorted = [...rows].sort((a, b) => (a.rank ?? 9999) - (b.rank ?? 9999));
  return (
    <table>
      <thead>
        <tr>
          <th>Rank</th><th>Hypothesis</th><th>Train n/EV</th><th>VAL n/EV</th><th>TEST n/EV</th><th>q</th><th>Status</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((h, i) => {
          const tn = h.train?.n ?? h.train_n;
          const vn = h.validation?.n ?? h.val_n;
          const xn = h.test?.n ?? h.test_n;
          const te = h.train?.ev_cents ?? h.train_ev;
          const ve = h.validation?.ev_cents ?? h.val_ev;
          const xe = h.test?.ev_cents ?? h.test_ev;
          return (
            <tr key={`${h.condition}-${i}`}>
              <td className="mono">{h.rank ?? i + 1}</td>
              <td className="mono">{h.condition}</td>
              <td className="mono">{tn} / <span className={evClass(te)}>{fmt(te)}</span></td>
              <td className="mono">{vn} / <span className={evClass(ve)}>{fmt(ve)}</span></td>
              <td className="mono">{xn} / <span className={evClass(xe)}>{fmt(xe)}</span></td>
              <td className="mono">{fmt(h.q_value, 3)}</td>
              <td><span className={`badge ${h.classification ?? ""}`}>{h.classification ?? "—"}</span></td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function Jobs() {
  const [rows, setRows] = useState<Job[]>([]);
  useEffect(() => { api.jobs().then(setRows).catch(() => undefined); }, []);
  return (
    <>
      <h1>Jobs</h1>
      <table>
        <thead><tr><th>Job</th><th>Experiment</th><th>Status</th><th>Progress</th></tr></thead>
        <tbody>
          {rows.map((j) => (
            <tr key={j.id}>
              <td><NavLink to={`/jobs/${j.id}`}>{j.id}</NavLink></td>
              <td className="mono">{j.experiment_id}</td>
              <td><span className={`badge ${j.status}`}>{j.status}</span></td>
              <td className="mono">{j.progress_done}/{j.progress_total}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function JobDetail() {
  const { id } = useParams();
  const [job, setJob] = useState<Job | null>(null);
  useEffect(() => {
    if (!id) return;
    let stop = false;
    const tick = () => api.job(id).then((j) => { if (!stop) setJob(j); });
    tick();
    const t = setInterval(tick, 1500);
    return () => { stop = true; clearInterval(t); };
  }, [id]);
  if (!job) return <p>Loading…</p>;
  return (
    <>
      <h1>Job {job.id}</h1>
      <p><NavLink to={`/experiments/${job.experiment_id}`}>Open experiment</NavLink></p>
      <span className={`badge ${job.status}`}>{job.status}</span>
      <p>Progress {job.progress_done}/{job.progress_total} · {job.current_hypothesis}</p>
      {job.error && <p className="err">{job.error}</p>}
      {(job.status === "RUNNING" || job.status === "QUEUED" || job.status === "CANCEL_REQUESTED") && (
        <button type="button" className="secondary" onClick={() => api.cancelJob(job.id).then(setJob)}>Cancel</button>
      )}
      <progress value={job.progress_done} max={Math.max(job.progress_total, 1)} style={{ width: "100%" }} />
      {job.status === "COMPLETED" && <p><NavLink to={`/experiments/${job.experiment_id}`}>View results</NavLink></p>}
      <h2>Logs</h2>
      <pre className="log">{job.logs.join("\n")}</pre>
    </>
  );
}

function Candidates() {
  const [rows, setRows] = useState<Candidate[]>([]);
  useEffect(() => { api.candidates().then(setRows).catch(() => undefined); }, []);
  return (
    <>
      <h1>Research candidates</h1>
      <div className="notice">None of these are production. Promotion is explicit and cannot skip CANDIDATE → PRODUCTION.</div>
      <table>
        <thead><tr><th>Condition</th><th>Status</th><th>Experiment</th><th>q / TEST EV</th></tr></thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.id}>
              <td className="mono">{c.condition}</td>
              <td><span className={`badge ${c.status}`}>{c.status}</span></td>
              <td><NavLink to={`/experiments/${c.experiment_id}`}>{c.experiment_id}</NavLink></td>
              <td className="mono">{fmt(c.payload.q_value as number | undefined, 3)} / {fmt(c.payload.test_ev as number | undefined)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function Prospective83() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    api.prospective83().then(setData).catch((e: Error) => setErr(e.message));
  }, []);
  const summary = data?.summary as Record<string, unknown> | null | undefined;
  const coverage = (summary?.coverage ?? {}) as Record<string, unknown>;
  const candidates = (summary?.candidates ?? data?.frozen_candidates ?? []) as Record<string, unknown>[];
  const layers = (data?.layers ?? {}) as Record<string, unknown>;
  const answer = String(data?.status ?? summary?.answer ?? "NOT_RUN");
  const reqs = (data?.requirements ?? {}) as Record<string, unknown>;
  const engine = data?.engine as Record<string, unknown> | undefined;
  const headline = String(engine?.headline_status ?? answer);
  return (
    <>
      <h1>Prospective 83¢ validation</h1>
      <div className="notice">
        Research mode <b className="mono">B1_FIRST83_PROSPECTIVE/v1</b>. Same engine as CLI.
        Existing TEST through 2026-06-27 is consumed. Do not retune on the holdout.
        PRODUCTION_COUNT = 0.
      </div>
      <p><b>{headline}</b></p>
      {typeof data?.reason === "string" && <p className="muted">{data.reason as string}</p>}
      {err && <p className="err">{err}</p>}
      <div className="row">
        <div className={`card ${answer === "INSUFFICIENT DATA" || answer === "NOT_RUN" ? "layer-holdout" : ""}`}>
          <div className="k">Holdout answer</div>
          <div className="v" style={{ fontSize: 18 }}>{answer}</div>
        </div>
        <div className="card layer-frozen">
          <div className="k">Locked cutoff</div>
          <div className="v" style={{ fontSize: 18 }}>{String(coverage.existing_cutoff ?? data?.cutoff ?? "2026-06-27")}</div>
        </div>
        <div className="card layer-holdout">
          <div className="k">W7 ∩ post-cutoff W6</div>
          <div className="v">{String(coverage.w7_post_cutoff_games ?? "—")}</div>
        </div>
        <div className="card">
          <div className="k">First-83 in holdout</div>
          <div className="v">{String(coverage.first83_eligible ?? 0)}</div>
        </div>
        <div className="card">
          <div className="k">Production</div>
          <div className="v">0</div>
        </div>
        <div className="card">
          <div className="k">Required holdout N</div>
          <div className="v">{String(reqs.minimum_test_n ?? 25)}</div>
        </div>
        <div className="card">
          <div className="k">W6 available</div>
          <div className="v">{String(reqs.available_games ?? "—")}</div>
        </div>
      </div>
      <h2>Why the holdout is empty</h2>
      <table>
        <tbody>
          <tr><th>status</th><td className="mono">{answer}</td></tr>
          <tr><th>required_games</th><td className="mono">{String(reqs.required_games ?? "—")}</td></tr>
          <tr><th>available_games (W6)</th><td className="mono">{String(reqs.available_games ?? "—")}</td></tr>
          <tr><th>w7_overlap</th><td className="mono">{String(reqs.w7_overlap ?? "—")}</td></tr>
          <tr><th>available first-83</th><td className="mono">{String((data?.prospective as { n?: number } | undefined)?.n ?? 0)}</td></tr>
          <tr><th>locked_candidate</th><td className="mono">{String(reqs.locked_candidate ?? "start_price_band=40_49")}</td></tr>
          <tr><th>minimum_ev</th><td className="mono">{String(reqs.minimum_ev ?? 3)}¢ hypothetical research</td></tr>
        </tbody>
      </table>
      <h2>Evidence layers</h2>
      <table>
        <thead><tr><th>Layer</th><th>Meaning</th></tr></thead>
        <tbody>
          <tr>
            <td><span className="badge FROZEN_HISTORICAL_RESULT">FROZEN HISTORICAL RESULT</span></td>
            <td>{String(layers.FROZEN_HISTORICAL_RESULT ?? "locked TRAIN/VAL/TEST; not re-selected")}</td>
          </tr>
          <tr>
            <td><span className="badge PROSPECTIVE_VALIDATION_RESULT">PROSPECTIVE VALIDATION RESULT</span></td>
            <td>{String(layers.PROSPECTIVE_VALIDATION_RESULT ?? "—")}</td>
          </tr>
          <tr>
            <td><span className="badge POST_HOLDOUT_DISCOVERY">POST_HOLDOUT_DISCOVERY</span></td>
            <td>{String(layers.POST_HOLDOUT_DISCOVERY ?? "not run")}</td>
          </tr>
        </tbody>
      </table>
      <h2>Frozen candidates</h2>
      <table>
        <thead>
          <tr>
            <th>Candidate</th>
            <th>Definition</th>
            <th>Historical TEST EV</th>
            <th>Prospective N</th>
            <th>Prospective EV</th>
            <th>95% CI</th>
            <th>Cost survival</th>
            <th>Class</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((c, i) => {
            const hist = (c.historical ?? {}) as Record<string, number>;
            const pro = (c.prospective ?? {}) as Record<string, unknown>;
            const boot = (c.bootstrap ?? null) as { ci95?: number[] } | null;
            const ci = boot?.ci95 ? `[${fmt(boot.ci95[0])} , ${fmt(boot.ci95[1])}]` : "—";
            return (
              <tr key={String(c.hypothesis_id ?? c.id ?? i)}>
                <td>{String(c.name ?? c.id ?? "")}<div className="muted mono">{String(c.hypothesis_id ?? c.id ?? "")}</div></td>
                <td className="mono">{String(c.condition ?? "")}</td>
                <td className={`mono ${evClass(hist.test_ev)}`}>{hist.test_ev == null ? "—" : `${hist.test_ev > 0 ? "+" : ""}${fmt(hist.test_ev)}¢`}</td>
                <td className="mono">{String(pro.n_unique_games ?? 0)}</td>
                <td className={`mono ${evClass(pro.ev_cents as number | undefined)}`}>{pro.ev_cents == null ? "—" : `${fmt(pro.ev_cents as number)}¢`}</td>
                <td className="mono">{ci}</td>
                <td className="mono">{c.cost_survival_max_cents == null ? "—" : `${fmt(c.cost_survival_max_cents as number)}¢`}</td>
                <td><span className={`badge ${String(c.classification ?? "INSUFFICIENT_DATA")}`}>{String(c.classification ?? "INSUFFICIENT_DATA")}</span></td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <h2>Coverage / provenance</h2>
      <p className="muted">W6 after cutoff is not a first-83 universe. First-exact-83 requires a W7 TRADE at 83¢.</p>
      <pre className="log">{JSON.stringify({ coverage, reproducibility: data?.reproducibility, headline: summary?.headline }, null, 2)}</pre>
    </>
  );
}

function Datasets() {
  const [rows, setRows] = useState<Dataset[]>([]);
  useEffect(() => { api.datasets().then(setRows).catch(() => undefined); }, []);
  return (
    <>
      <h1>Datasets</h1>
      {rows.map((d) => (
        <div key={`${d.id}-${d.version}`} className="card" style={{ marginBottom: 12, minWidth: 0 }}>
          <div className="k">{d.id} {d.version}</div>
          <div className="v" style={{ fontSize: 16 }}>{d.name}</div>
          <p>{d.event_definition}</p>
          <p>Games: <b className="mono">{d.game_count ?? "—"}</b> · {d.status}</p>
          <p className="muted">Source: {d.source}</p>
          <p>
            Capabilities:
            {Object.entries(d.capabilities).map(([k, v]) => (
              <span key={k} className="badge" style={{ marginLeft: 6 }}>{k} {v ? "✓" : "—"}</span>
            ))}
          </p>
          <pre className="log">{JSON.stringify(d.quality, null, 2)}</pre>
        </div>
      ))}
    </>
  );
}

function Strategies() {
  const [rows, setRows] = useState<Strategy[]>([]);
  useEffect(() => { api.strategies().then(setRows).catch(() => undefined); }, []);
  return (
    <>
      <h1>Strategies</h1>
      {rows.map((s) => (
        <div key={s.id} className="card" style={{ minWidth: 0 }}>
          <div className="v" style={{ fontSize: 18 }}>{s.id}</div>
          <p>{s.description}</p>
          <p>Research: {s.research_status} · Production: <b>{s.production_status}</b></p>
          <p className="muted">{s.version}</p>
        </div>
      ))}
    </>
  );
}

function ModelsPage() {
  const [rows, setRows] = useState<Model[]>([]);
  useEffect(() => { api.models().then(setRows).catch(() => undefined); }, []);
  return (
    <>
      <h1>Models</h1>
      <table>
        <thead><tr><th>Model</th><th>Strategy</th><th>Health</th><th>Status</th></tr></thead>
        <tbody>
          {rows.map((m) => (
            <tr key={m.id}>
              <td className="mono">{m.id}</td><td>{m.strategy_id}</td>
              <td>{m.health}</td><td><span className={`badge ${m.status}`}>{m.status}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function Quality() {
  const [rows, setRows] = useState<Dataset[]>([]);
  useEffect(() => { api.datasets().then(setRows).catch(() => undefined); }, []);
  return (
    <>
      <h1>Data quality</h1>
      <p className="muted">Metrics come from registered artifacts. L2 is unavailable on B1 first-83.</p>
      {rows.map((d) => (
        <div key={d.id}>
          <h2>{d.id} {d.version}</h2>
          <pre className="log">{JSON.stringify(d.quality, null, 2)}</pre>
        </div>
      ))}
    </>
  );
}

function Compare() {
  const [rows, setRows] = useState<Experiment[]>([]);
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [left, setLeft] = useState<Experiment | undefined>();
  const [right, setRight] = useState<Experiment | undefined>();
  useEffect(() => {
    api.experiments().then((xs) => {
      setRows(xs);
      const done = xs.filter((e) => e.result_summary);
      if (done[0]) setA(done[0].id);
      else if (xs[0]) setA(xs[0].id);
      if (done[1]) setB(done[1].id);
      else if (xs[1]) setB(xs[1].id);
    }).catch(() => undefined);
  }, []);
  useEffect(() => {
    if (a) api.experiment(a).then(setLeft).catch(() => setLeft(undefined));
  }, [a]);
  useEffect(() => {
    if (b) api.experiment(b).then(setRight).catch(() => setRight(undefined));
  }, [b]);
  const cell = (exp: Experiment | undefined, split: string, field: string) => {
    const u = exp?.result_summary?.unconditional as Record<string, Record<string, number>> | undefined;
    const b = u?.[split] ?? u?.[split === "validation" ? "VAL" : split];
    return b?.[field];
  };
  return (
    <>
      <h1>Compare experiments</h1>
      <div className="row">
        <select value={a} onChange={(e) => setA(e.target.value)}>{rows.map((e) => <option key={e.id} value={e.id}>{e.definition.name}</option>)}</select>
        <select value={b} onChange={(e) => setB(e.target.value)}>{rows.map((e) => <option key={e.id} value={e.id}>{e.definition.name}</option>)}</select>
      </div>
      <table>
        <thead><tr><th></th><th>A</th><th>B</th></tr></thead>
        <tbody>
          <tr><th>ID</th><td className="mono">{left?.id}</td><td className="mono">{right?.id}</td></tr>
          <tr><th>Status</th><td>{left?.status}</td><td>{right?.status}</td></tr>
          <tr><th>Dataset</th><td>{left?.definition.dataset_id}/{left?.definition.dataset_version}</td><td>{right?.definition.dataset_id}/{right?.definition.dataset_version}</td></tr>
          <tr><th>Strategy</th><td>{left?.definition.strategy_id}</td><td>{right?.definition.strategy_id}</td></tr>
          <tr><th>Search / tests</th><td>{left?.definition.search_method} / {String(left?.result_summary?.number_of_tests ?? "—")}</td><td>{right?.definition.search_method} / {String(right?.result_summary?.number_of_tests ?? "—")}</td></tr>
          <tr><th>TRAIN EV / n</th><td className={evClass(cell(left, "train", "ev_cents"))}>{fmt(cell(left, "train", "ev_cents"))} / {cell(left, "train", "n") ?? "—"}</td><td className={evClass(cell(right, "train", "ev_cents"))}>{fmt(cell(right, "train", "ev_cents"))} / {cell(right, "train", "n") ?? "—"}</td></tr>
          <tr><th>VAL EV / n</th><td className={evClass(cell(left, "validation", "ev_cents"))}>{fmt(cell(left, "validation", "ev_cents"))} / {cell(left, "validation", "n") ?? "—"}</td><td className={evClass(cell(right, "validation", "ev_cents"))}>{fmt(cell(right, "validation", "ev_cents"))} / {cell(right, "validation", "n") ?? "—"}</td></tr>
          <tr><th>TEST EV / n</th><td className={evClass(cell(left, "test", "ev_cents"))}>{fmt(cell(left, "test", "ev_cents"))} / {cell(left, "test", "n") ?? "—"}</td><td className={evClass(cell(right, "test", "ev_cents"))}>{fmt(cell(right, "test", "ev_cents"))} / {cell(right, "test", "n") ?? "—"}</td></tr>
          <tr><th>Execution</th><td>{left?.definition.execution_model}</td><td>{right?.definition.execution_model}</td></tr>
          <tr><th>Parent</th><td className="mono">{left?.definition.parent_experiment_id ?? "—"}</td><td className="mono">{right?.definition.parent_experiment_id ?? "—"}</td></tr>
        </tbody>
      </table>
      <h2>Unconditional equity</h2>
      <div className="row">
        <div style={{ flex: 1 }}>
          <p className="muted">A</p>
          <Equity points={(left?.result_summary?.unconditional as { equity?: { date: string; cumulative_usd: number }[] } | undefined)?.equity} />
        </div>
        <div style={{ flex: 1 }}>
          <p className="muted">B</p>
          <Equity points={(right?.result_summary?.unconditional as { equity?: { date: string; cumulative_usd: number }[] } | undefined)?.equity} />
        </div>
      </div>
    </>
  );
}

function ResultsIndex() {
  const [rows, setRows] = useState<Experiment[]>([]);
  useEffect(() => { api.experiments().then(setRows).catch(() => undefined); }, []);
  const done = rows.filter((e) => e.result_summary);
  return (
    <>
      <h1>Results</h1>
      <p className="muted">Completed experiments with stored summaries. TEST is never mixed into TRAIN/VAL headlines.</p>
      <ExpTable rows={done} />
    </>
  );
}

function SystemPage() {
  const [sys, setSys] = useState<Record<string, unknown> | null>(null);
  const [orch, setOrch] = useState<Record<string, unknown> | null>(null);
  useEffect(() => {
    api.system().then(setSys).catch(() => undefined);
    api.orchestration().then(setOrch).catch(() => undefined);
  }, []);
  return (
    <>
      <h1>System</h1>
      <p>Internal research console. Not momentosystems.com. No venue keys in this UI.</p>
      <h2>Orchestration (manual)</h2>
      <pre className="log">{JSON.stringify(orch, null, 2)}</pre>
      <h2>Engine</h2>
      <pre className="log">{JSON.stringify(sys, null, 2)}</pre>
    </>
  );
}

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/experiments" element={<Experiments />} />
        <Route path="/experiments/:id" element={<ExperimentDetail />} />
        <Route path="/results" element={<ResultsIndex />} />
        <Route path="/results/:id" element={<ExperimentDetail />} />
        <Route path="/new" element={<NewBacktest />} />
        <Route path="/jobs" element={<Jobs />} />
        <Route path="/jobs/:id" element={<JobDetail />} />
        <Route path="/candidates" element={<Candidates />} />
        <Route path="/prospective" element={<Prospective83 />} />
        <Route path="/datasets" element={<Datasets />} />
        <Route path="/strategies" element={<Strategies />} />
        <Route path="/models" element={<ModelsPage />} />
        <Route path="/quality" element={<Quality />} />
        <Route path="/compare" element={<Compare />} />
        <Route path="/system" element={<SystemPage />} />
      </Routes>
    </Layout>
  );
}
