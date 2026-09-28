import { useEffect, useMemo, useState, type FormEvent, type MouseEvent } from "react";
import { fetchTkUltra78 as fetchTkUltra, fetchTkUltra78Assess as fetchTkUltraAssess, fetchTkUltra78Health as fetchTkUltraHealth, postTkUltra78AssessV0 as postTkUltraAssessV0 } from "./api";
import { Desk } from "./Desk";
import type { TkUltraAssess, TkUltraDesk, TkUltraHealth, TkUltraV0Assess } from "./types";

type Props = {
  onHome: () => void;
};

type Fields = {
  wing_price: string;
  base_price: string;
  beta: string;
  wing_anchor: string;
  base_anchor: string;
  ticks_per_handle: string;
  pair: string;
  corridor_cents: string;
};

const EMPTY: Fields = {
  wing_price: "",
  base_price: "45",
  beta: "",
  wing_anchor: "",
  base_anchor: "80",
  ticks_per_handle: "1",
  pair: "yes_vs_opponent",
  corridor_cents: "67",
};

type BinaryFields = {
  a_entry_cents: string;
  a_stop_cents: string;
  a_bid_cents: string;
  b_ask_cents: string;
  a_anchor_cents: string;
  b_anchor_cents: string;
  a_ref_cents: string;
  b_observed_cents: string;
  a_ref_basis: string;
  b_observed_basis: string;
  q_a: string;
  q_b: string;
  b_avg_existing_cents: string;
};

const EMPTY_BINARY: BinaryFields = {
  a_entry_cents: "78",
  a_stop_cents: "67",
  a_bid_cents: "70",
  b_ask_cents: "32",
  a_anchor_cents: "78",
  b_anchor_cents: "22",
  a_ref_cents: "50",
  b_observed_cents: "48",
  a_ref_basis: "MID",
  b_observed_basis: "MID",
  q_a: "1",
  q_b: "0.4",
  b_avg_existing_cents: "52",
};

function Row({ label, value }: { label: string; value?: string | number | null }) {
  const shown = value == null || value === "" ? "UNAVAILABLE" : String(value);
  return (
    <div className="row">
      <dt>{label}</dt>
      <dd>{shown}</dd>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  hint,
}: {
  label: string;
  value: string;
  onChange: (next: string) => void;
  hint?: string;
}) {
  return (
    <label className="field">
      {label}
      <input
        className="field-input"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        autoComplete="off"
        spellCheck={false}
      />
      {hint ? <span className="muted">{hint}</span> : null}
    </label>
  );
}

