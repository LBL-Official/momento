import { useEffect, useMemo, useState } from "react";
import { DreError, fetchDecision, fetchPosition, type DreBook, type DrePositionState, type DrevoDecision, type EvidenceEvent } from "./api";
import { cents, signedCents, text } from "./text";

type Props = {
  positionId: string;
  asOf: string | null;
  book?: DreBook;
};

function rec(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function asList(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

export default function PositionPage({ positionId, asOf, book = "80" }: Props) {
  const [state, setState] = useState<DrePositionState | null>(null);
  const [decision, setDecision] = useState<DrevoDecision | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [asOfDraft, setAsOfDraft] = useState(asOf || "");

  useEffect(() => {
    setAsOfDraft(asOf || "");
  }, [asOf]);

  useEffect(() => {
    fetchPosition(positionId, asOf, book)
      .then((body) => {
        setState(body);
        setError(null);
      })
      .catch((err: unknown) => {
        setError(err instanceof DreError ? err.message : String(err));
      });
    fetchDecision(positionId, asOf, book)
      .then(setDecision)
      .catch(() => setDecision(null));
  }, [positionId, asOf, book]);

  const position = state?.position;
  const ct = rec(state?.trade_context);
  const live = rec(state?.live_state);
  const risk = state?.dynamic_risk;
  const intervention = state?.intervention;
  const ev = rec(risk?.ev_blocks);
  const ctEv = rec(ev.choosin_texas_prior);
  const austinEv = rec(ev.austin_conditional);
  const austinChg = rec(ev.austin_state_change);
  const features = asList(rec(rec(live.current_feature_vector).top));
  const entryDef = rec(ct.entry_definition);
  const histEv = rec(ct.historical_ev);
  const paths = asList(ct.baseline_path_profile);
  const timeline = state?.evidence_timeline || [];
  const chart = state?.chart;
  const provenance = rec(state?.provenance);
  const freshness = rec(state?.freshness);
  const details = rec(live.details);

  const gameState = useMemo(() => {
    if (!position) return "UNAVAILABLE";
    const period = position.period != null ? `Q${position.period}` : "";
    const clock = position.clock || "";
    const score =
      position.home_score != null && position.away_score != null
        ? `${position.home_score}–${position.away_score}`
        : "";
    return [period, clock, score].filter(Boolean).join(" · ") || "UNAVAILABLE";
  }, [position]);

  if (error) return <div className="banner is-bad">{error}</div>;
  if (!state) return <p className="muted">Loading position…</p>;

  return (
    <section className="position-desk">
      <header className="pos-header">
        <div>
          <p className="kicker">DYNAMIC RISK ENGINE</p>
          <h2>
            {text(position?.game)} · {text(position?.position_label)}
          </h2>
          <p className="muted small">
            {text(position?.sport || "NBA")} · {text(state.mode)} · {text(position?.ticker)}
          </p>
        </div>
        <dl className="header-meta">
          <div>
            <dt>Entry</dt>
            <dd className="mono">{cents(position?.entry_price_cents)}</dd>
          </div>
          <div>
            <dt>Size</dt>
            <dd className="mono">{text(position?.quantity)}</dd>
          </div>
          <div>
            <dt>Entry time</dt>
            <dd className="mono">{text(position?.entry_timestamp)}</dd>
          </div>
          <div>
            <dt>Current at as_of</dt>
            <dd className="mono">{cents(position?.current_price_cents)}</dd>
          </div>
          <div>
            <dt>as_of</dt>
            <dd className="mono">{text(state.as_of)}</dd>
          </div>
          <div>
            <dt>Game state</dt>
            <dd>{gameState}</dd>
          </div>
          <div>
            <dt>Austin inference</dt>
            <dd className="mono">{text(freshness.austin_inference_timestamp)}</dd>
          </div>
          <div>
            <dt>Feed</dt>
            <dd>{text(state.live_feed)}</dd>
          </div>
        </dl>
      </header>

      <div className="strip">
        <StripCell label="Entry" value={cents(position?.entry_price_cents)} />
        <StripCell label="Current at as_of" value={cents(position?.current_price_cents)} />
        <StripCell label="Change" value={signedCents(position?.price_change_cents)} />
        <StripCell label="Unrealized" value={signedCents(position?.unrealized_pnl_cents)} hint={text(position?.unrealized_pnl_basis)} />
        <StripCell label="Period" value={position?.period != null ? `Q${position.period}` : "UNAVAILABLE"} />
        <StripCell label="Clock" value={text(position?.clock)} />
        <StripCell
          label="Score"
          value={
            position?.home_score != null && position?.away_score != null
              ? `${position.home_score}–${position.away_score}`
              : "UNAVAILABLE"
          }
        />
        <StripCell label="as_of" value={text(state.as_of)} />
        <StripCell label="Feed" value={text(state.live_feed)} />
      </div>

      <form
        className="asof-form"
        onSubmit={(event) => {
          event.preventDefault();
          const next = asOfDraft.trim();
          const base = `${book === "78" ? "#/" : "#/first80/"}positions/${positionId}`;
          window.location.hash = next ? `${base}?as_of=${encodeURIComponent(next)}` : base;
        }}
      >
        <label>
          Replay as_of
          <input
            className="mono"
            value={asOfDraft}
            onChange={(event) => setAsOfDraft(event.target.value)}
            placeholder={state.as_of || "ISO-8601"}
          />
        </label>
        <button type="submit">Load</button>
      </form>

      <div className="cols">
        <article>
          <p className="kicker">Trade breakdown</p>
          <h2>Choosin Texas</h2>
          <p className="muted small">
            {book === "78"
              ? "Static FIRST78 78→67 prior. Qualified N is not the Austin training N."
              : "Static FIRST80 80→40 prior. N=936. Not Austin 604."}
          </p>
          <dl className="stack">
            <Row label="Trade" value={text(ct.articulation)} />
            <Row label="Population" value={text(ct.population)} />
            <Row label="Historical N" value={text(ct.historical_n)} />
            <Row label="Entry" value={cents(entryDef.entry_cents)} />
            <Row label="Loss barrier" value={cents(entryDef.loss_barrier_cents)} />
            <Row label="Historical survival" value={text(ct.historical_survival_rate)} />
            <Row label="Historical win rate" value={text(ct.historical_win_rate)} />
            <Row label="Expected economics" value={text(histEv.ev_display)} />
            <Row label="Trade class" value={text(ct.trade_classification)} />
            <Row label="Support" value="UNAVAILABLE" />
          </dl>
          <h3>Historical path</h3>
          <ul className="path-mini">
            {paths.map((row, idx) => {
              const item = rec(row);
              return (
                <li key={idx}>
                  <span>{text(item.key)}</span>
                  <span className="mono">{text(item.S_display)}</span>
                  <span className="mono">{text(item.ev_per_trade_display || item.ev_display)}</span>
                </li>
              );
            })}
          </ul>
          <p className="muted tiny">{text(ct.note)}</p>
        </article>

        <article>
          <p className="kicker">Position stratification</p>
          <h2>Austin</h2>
          <p className="muted small">Historical query at as_of. Live feed UNAVAILABLE. Never BUY/SKIP.</p>
          <dl className="stack">
            <Row label="Query status" value={text(live.query_status || live.availability)} />
            <Row label="Period / clock" value={`${text(live.period)} · ${text(live.game_clock)}`} />
            <Row label="Market price" value={cents(live.market_price_cents)} />
            <Row label="Price travel" value={signedCents(live.price_from_entry_cents)} />
            <Row label="Conditional EV" value={signedCents(rec(live.conditional_ev).conditional_ev_cents)} />
            <Row label="Support" value={text(rec(live.model_support).support)} />
            <Row label="Deterioration" value={text(rec(live.deterioration_state).availability)} />
            <Row label="Temporary distress" value={text(rec(live.temporary_distress_evidence).availability)} />
            <Row label="Persistent deterioration" value={text(rec(live.persistent_distress_evidence).availability)} />
            <Row label="Loss hazard" value={text(rec(live.loss_hazard).availability)} />
            <Row label="Model" value={text(live.source_model_version)} />
          </dl>
          <h3>Current evidence</h3>
          <ul className="path-mini">
            {features.slice(0, 5).map((row, idx) => {
              const item = rec(row);
              return (
                <li key={idx}>
                  <span>{text(item.feature)}</span>
                  <span className="mono">{text(item.query)}</span>
                </li>
              );
            })}
          </ul>
        </article>

        <article className="dre-strong">
          <p className="kicker">Dynamic risk</p>
          <h2>DREVO</h2>
          <dl className="stack synthesis">
            <Row label="Observation state" value={text(risk?.observation_state)} strong />
            <Row label="Hold reason" value={text(risk?.hold_reason_status)} strong />
            <Row label="Austin conditional EV" value={signedCents(risk?.austin_conditional_ev)} />
            <Row label="Change from entry" value={signedCents(risk?.change_from_entry)} />
            <Row label="Historical support" value={text(risk?.historical_support)} />
            <Row label="Dynamic risk class" value={text(risk?.dynamic_risk_class)} strong />
            <Row label="Intervention" value={intervention?.authorized ? "AUTHORIZED" : "NOT AUTHORIZED"} strong />
            <Row label="Execution" value={text(intervention?.execution)} strong />
          </dl>
          <p className="muted tiny">{text(risk?.note)}</p>
        </article>
      </div>

      <section className="ev-blocks">
        <article>
          <h2>Positman plan</h2>
          <p>quantity × route proposal</p>
          <p className="mono big">{text(rec(decision?.positman_ref).position_route)}</p>
          <p className="muted small">
            qty {text(rec(decision?.positman_ref).planned_qty)} · {text(rec(decision?.positman_ref).plan_status)}
          </p>
        </article>
        <article>
          <h2>Drevo decision</h2>
          <p>structural then policy</p>
          <p className="mono big">{text(decision?.decision_status)}</p>
          <p className="muted small">
            {text(decision?.structural_status)} · authorized {String(decision?.execution_authorized ?? false)}
          </p>
        </article>
        <article>
          <h2>Execution boundary</h2>
          <p>NOT_SUBMITTED</p>
          <p className="mono big">{text(rec(decision?.execution_boundary).status)}</p>
          <p className="muted small">{text(decision?.policy_status)}</p>
        </article>
      </section>

      <section className="ev-blocks">
        <article>
          <h2>Choosin Texas prior</h2>
          <p>{book === "78" ? "78→67 population EV" : "80→40 population EV"}</p>
          <p className="mono big">{text(ctEv.ev_display || histEv.ev_display)}</p>
          <p className="muted small">Definition · {text(ctEv.definition)}</p>
        </article>
        <article>
          <h2>Austin conditional</h2>
          <p>Conditional EV at as_of</p>
          <p className="mono big">{signedCents(austinEv.conditional_ev_cents)}</p>
          <p className="muted small">Definition · {text(austinEv.definition)}</p>
        </article>
        <article>
          <h2>Austin state change</h2>
          <dl className="stack">
            <Row label="EV at entry" value={signedCents(austinChg.ev_at_entry)} />
            <Row label="EV now" value={signedCents(austinChg.ev_now)} />
            <Row label="Δ conditional EV" value={signedCents(austinChg.ev_change)} />
          </dl>
          <p className="muted small">{text(austinChg.note)}</p>
        </article>
      </section>

      <section className="timeline-block">
        <h2>Position Evidence Timeline</h2>
        <p className="muted small">Not a risk-state sequence. V1 events are ENTRY / ENTRY_QUERY / AS_OF_QUERY / CURRENT_AS_OF.</p>
        <ol className="evidence">
          {timeline.map((event: EvidenceEvent, idx) => (
            <li key={`${event.event}-${idx}`}>
              <span className="ev-name">{event.event}</span>
              <span className="mono">{text(event.timestamp)}</span>
              <span className="mono">{cents(event.market_price_cents)}</span>
              <span className="muted small">{text(event.note)}</span>
            </li>
          ))}
        </ol>
        <PriceChart
          path={chart?.path || []}
          entry={chart?.entry_cents ?? 80}
          barrier={chart?.loss_barrier_cents ?? 40}
        />
        <h3>Canonical future DRE states</h3>
        <ul className="legend-states">
          {(state.future_state_legend || []).map((row) => (
            <li key={row.state}>
              {row.state} · {row.availability}
            </li>
          ))}
        </ul>
      </section>

      <section className="intervention">
        <h2>Intervention</h2>
        <dl className="stack">
          <Row label="Current response" value={text(intervention?.current_action)} />
          <Row label="Authorized" value={intervention?.authorized ? "YES" : "NO"} />
          <Row label="Policy" value={text(intervention?.policy_status || intervention?.policy_id)} />
          <Row label="Execution" value={text(intervention?.execution)} />
          <Row label="Reason" value={text(intervention?.action_reason)} />
        </dl>
      </section>

      <div className="drawers">
        <details>
          <summary>Trade details</summary>
          <pre>{JSON.stringify(ct, null, 2)}</pre>
        </details>
        <details>
          <summary>Austin model details</summary>
          <pre>{JSON.stringify({ live_state: { ...live, details: undefined }, details }, null, 2)}</pre>
        </details>
        <details>
          <summary>DRE details</summary>
          <pre>{JSON.stringify({ dynamic_risk: risk, intervention, freshness }, null, 2)}</pre>
        </details>
        <details>
          <summary>Provenance</summary>
          <pre>{JSON.stringify(provenance, null, 2)}</pre>
        </details>
      </div>
    </section>
  );
}

function Row({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd className={strong ? "strong" : undefined}>{value}</dd>
    </div>
  );
}

function StripCell({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd className="mono">{value}</dd>
      {hint ? <p className="muted tiny">{hint}</p> : null}
    </div>
  );
}

function PriceChart({
  path,
  entry,
  barrier,
}: {
  path: { t?: string; price_cents?: number | null }[];
  entry: number;
  barrier: number;
}) {
  const width = 920;
  const height = 220;
  const pad = 18;
  const priced = path.filter((row) => row.price_cents != null);
  if (!priced.length) return <p className="muted small">Price path UNAVAILABLE</p>;
  const ys = priced.map((row) => Number(row.price_cents));
  const minY = Math.min(0, barrier - 5, ...ys);
  const maxY = Math.max(100, entry + 5, ...ys);
  const x = (i: number) => pad + (i / Math.max(priced.length - 1, 1)) * (width - pad * 2);
  const y = (v: number) => pad + ((maxY - v) / Math.max(maxY - minY, 1)) * (height - pad * 2);
  const d = priced.map((row, i) => `${i === 0 ? "M" : "L"} ${x(i)} ${y(Number(row.price_cents))}`).join(" ");
  return (
    <svg className="price-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Price path">
      <line x1={pad} x2={width - pad} y1={y(entry)} y2={y(entry)} className="ref entry" />
      <line x1={pad} x2={width - pad} y1={y(barrier)} y2={y(barrier)} className="ref barrier" />
      <path d={d} className="series" />
      <circle cx={x(priced.length - 1)} cy={y(Number(priced[priced.length - 1].price_cents))} r={3} className="asof" />
      <text x={pad} y={y(entry) - 4} className="ref-label">
        ENTRY {entry}
      </text>
      <text x={pad} y={y(barrier) - 4} className="ref-label">
        LOSS {barrier}
      </text>
    </svg>
  );
}
