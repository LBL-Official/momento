import { useEffect, useMemo, useState } from "react";
import {
  BallhogError,
  fetchHealth,
  fetchPositions,
  fetchState,
  type BallhogHealth,
  type BallhogIntent,
  type BallhogListRow,
  type BallhogState,
  type LoadState,
  type SurfaceCell,
} from "./api78";
import { cents, loadedQty, loadedRho, num, text } from "./text";

const TK_ULTRA = "http://127.0.0.1:5190/#/tk-ultra";
const BDR = "http://127.0.0.1:5190/#/bdr";
const BOOK = "FIRST78_67";

function cellKey(cell: SurfaceCell): string {
  return `${cell.q_hedge ?? "x"}-${cell.hedge_price_cents ?? "none"}`;
}

function isStar(cell: SurfaceCell, state: BallhogState | null): boolean {
  const chosen = state?.decision?.chosen_frontier_point;
  if (!chosen) return false;
  return cell.q_hedge === chosen.q_hedge && cell.hedge_price_cents === chosen.hedge_price_cents;
}

function rowId(row: BallhogListRow): string {
  return String(row.trade_id || row.position_id || "");
}

function classifyError(err: BallhogError): LoadState {
  const code = err.code || "";
  if (code === "QUERY_REJECTED" || code.includes("AS_OF") || /as_of/i.test(err.message)) return "INVALID_AS_OF";
  if (code === "SOURCE_UNAVAILABLE") return "SOURCE_UNAVAILABLE";
  return "QUERY_ERROR";
}