export default function TkUltra({ onHome }: Props) {
  const [desk, setDesk] = useState<TkUltraDesk | null>(null);
  const [fields, setFields] = useState<Fields>(EMPTY);
  const [binary, setBinary] = useState<BinaryFields>(EMPTY_BINARY);
  const [assess, setAssess] = useState<TkUltraAssess | null>(null);
  const [v0, setV0] = useState<TkUltraV0Assess | null>(null);
  const [health, setHealth] = useState<TkUltraHealth | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchTkUltra()
      .then((body) => {
        if (!cancelled) setDesk(body);
      })
      .catch((exc: Error) => {
        if (!cancelled) setError(exc.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchTkUltraHealth()
      .then((body) => {
        if (!cancelled) setHealth(body);
      })
      .catch(() => {
        if (!cancelled) setHealth(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchTkUltraAssess(fields)
      .then((body) => {
        if (!cancelled) setAssess(body);
      })
      .catch((exc: Error) => {
        if (!cancelled) setError(exc.message);
      });
    return () => {
      cancelled = true;
    };
  }, [fields]);

  useEffect(() => {
    let cancelled = false;
    postTkUltraAssessV0(binary)
      .then((body) => {
        if (!cancelled) setV0(body);
      })
      .catch((exc: Error) => {
        if (!cancelled) setError(exc.message);
      });
    return () => {
      cancelled = true;
    };
  }, [binary]);

  const example = desk?.worked_example;
  const letter = desk?.source_letter;
  const readingCopy = useMemo(() => {
    if (!desk || !assess?.reading) return null;
    return desk.formula.reading[assess.reading] || assess.reading;
  }, [assess, desk]);

  function patchBinary(name: keyof BinaryFields, value: string) {
    setBinary((prev) => ({ ...prev, [name]: value }));
  }

  function loadAcceptanceOverlay() {
    setBinary(EMPTY_BINARY);
  }

  function forceCollinearQuotes() {
    setBinary((prev) => ({
      ...prev,
      a_ref_cents: prev.a_bid_cents,
      b_observed_cents: prev.b_ask_cents,
      a_ref_basis: "YES_BID",
      b_observed_basis: "YES_ASK",
    }));
  }

  function patch(name: keyof Fields, value: string) {
    setFields((prev) => {
      const next = { ...prev, [name]: value };
      if (name === "base_price" && (value === "78" || value === "69" || value === "67")) {
        next.corridor_cents = value;
      }
      return next;
    });
  }

  function goHome(event: MouseEvent<HTMLAnchorElement>) {
    event.preventDefault();
    onHome();
  }

  function loadLetterExample() {
    if (!example) return;
    setFields({
      wing_price: example.wing_price,
      base_price: example.base_price,
      beta: example.beta,
      wing_anchor: example.wing_anchor,
      base_anchor: example.base_anchor,
      ticks_per_handle: String(example.ticks_per_handle),
      pair: "futures_nq_es",
      corridor_cents: "",
    });
  }

  function setCorridor(cents: "78" | "69" | "67") {
    setFields({
      wing_price: "",
      base_price: cents,
      beta: "",
      wing_anchor: "",
      base_anchor: "80",
      ticks_per_handle: "1",
      pair: "yes_vs_opponent",
      corridor_cents: cents,
    });
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
  }

  if (error) {
    return (
      <Desk kicker="Relative value hedging · TK Ultra" title="TK Ultra" active="tk-ultra">
        <div className="page-meta">
          <a className="pill" href="#/tk-ultra/live-inputs">
            Live Inputs Needed
          </a>
        </div>
        <p className="banner is-bad">{error}</p>
      </Desk>
    );
  }

  if (!desk) {
    return (
      <Desk kicker="Relative value hedging · TK Ultra" title="TK Ultra" active="tk-ultra">
        <div className="page-meta">
          <a className="pill" href="#/tk-ultra/live-inputs">
            Live Inputs Needed
          </a>
        </div>
        <p className="muted">UNREAD</p>
      </Desk>
    );
  }

  const residualClass =
    assess?.reading === "WING_CHEAP" ? "is-ok" : assess?.reading === "WING_RICH" ? "is-bad" : "is-idle";

  return (
    <Desk kicker="Relative value hedging · TK Ultra" title="TK Ultra" active="tk-ultra">
      <p className="muted" style={{ marginTop: 14 }}>
        {desk.subtitle}. Named for {desk.named_for}.
      </p>
      <div className="page-meta">
        <a className="pill" href="#/" onClick={goHome}>
          bracket
        </a>
        <a className="pill" href="#/bdr">
          BDR
        </a>
        <a className="pill" href="#/tk-ultra/live-inputs">
          Live Inputs Needed
        </a>
        <span className="pill">research only</span>
        <span className="pill">formula ≠ truth</span>
        <span className="pill">FIRST78→67</span>
        <a className="pill" href="#/tk-ultra-80">
          80/40
        </a>
        <span className="pill">LIVE EXECUTION = FALSE</span>
        <span className="pill">
          Ballhog {health?.ballhog?.availability === "OBSERVED" ? "connected" : "unavailable"}
        </span>
      </div>
      <div className="banner">
        <h2>LIMITATIONS</h2>
        {desk.limitations.map((line) => (
          <p key={line}>{line}</p>
        ))}
        <p className="muted">{desk.note}</p>
      </div>

      <section className="grid" style={{ marginTop: 18 }}>
        <article className="wide">
          <h2>One number</h2>
          {assess?.status === "SOURCE_UNAVAILABLE" ? (
            <>
              <p className="hero-number is-idle">SOURCE_UNAVAILABLE</p>
              <p>{assess.detail}</p>
              <p className="muted">Missing: {(assess.missing || []).join(", ")}</p>
            </>
          ) : (
            <>
              <p className={`hero-number ${residualClass}`}>{assess?.rv_ticks ?? "UNREAD"}</p>
              <p className={residualClass}>{assess?.reading}</p>
              <p>{readingCopy}</p>
              {assess?.corridor_note ? <p className="muted">{assess.corridor_note}</p> : null}
              <div className="row">
                <dt>multiplier</dt>
                <dd>{assess?.relationship_multiplier}</dd>
              </div>
              <div className="row">
                <dt>expected move</dt>
                <dd>{assess?.expected_wing_move}</dd>
              </div>
              <div className="row">
                <dt>residual</dt>
                <dd>{assess?.residual}</dd>
              </div>
              <div className="row">
                <dt>ticks</dt>
                <dd>{assess?.rv_ticks}</dd>
              </div>
            </>
          )}
        </article>
        <article className="wide">
          <h2>Calculator</h2>
          <p className="muted">
            Same engine as <code>tk_relative_value_v1</code>. Empty wing or beta stays SOURCE_UNAVAILABLE.
          </p>
          <form className="calc-grid" onSubmit={onSubmit} style={{ marginTop: 12 }}>
            <Field
              label="Wing price"
              value={fields.wing_price}
              onChange={(value) => patch("wing_price", value)}
              hint="Hedge instrument now. Do not invent."
            />
            <Field
              label="Base price"
              value={fields.base_price}
              onChange={(value) => patch("base_price", value)}
              hint="Held position now."
            />
            <Field
              label="Beta"
              value={fields.beta}
              onChange={(value) => patch("beta", value)}
              hint="vol(wing) / vol(base). Inverse pair is negative."
            />
            <Field
              label="Ticks / handle"
              value={fields.ticks_per_handle}
              onChange={(value) => patch("ticks_per_handle", value)}
              hint="Nasdaq 4. Kalshi cents 1."
            />
            <Field
              label="Wing anchor"
              value={fields.wing_anchor}
              onChange={(value) => patch("wing_anchor", value)}
              hint="Wing at the same as-of as the base fill."
            />
            <Field
              label="Base anchor"
              value={fields.base_anchor}
              onChange={(value) => patch("base_anchor", value)}
              hint="Futures base anchor. The binary pair below is 78 and 22."
            />
          </form>
          <div className="page-meta">
            <button type="button" onClick={loadLetterExample}>
              Load TK NQ/ES letter
            </button>
            <button type="button" onClick={() => setCorridor("78")}>
              Entry 78
            </button>
            <button type="button" onClick={() => setCorridor("69")}>
              Corridor 69
            </button>
            <button type="button" onClick={() => setCorridor("67")}>
              Stop 67
            </button>
          </div>
        </article>
      </section>

      <article className="wide" style={{ marginTop: 14 }}>
        <h2>78 → 69 → 67</h2>
        <p>
          Ballhog owns <strong>when</strong> ({desk.corridor.owner_when}). TK Ultra owns{" "}
          <strong>rich / cheap</strong> ({desk.corridor.owner_rich_cheap}). The 69 and 67 prints are a
          counterfactual corridor around the 67 stop. Austin N={health?.austin?.n ?? "UNAVAILABLE"} and the
          Choosin prior N={health?.choosin_texas?.n ?? "UNAVAILABLE"} sit beside the quote. They are not residual inputs.
        </p>
        <table className="data-table" style={{ marginTop: 12 }}>
          <thead>
            <tr>
              <th>Print</th>
              <th>Role</th>
              <th>BDR (when)</th>
              <th>TK Ultra (rich / cheap)</th>
            </tr>
          </thead>
          <tbody>
            {desk.corridor.windows.map((window) => (
              <tr key={window.cents}>
                <td>{window.cents}</td>
                <td>{window.role}</td>
                <td>{window.bdr}</td>
                <td>{window.tk}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <h3>Pair</h3>
        <div className="row">
          <dt>Base A</dt>
          <dd>{desk.corridor.pair.base}</dd>
        </div>
        <div className="row">
          <dt>Wing B</dt>
          <dd>{desk.corridor.pair.wing}</dd>
        </div>
        <div className="row">
          <dt>Beta +</dt>
          <dd>{desk.corridor.pair.beta_same_direction}</dd>
        </div>
        <div className="row">
          <dt>Beta −</dt>
          <dd>{desk.corridor.pair.beta_inverse}</dd>
        </div>
        <h3>Implementation</h3>
        <ol>
          {desk.corridor.implementation.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ol>
      </article>

      <article className="wide" style={{ marginTop: 14 }}>
        <h2>BINARY COMPLEMENT V0</h2>
        <p className="muted">
          FIRST78 A/B YES. Default anchors 78 and 22. Server math only. The calculator above stays GENERIC_RV. Not an order.
        </p>
        <form className="calc-grid" onSubmit={onSubmit} style={{ marginTop: 12 }}>
          <Field label="A entry" value={binary.a_entry_cents} onChange={(value) => patchBinary("a_entry_cents", value)} />
          <Field label="A stop" value={binary.a_stop_cents} onChange={(value) => patchBinary("a_stop_cents", value)} />
          <Field label="A bid" value={binary.a_bid_cents} onChange={(value) => patchBinary("a_bid_cents", value)} hint="Route only." />
          <Field label="B ask" value={binary.b_ask_cents} onChange={(value) => patchBinary("b_ask_cents", value)} hint="Route only." />
          <Field label="A anchor" value={binary.a_anchor_cents} onChange={(value) => patchBinary("a_anchor_cents", value)} />
          <Field label="B anchor" value={binary.b_anchor_cents} onChange={(value) => patchBinary("b_anchor_cents", value)} />
          <Field
            label="A ref"
            value={binary.a_ref_cents}
            onChange={(value) => patchBinary("a_ref_cents", value)}
            hint="Relationship basis. Not auto A bid."
          />
          <Field
            label="B observed"
            value={binary.b_observed_cents}
            onChange={(value) => patchBinary("b_observed_cents", value)}
            hint="Relationship basis. Not auto B ask."
          />
          <Field label="A ref basis" value={binary.a_ref_basis} onChange={(value) => patchBinary("a_ref_basis", value)} />
          <Field
            label="B observed basis"
            value={binary.b_observed_basis}
            onChange={(value) => patchBinary("b_observed_basis", value)}
          />
          <Field label="q A" value={binary.q_a} onChange={(value) => patchBinary("q_a", value)} />
          <Field label="q B" value={binary.q_b} onChange={(value) => patchBinary("q_b", value)} />
          <Field
            label="B existing avg"
            value={binary.b_avg_existing_cents}
            onChange={(value) => patchBinary("b_avg_existing_cents", value)}
          />
        </form>
        <div className="page-meta">
          <button type="button" onClick={loadAcceptanceOverlay}>
            Load V0 overlay
          </button>
          <button type="button" onClick={forceCollinearQuotes}>
            Force collinear quotes
          </button>
        </div>
      </article>

      <section className="grid" style={{ marginTop: 18 }}>
        <article className="wide">
          <h2>Relationship</h2>
          <p className={`hero-number ${v0?.rv_state === "CHEAP" ? "is-ok" : v0?.rv_state === "RICH" ? "is-bad" : "is-idle"}`}>
            {v0?.relationship?.rv_state || "UNAVAILABLE"}
          </p>
          <Row label="basis" value={v0?.relationship?.relationship_basis_label} />
          <Row label="expected B" value={v0?.relationship?.expected_wing} />
          <Row label="observed B" value={v0?.relationship?.observed_wing} />
          <Row label="residual" value={v0?.relationship?.tk_residual} />
          <Row label="anchor validity" value={v0?.relationship?.anchor_validity} />
          {v0?.relationship_route_collinear ? (
            <p className="banner is-idle">{v0.relationship?.note}</p>
          ) : (
            <p className="muted">{v0?.relationship?.note}</p>
          )}
        </article>
        <article className="wide">
          <h2>Route</h2>
          <p className="hero-number is-idle">{v0?.route?.route_preference || "UNAVAILABLE"}</p>
          <Row label="A bid" value={v0?.route?.direct_exit_price} />
          <Row label="synthetic A exit" value={v0?.route?.synthetic_exit_price} />
          <Row label="gross route edge" value={v0?.route?.gross_route_edge} />
          <Row label="B parity" value={v0?.route?.b_route_parity_price} />
          <Row label="quality" value={v0?.route?.route_execution_quality} />
          <p className="muted">{v0?.route?.preference_note}</p>
        </article>
      </section>

      <section className="grid" style={{ marginTop: 18 }}>
        <article className="wide">
          <h2>Hedge budget / runway</h2>
          <Row label="A entry" value={v0?.hedge_budget?.a_entry} />
          <Row label="A stop" value={v0?.hedge_budget?.a_stop_benchmark} />
          <Row label="B stop-eq" value={v0?.hedge_budget?.stop_equivalent_b_avg} />
          <Row label="stop PnL" value={v0?.hedge_budget?.stop_pnl_benchmark} />
          <Row label="hedge fraction" value={v0?.hedge_budget?.hedge_fraction} />
          <Row label="max remaining avg" value={v0?.hedge_budget?.max_remaining_avg_price} />
          <Row label="runway vs ask" value={v0?.hedge_budget?.hedge_runway_vs_ask} />
          <Row label="cushion vs existing" value={v0?.hedge_budget?.cost_cushion_vs_existing_avg} />
          <Row label="fees" value={v0?.hedge_budget?.fees} />
          <Row label="slippage" value={v0?.hedge_budget?.slippage} />
        </article>
        <article className="wide">
          <h2>Completion-now vs 67-stop</h2>
          <p className="hero-number is-idle">{v0?.hedge_budget?.locked_pnl_if_completed_now || "UNAVAILABLE"}</p>
          <Row label="completed-now B avg" value={v0?.hedge_budget?.completed_now_b_avg} />
          <Row label="locked PnL" value={v0?.hedge_budget?.locked_pnl_if_completed_now} />
          <Row label="vs stop" value={v0?.hedge_budget?.gross_improvement_vs_stop_if_completed_now} />
          <p className="muted">Theoretical lock. Candle path ≠ fill. Not a live 67-stop rule.</p>
        </article>
      </section>

      <section className="grid" style={{ marginTop: 18 }}>
        <article className="wide">
          <h2>SIBLING CONTEXT — NOT MODEL INPUT</h2>
          <Row
            label="availability"
            value={
              typeof v0?.sibling_context === "object" ? v0.sibling_context.availability : String(v0?.sibling_context || "UNAVAILABLE")
            }
          />
          <Row
            label="intent status"
            value={typeof v0?.sibling_context === "object" ? v0.sibling_context.intent_status : undefined}
          />
          <Row label="q*" value={typeof v0?.sibling_context === "object" ? v0.sibling_context.q_star : undefined} />
          <Row label="ρ*" value={typeof v0?.sibling_context === "object" ? v0.sibling_context.rho_star : undefined} />
          <Row
            label="risk intent"
            value={typeof v0?.sibling_context === "object" ? v0.sibling_context.risk_intent : undefined}
          />
          <Row label="Position Management" value={v0?.position_management} />
          <p className="muted">
            {typeof v0?.sibling_context === "object" ? v0.sibling_context.note : "SIBLING CONTEXT — NOT MODEL INPUT"}
          </p>
        </article>
        <article className="wide">
          <h2>Provenance</h2>
          <Row label="Austin universe" value={v0?.austin?.universe} />
          <Row label="Austin N" value={v0?.austin?.n} />
          <Row label="Austin adapter" value={v0?.austin?.adapter} />
          <Row label="Choosin universe" value={v0?.choosin_texas?.universe} />
          <Row label="Choosin N" value={v0?.choosin_texas?.n} />
          <Row label="Choosin adapter" value={v0?.choosin_texas?.adapter} />
          <Row label="feed" value={v0?.feed_mode} />
          <Row label="live feed" value={v0?.live_feed} />
        </article>
      </section>

      <article className="wide" style={{ marginTop: 14 }}>
        <h2>Formula</h2>
        <ol>
          {desk.formula.steps.map((step) => (
            <li key={step}>
              <code>{step}</code>
            </li>
          ))}
        </ol>
        {assess?.steps?.length ? (
          <>
            <h3>This evaluation</h3>
            {assess.steps.map((step) => (
              <div className="row" key={step.id}>
                <dt>{step.id}</dt>
                <dd>
                  {step.value}
                  <span className="muted"> · {step.label}</span>
                </dd>
              </div>
            ))}
          </>
        ) : null}
      </article>

      {example ? (
        <article className="wide" style={{ marginTop: 14 }}>
          <h2>TK letter worked example</h2>
          <p>
            {example.wing_name} vs {example.base_name}. {example.beta_note}. Ticks/handle{" "}
            {example.ticks_per_handle}.
          </p>
          <table className="data-table" style={{ marginTop: 12 }}>
            <thead>
              <tr>
                <th>Step</th>
                <th>Letter (rounded)</th>
                <th>Engine (exact, displayed)</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>multiplier</td>
                <td>{example.published.multiplier}</td>
                <td>{example.engine.relationship_multiplier}</td>
              </tr>
              <tr>
                <td>expected move</td>
                <td>{example.published.expected_move}</td>
                <td>{example.engine.expected_wing_move}</td>
              </tr>
              <tr>
                <td>residual</td>
                <td>{example.published.residual}</td>
                <td>{example.engine.residual}</td>
              </tr>
              <tr>
                <td>rv ticks</td>
                <td>{example.published.rv_ticks}</td>
                <td>{example.engine.rv_ticks}</td>
              </tr>
            </tbody>
          </table>
          <p className="muted">{example.published.note}</p>
        </article>
      ) : null}

      {letter ? (
        <article className="wide" style={{ marginTop: 14 }}>
          <h2>Source letter</h2>
          <div className="row">
            <dt>From</dt>
            <dd>
              {letter.from_name} &lt;{letter.from_email}&gt;
            </dd>
          </div>
          <div className="row">
            <dt>Date</dt>
            <dd>{letter.date}</dd>
          </div>
          <div className="row">
            <dt>To</dt>
            <dd>{letter.to}</dd>
          </div>
          <div className="row">
            <dt>Stored</dt>
            <dd>{letter.path}</dd>
          </div>
          <pre className="letter">{letter.body}</pre>
        </article>
      ) : null}
    </Desk>
  );
}
