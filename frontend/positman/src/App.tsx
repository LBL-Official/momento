import { useEffect, useState } from "react";
import {
  PositmanError,
  fetchDecision,
  fetchHealth,
  fetchPlan,
  fetchPositions,
  fetchSources,
  fetchState,
  fetchTrace,
  type PositmanBook,
  type PositmanHealth,
  type PositmanPlan,
  type TradeOption,
} from "./api";

const PREFERRED_TRADE = "f84fd059fc0e1429";

function bookOf(): PositmanBook {
  const hash = window.location.hash.replace(/^#/, "");
  if (hash === "/first80" || hash.startsWith("/first80/") || hash.startsWith("/first80?")) return "80";
  return "78";
}

function text(value: unknown): string {
  if (value == null || value === "") return "UNAVAILABLE";
  return String(value);
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

export default function App() {
  const [book, setBook] = useState<PositmanBook>(bookOf);
  const [health, setHealth] = useState<PositmanHealth | null>(null);
  const [sources, setSources] = useState<Record<string, unknown> | null>(null);
  const [trades, setTrades] = useState<TradeOption[]>([]);
  const [tradeId, setTradeId] = useState(book === "80" ? PREFERRED_TRADE : "");
  const [asOfDraft, setAsOfDraft] = useState("");
  const [asOf, setAsOf] = useState("");
  const [state, setState] = useState<Record<string, unknown> | null>(null);
  const [plan, setPlan] = useState<PositmanPlan | null>(null);
  const [decision, setDecision] = useState<Record<string, unknown> | null>(null);
  const [trace, setTrace] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const onHash = () => setBook(bookOf());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    fetchHealth(book).then(setHealth).catch(() => setHealth(null));
    fetchSources(book).then(setSources).catch(() => setSources(null));
    fetchPositions(book)
      .then((body) => {
        const rows = (body.positions || []).filter((row) => row.trade_id);
        setTrades(rows);
        setTradeId((current) => {
          if (book === "80") return current || PREFERRED_TRADE;
          if (current.startsWith("f78-")) return current;
          return rows[0]?.trade_id || "";
        });
      })
      .catch(() => setTrades([]));
  }, [book]);

  useEffect(() => {
    let cancelled = false;
    const id = tradeId.trim() || (book === "80" ? PREFERRED_TRADE : "");
    if (!id) return;
    setBusy(true);
    setError(null);
    setTrace(null);
    Promise.all([fetchState(id, asOf || null, book), fetchPlan(id, asOf || null, book), fetchDecision(id, asOf || null, book)])
      .then(async ([nextState, nextPlan, nextDecision]) => {
        if (cancelled) return;
        setState(nextState);
        setPlan(nextPlan);
        setDecision(nextDecision);
        if (!nextPlan.trace_id) return;
        try {
          const nextTrace = await fetchTrace(nextPlan.trace_id, book);
          if (!cancelled) setTrace(nextTrace);
        } catch {
          if (!cancelled) setTrace({ availability: "UNAVAILABLE" });
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const fail = err instanceof PositmanError ? err : new PositmanError(0, String(err));
        setError(fail.code ? `${fail.code}: ${fail.message}` : fail.message);
      })
      .finally(() => {
        if (!cancelled) setBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [tradeId, asOf, book]);

  const ballhog = record(record(state?.ballhog).intent);
  const tk = record(record(state?.tk_ultra).assessment);
  const boundary = record(decision?.execution_boundary);
  const events = Array.isArray(trace?.events) ? (trace.events as Record<string, unknown>[]) : [];
  const integrity = record(trace?.integrity);
  const inputs = Array.isArray(sources?.inputs) ? (sources.inputs as string[]) : [];

  return (
    <main className="desk">
      <header className="mast">
        <div>
          <p className="kicker">POSITION MANAGEMENT</p>
          <h1>Positman</h1>
        </div>
        <div className="mast-meta">
          <nav className="page-nav">
            <a href="http://127.0.0.1:5190/#/systems/position_management">Bracket</a>
            <a href={book === "78" ? "#/first80" : "#/"}>{book === "78" ? "80/40" : "78/67"}</a>
            <a href="http://127.0.0.1:5192/">Ballhog</a>
            <a href="http://127.0.0.1:5190/#/tk-ultra">TK Ultra</a>
            <a href="http://127.0.0.1:5191/">Drevo</a>
            <a href="http://127.0.0.1:5193/">Systimo</a>
          </nav>
          <span className="pill">LIVE EXECUTION = FALSE</span>
          <span className="pill">no submit</span>
          <span className="pill">{busy ? "loading" : text(plan?.plan_status)}</span>
        </div>
      </header>
      <p className="muted">
        {book === "78" ? "FIRST78→67." : "FIRST80 80/40."} Quantity from Ballhog. Route from TK Ultra. Drevo is the
        structural gate. The plan and Systimo trace load with the selected trade. Candle path is not a fill.
        execution_enabled is {text(health?.execution_enabled)}.
      </p>
      {error ? <div className="banner is-bad">{error}</div> : null}
      <section className="controls">
        <label>
          trade
          <select value={tradeId} onChange={(event) => setTradeId(event.target.value)}>
            {!trades.some((row) => row.trade_id === tradeId) ? <option value={tradeId}>{tradeId}</option> : null}
            {trades.map((row) => (
              <option key={row.trade_id} value={row.trade_id}>
                {row.trade_id} · {row.game || row.team || row.ticker || "trade"}
              </option>
            ))}
          </select>
        </label>
        <label>
          as_of
          <input
            value={asOfDraft}
            onChange={(event) => setAsOfDraft(event.target.value)}
            onBlur={() => setAsOf(asOfDraft.trim())}
            onKeyDown={(event) => {
              if (event.key === "Enter") setAsOf(asOfDraft.trim());
            }}
            placeholder="Austin stamp"
          />
        </label>
      </section>
      <section className="merge">
        <article>
          <p className="kicker">Ballhog</p>
          <h2>quantity</h2>
          <p className="mono big">{text(ballhog.q_star ?? plan?.requested_reduction_qty)}</p>
          <p className="muted small">
            intent {text(ballhog.risk_intent ?? plan?.risk_intent)} · {text(record(state?.ballhog).availability)}
          </p>
        </article>
        <article className="times">×</article>
        <article>
          <p className="kicker">TK Ultra</p>
          <h2>route</h2>
          <p className="mono big">{text(tk.route_preference ?? plan?.route_preference)}</p>
          <p className="muted small">{text(record(state?.tk_ultra).availability)}</p>
        </article>
        <article className="equals">=</article>
        <article>
          <p className="kicker">Positman</p>
          <h2>{text(plan?.position_route)}</h2>
          <p className="mono big">qty {text(plan?.planned_qty)}</p>
          <p className="muted small">
            {text(plan?.plan_status)} · {text(plan?.match_status)}
          </p>
        </article>
      </section>
      <section className="panels">
        <article>
          <h2>Drevo decision</h2>
          <p className="mono big">{text(decision?.decision_status)}</p>
          <p className="muted small">structural {text(decision?.structural_status)}</p>
          <p className="muted small">policy {text(decision?.policy_status)}</p>
          <p className="muted small">authorized {text(decision?.execution_authorized)}</p>
          <p className="muted small">boundary {text(boundary.status)}</p>
        </article>
        <article>
          <h2>Systimo chain</h2>
          <p className="muted small">integrity {text(integrity.integrity_status)}</p>
          <p className="muted small">trace {text(plan?.trace_id)}</p>
          {events.length ? (
            <ul>
              {events.map((event) => (
                <li key={String(event.transition_event_id)}>
                  {text(event.stage_seq)} · {text(event.object_type)} · {text(event.event_status)}
                </li>
              ))}
            </ul>
          ) : (
            <p>UNAVAILABLE</p>
          )}
        </article>
      </section>
      <details className="registry">
        <summary>position_management</summary>
        <p className="muted small">
          Upstream hedging_analysis and relative_value_hedging. Inputs {inputs.join(" · ") || "UNAVAILABLE"}. Output{" "}
          {text(sources?.output)}. Write {text(sources?.write)}. Reasons{" "}
          {(plan?.reason_codes || []).join(" · ") || "UNAVAILABLE"}.
        </p>
      </details>
    </main>
  );
}