export default function App() {
  const [health, setHealth] = useState<BallhogHealth | null>(null);
  const [rows, setRows] = useState<BallhogListRow[]>([]);
  const [tradeId, setTradeId] = useState("");
  const [asOf, setAsOf] = useState("");
  const [qDir, setQDir] = useState("1");
  const [state, setState] = useState<BallhogState | null>(null);
  const [selected, setSelected] = useState<SurfaceCell | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("NOT_LOADED");
  const [frontierOnly, setFrontierOnly] = useState(false);

  function applyState(body: BallhogState) {
    setState(body);
    setSelected(body.decision?.chosen_frontier_point || body.decision?.surface?.cells?.[0] || null);
    setLoadState("LOADED");
  }

  function loadTrade(id: string, stamp: string, quantity: string) {
    if (!id) {
      setLoadState("SOURCE_UNAVAILABLE");
      setError("SOURCE_UNAVAILABLE: no Austin trade selected");
      return;
    }
    if (!stamp) {
      setState(null);
      setSelected(null);
      setLoadState("SOURCE_UNAVAILABLE");
      setError("SOURCE_UNAVAILABLE: Austin replay path missing");
      return;
    }
    setLoadState("LOADING");
    setError(null);
    fetchState(id, stamp, quantity)
      .then(applyState)
      .catch((err: unknown) => {
        const fail = err instanceof BallhogError ? err : new BallhogError(0, String(err));
        setLoadState(classifyError(fail));
        setError(fail.code ? `${fail.code}: ${fail.message}` : fail.message);
      });
  }

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch((err: unknown) => {
        setError(err instanceof BallhogError ? err.message : String(err));
      });
    fetchPositions()
      .then((body) => {
        const positions = body.positions || [];
        setRows(positions);
        const firstReplay = positions.find((row) => row.default_as_of);
        const chosen = firstReplay || positions[0];
        if (!chosen) {
          setLoadState("SOURCE_UNAVAILABLE");
          setError("SOURCE_UNAVAILABLE: Austin 78/67 book is empty");
          return;
        }
        const id = rowId(chosen);
        const stamp = chosen.default_as_of || "";
        setTradeId(id);
        setAsOf(stamp);
        loadTrade(id, stamp, "1");
      })
      .catch((err: unknown) => {
        setLoadState("QUERY_ERROR");
        setError(err instanceof BallhogError ? err.message : String(err));
      });
  }, []);

  function onPositionChange(nextId: string) {
    const row = rows.find((item) => rowId(item) === nextId);
    const stamp = row?.default_as_of || "";
    setTradeId(nextId);
    setAsOf(stamp);
    setState(null);
    setSelected(null);
    loadTrade(nextId, stamp, qDir);
  }

  const loaded = loadState === "LOADED";
  const cells = state?.decision?.surface?.cells || [];
  const prices = state?.decision?.surface?.price_grid || [35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45];
  const frontierPts = state?.decision?.frontier?.frontier || [];
  const frontierQs = useMemo(() => new Set(frontierPts.map((row) => Number(row.q_hedge))), [frontierPts]);
  const qValues = useMemo(() => {
    const found = Array.from(new Set(cells.map((cell) => Number(cell.q_hedge)))).sort((a, b) => a - b);
    if (!frontierOnly) return found;
    return found.filter((q) => q === 0 || frontierQs.has(q));
  }, [cells, frontierOnly, frontierQs]);
  const intent: BallhogIntent | undefined = state?.intent;
  const decision = state?.decision;
  const explanation = decision?.explanation || state?.explanation;
  const largeQ = Number(state?.q_dir || qDir) > 8;

  return (
    <main className="desk">
      <header className="mast">
        <div>
          <p className="kicker">Hedging Analysis</p>
          <h1>Ballhog</h1>
        </div>
        <div className="mast-meta">
          <span className="pill is-on">LIVE EXECUTION = FALSE</span>
          <span className="pill">EXECUTION DISABLED</span>
          <span className="pill">LIVE FEED UNAVAILABLE</span>
          <span className="pill">HEDGE PRINT UNAVAILABLE</span>
          <span className="pill">{text(state?.feed_mode || health?.live_feed || "HISTORICAL")}</span>
          <span className="pill">{loadState}</span>
          <a className="pill" href="#/first80">
            80/40
          </a>
          <a className="pill" href={TK_ULTRA}>
            TK Ultra
          </a>
          <a className="pill" href={BDR}>
            BDR library
          </a>
        </div>
      </header>
      <p className="muted">
        FIRST78→67 exposure-removal optimizer ({BOOK}). Austin owns a_t on the 78/67 fit. Choosin Texas is the derived-four
        78/67 STATIC prior. Lock is 22 − p. Candle path ≠ fill. Frontend does not compute ρ*, alpha, or transitions.
      </p>
      {error ? <div className="banner is-bad">{error}</div> : null}
      {loadState === "SOURCE_UNAVAILABLE" && !error ? (
        <div className="banner is-bad">SOURCE_UNAVAILABLE: Austin replay path missing</div>
      ) : null}

      <section className="workspace">
        <div className="toolbar">
          <label>
            Position
            <select value={tradeId} onChange={(event) => onPositionChange(event.target.value)}>
              {rows.map((row) => (
                <option key={row.position_id} value={rowId(row)}>
                  {text(row.display_name || `${row.game || ""} · ${row.ticker || ""}`)}
                </option>
              ))}
            </select>
          </label>
          <label>
            as_of
            <input value={asOf} onChange={(event) => setAsOf(event.target.value)} placeholder="ISO-8601" />
          </label>
          <label>
            q_dir
            <input value={qDir} onChange={(event) => setQDir(event.target.value)} />
          </label>
          <button className="primary" type="button" onClick={() => loadTrade(tradeId, asOf, qDir)} disabled={loadState === "LOADING"}>
            {loadState === "LOADING" ? "Loading" : "Load"}
          </button>
        </div>

        <div className="stats">
          <div className="stat">
            <dt>Austin a_t</dt>
            <dd className="mono">{cents(state?.austin?.a_t)}</dd>
          </div>
          <div className="stat">
            <dt>Austin a_L / CI</dt>
            <dd className="mono">{cents(state?.austin?.a_l)}</dd>
          </div>
          <div className="stat">
            <dt>Support</dt>
            <dd>{text(state?.austin?.support)}</dd>
          </div>
          <div className="stat">
            <dt>N_eff</dt>
            <dd className="mono">{text(state?.austin?.effective_sample_size)}</dd>
          </div>
          <div className="stat">
            <dt>α delta from entry</dt>
            <dd className="mono">{cents(state?.austin?.alpha_delta_from_entry)}</dd>
          </div>
          <div className="stat">
            <dt>Current q_dir</dt>
            <dd className="mono">{text(state?.q_dir)}</dd>
          </div>
        </div>

        <div className="stage-grid">
          <article className="stage">
            <h2>Risk intent</h2>
            <p className="stage-value">{text(decision?.risk_intent || decision?.timing?.timing_state)}</p>
            <p className="muted tiny">WHEN from Austin evidence. Not a hedge fill.</p>
          </article>
          <article className="stage">
            <h2>Hedge feasibility</h2>
            <p className="stage-value">{text(decision?.hedge_feasibility)}</p>
            <p className="muted tiny">NO_ADMISSIBLE_HEDGE means risk-off is indicated, but no modeled 62–72 hedge preserves robust EV.</p>
          </article>
          <article className="stage star">
            <h2>Final target</h2>
            <p className="stage-value mono">
              q* {loadedQty(loaded, decision?.q_star)} · ρ* {loadedRho(loaded, decision?.rho_star)} · residual{" "}
              {loadedQty(loaded, decision?.delta_star ?? decision?.target_residual_qty)}
            </p>
            <p className="muted tiny">{text(decision?.decision_status)} · q*=0 is 0, not UNAVAILABLE</p>
          </article>
        </div>

        <div className="explanation">
          {explanation ? explanation : "UNAVAILABLE"}
        </div>

        <div className="split">
          <article>
            <h2>62–72 theoretical surface</h2>
            <p className="muted tiny">
              Click a cell. Numbers are API cells only. Not a fill.
              {largeQ ? " Large q_dir: scroll the grid. Frontier filter hides rows; it does not shrink the backend set." : ""}
            </p>
            {largeQ ? (
              <label className="inline">
                <input type="checkbox" checked={frontierOnly} onChange={(event) => setFrontierOnly(event.target.checked)} />
                Frontier q only
              </label>
            ) : null}
            <div className={largeQ ? "surface-wrap is-large" : "surface-wrap"}>
              <div className="surface">
                <div className="surface-row">
                  <div className="head">q \ p</div>
                  {prices.map((price) => (
                    <div className="head" key={price}>
                      {price}
                    </div>
                  ))}
                </div>
                {qValues.map((q) => {
                  if (q === 0) {
                    const zero = cells.find((cell) => cell.q_hedge === 0);
                    if (!zero) return null;
                    return (
                      <div className="surface-row" key={q}>
                        <div className="head">{q}</div>
                        <button
                          type="button"
                          className={`cell is-zero${selected && cellKey(selected) === cellKey(zero) ? " is-selected" : ""}${isStar(zero, state) ? " is-star" : ""}`}
                          onClick={() => setSelected(zero)}
                        >
                          {num(zero.economic_EV_cost_of_hedge, 1)}
                        </button>
                      </div>
                    );
                  }
                  return (
                    <div className="surface-row" key={q}>
                      <div className="head">{q}</div>
                      {prices.map((price) => {
                        const cell = cells.find((row) => row.q_hedge === q && row.hedge_price_cents === price);
                        if (!cell) return <div className="cell" key={price} />;
                        return (
                          <button
                            type="button"
                            key={price}
                            className={`cell${selected && cellKey(selected) === cellKey(cell) ? " is-selected" : ""}${isStar(cell, state) ? " is-star" : ""}`}
                            onClick={() => setSelected(cell)}
                          >
                            {num(cell.economic_EV_cost_of_hedge, 1)}
                          </button>
                        );
                      })}
                    </div>
                  );
                })}
              </div>
            </div>
            {selected ? (
              <pre className="intent cell-detail">{JSON.stringify(selected, null, 2)}</pre>
            ) : null}
          </article>
          <article>
            <h2>Frontier · economic EV cost vs T67 risk proxy removed</h2>
            <FrontierChart points={frontierPts} selected={selected} />
            <p className="muted tiny">
              {text(state?.decision?.frontier?.axes?.x)} vs {text(state?.decision?.frontier?.axes?.y)} (
              {text(state?.decision?.frontier?.axes?.y_metric)})
            </p>
            <h2>Transitions</h2>
            <p className="muted tiny">
              {text(state?.transitions?.availability)} · support {text(state?.transitions?.support)} · n_eff{" "}
              {text(state?.transitions?.sample_support)}
            </p>
            <div className="branches">
              {(state?.transitions?.branches || []).map((branch) => (
                <div className="branch" key={branch.label}>
                  <span>{text(branch.label)}</span>
                  <span className="mono">{num(branch.rate)}</span>
                </div>
              ))}
            </div>
          </article>
        </div>

        <article>
          <h2>BallhogHedgeIntent</h2>
          <p className="muted tiny">
            Handoff object only. Do not assess wing/base/β here.{" "}
            <a href={TK_ULTRA}>Open TK Ultra</a>
          </p>
          <pre className="intent">{intent ? JSON.stringify(intent, null, 2) : "UNAVAILABLE"}</pre>
        </article>

        <div className="provenance">
          <span className="pill is-on">
            Austin {text(state?.austin?.universe || health?.austin?.universe)} N={text(state?.austin?.n || health?.austin?.n)}
          </span>
          <span className="pill is-on">
            Choosin {text(state?.choosin_texas?.universe || health?.choosin_texas?.universe)} N=
            {text(state?.choosin_texas?.n || health?.choosin_texas?.n)}
          </span>
          <span className="pill">feed {text(state?.feed_mode)}</span>
          <span className="pill">LIVE FEED UNAVAILABLE</span>
          <span className="pill">HEDGE PRINT UNAVAILABLE</span>
          <span className="pill">EXECUTION DISABLED</span>
          <span className="pill">research_unit={text(state?.research_unit_qty)}</span>
        </div>
      </section>
    </main>
  );
}

function FrontierChart({ points, selected }: { points: SurfaceCell[]; selected: SurfaceCell | null }) {
  if (!points.length) {
    return <div className="muted tiny">No frontier points from backend.</div>;
  }
  const xs = points.map((row) => Number(row.economic_EV_cost_of_hedge));
  const ys = points.map((row) => Number(row.risk_removed));
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const dx = maxX - minX || 1;
  const dy = maxY - minY || 1;
  return (
    <svg className="chart" viewBox="0 0 400 220">
      <text x="12" y="16" className="axis-label">
        T67 risk proxy removed
      </text>
      <text x="210" y="214" className="axis-label">
        economic EV cost
      </text>
      {points.map((row, idx) => {
        const x = 24 + ((Number(row.economic_EV_cost_of_hedge) - minX) / dx) * 352;
        const y = 196 - ((Number(row.risk_removed) - minY) / dy) * 172;
        const on = selected != null && cellKey(selected) === cellKey(row);
        return <circle key={idx} className={on ? "dot on" : "dot"} cx={x} cy={y} r={on ? 5 : 3.5} />;
      })}
    </svg>
  );
}
