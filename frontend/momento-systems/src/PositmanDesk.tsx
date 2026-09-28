import { useEffect, useState } from "react";
import { Desk } from "./Desk";

const DEFAULT_TRADE = "f84fd059fc0e1429";

type Props = { onHome: () => void };

type TradeRow = { trade_id?: string; game?: string; team?: string; ticker?: string };

function show(value: unknown): string {
  if (value == null || value === "") return "UNAVAILABLE";
  return String(value);
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

async function getJson(path: string): Promise<Record<string, unknown>> {
  const res = await fetch(path, { headers: { Accept: "application/json" } });
  const body = (await res.json().catch(() => null)) as Record<string, unknown> | null;
  if (!res.ok) {
    const detail = body?.detail;
    const message =
      detail && typeof detail === "object" && "message" in detail
        ? String((detail as { message?: string }).message)
        : `${path} ${res.status}`;
    throw new Error(message);
  }
  return body || {};
}

export default function PositmanDesk({ onHome }: Props) {
  const [tradeId, setTradeId] = useState(DEFAULT_TRADE);
  const [asOfDraft, setAsOfDraft] = useState("");
  const [asOf, setAsOf] = useState("");
  const [trades, setTrades] = useState<TradeRow[]>([]);
  const [health, setHealth] = useState<Record<string, unknown> | null>(null);
  const [sources, setSources] = useState<Record<string, unknown> | null>(null);
  const [state, setState] = useState<Record<string, unknown> | null>(null);
  const [plan, setPlan] = useState<Record<string, unknown> | null>(null);
  const [decision, setDecision] = useState<Record<string, unknown> | null>(null);
  const [trace, setTrace] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getJson("/api/positman/health").then(setHealth).catch(() => setHealth(null));
    getJson("/api/positman/sources").then(setSources).catch(() => setSources(null));
    getJson("/api/ballhog/positions")
      .then((body) => {
        const rows = Array.isArray(body.positions) ? (body.positions as TradeRow[]) : [];
        setTrades(rows.filter((row) => row.trade_id));
      })
      .catch(() => setTrades([]));
  }, []);

  useEffect(() => {
    let cancelled = false;
    const stamp = asOf.trim();
    const suffix = stamp ? `?as_of=${encodeURIComponent(stamp)}` : "";
    const id = encodeURIComponent(tradeId.trim() || DEFAULT_TRADE);
    setBusy(true);
    setError(null);
    setTrace(null);
    Promise.all([
      getJson(`/api/positman/state/${id}${suffix}`),
      getJson(`/api/positman/plan/${id}${suffix}`),
      getJson(`/api/dre/decision/${id}${suffix}`),
    ])
      .then(async ([nextState, nextPlan, nextDecision]) => {
        if (cancelled) return;
        setState(nextState);
        setPlan(nextPlan);
        setDecision(nextDecision);
        const traceId = String(nextPlan.trace_id || "");
        if (!traceId) return;
        try {
          const nextTrace = await getJson(`/api/positman/trace/${encodeURIComponent(traceId)}`);
          if (!cancelled) setTrace(nextTrace);
        } catch {
          if (!cancelled) setTrace({ availability: "UNAVAILABLE" });
        }
      })
      .catch((exc: Error) => {
        if (!cancelled) setError(exc.message);
      })
      .finally(() => {
        if (!cancelled) setBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [tradeId, asOf]);

  const ballhog = asRecord(asRecord(state?.ballhog).intent);
  const tk = asRecord(asRecord(state?.tk_ultra).assessment);
  const boundary = asRecord(decision?.execution_boundary);
  const events = Array.isArray(trace?.events) ? (trace.events as Record<string, unknown>[]) : [];
  const integrity = asRecord(trace?.integrity);
  const reasons = Array.isArray(plan?.reason_codes) ? (plan.reason_codes as string[]) : [];

  return (
    <Desk kicker="Position Management" title="Positman" active="bracket" scroll>
      <div className="page-meta">
        <a
          className="pill"
          href="#/"
          onClick={(event) => {
            event.preventDefault();
            onHome();
          }}
        >
          bracket
        </a>
        <span className="pill">LIVE EXECUTION = FALSE</span>
        <span className="pill">execution {show(health?.execution_enabled)}</span>
        <span className="pill">{busy ? "loading" : show(plan?.plan_status)}</span>
      </div>
      <p className="muted">
        Quantity from Ballhog. Route from TK Ultra. The plan, Drevo decision, and Systimo trace load with the
        selected trade. Candle path is not a fill.
      </p>
      {error ? <p className="banner is-bad">{error}</p> : null}
      <div className="trade-bar">
        <select value={tradeId} onChange={(event) => setTradeId(event.target.value)}>
          {!trades.some((row) => row.trade_id === tradeId) ? <option value={tradeId}>{tradeId}</option> : null}
          {trades.map((row) => (
            <option key={row.trade_id} value={row.trade_id}>
              {row.trade_id} · {row.game || row.team || row.ticker || "trade"}
            </option>
          ))}
        </select>
        <input
          value={asOfDraft}
          placeholder="as_of"
          onChange={(event) => setAsOfDraft(event.target.value)}
          onBlur={() => setAsOf(asOfDraft.trim())}
          onKeyDown={(event) => {
            if (event.key === "Enter") setAsOf(asOfDraft.trim());
          }}
        />
      </div>
      <section className="grid">
        <article>
          <h2>Ballhog quantity</h2>
          <p className="mono">{show(ballhog.q_star ?? plan?.requested_reduction_qty)}</p>
          <p className="muted">intent {show(ballhog.risk_intent ?? plan?.risk_intent)}</p>
          <p className="muted">decision {show(ballhog.decision_status)}</p>
          <p className="muted">availability {show(asRecord(state?.ballhog).availability)}</p>
        </article>
        <article>
          <h2>TK Ultra route</h2>
          <p className="mono">{show(tk.route_preference ?? plan?.route_preference)}</p>
          <p className="muted">availability {show(asRecord(state?.tk_ultra).availability)}</p>
        </article>
        <article>
          <h2>Positman plan</h2>
          <p className="mono">{show(plan?.position_route)}</p>
          <p>qty {show(plan?.planned_qty)}</p>
          <p className="muted">
            {show(plan?.plan_status)} · match {show(plan?.match_status)}
          </p>
          <p className="muted">{reasons.join(" · ") || "UNAVAILABLE"}</p>
          <p className="muted">trace {show(plan?.trace_id)}</p>
        </article>
        <article>
          <h2>Drevo decision</h2>
          <p className="mono">{show(decision?.decision_status)}</p>
          <p className="muted">structural {show(decision?.structural_status)}</p>
          <p className="muted">policy {show(decision?.policy_status)}</p>
          <p className="muted">authorized {show(decision?.execution_authorized)}</p>
          <p className="muted">boundary {show(boundary.status)}</p>
        </article>
      </section>
      <section className="grid">
        <article>
          <h2>Systimo chain</h2>
          <p className="muted">integrity {show(integrity.integrity_status)}</p>
          {events.length ? (
            <ul>
              {events.map((event) => (
                <li key={String(event.transition_event_id)}>
                  {show(event.stage_seq)} · {show(event.object_type)} · {show(event.event_status)}
                </li>
              ))}
            </ul>
          ) : (
            <p>UNAVAILABLE</p>
          )}
        </article>
        <article>
          <h2>Registry</h2>
          <details>
            <summary>position_management</summary>
            <p>
              Upstream hedging_analysis and relative_value_hedging. Downstream algorithmic_execution is coming
              soon. Inputs {(Array.isArray(sources?.inputs) ? sources.inputs : []).join(" · ") || "UNAVAILABLE"}.
              Output {show(sources?.output)}. Write {show(sources?.write)}.
            </p>
          </details>
        </article>
      </section>
    </Desk>
  );
}
