export default function Objective({ book = "80" }: { book?: "78" | "80" }) {
  return (
    <section className="objective">
      <p className="kicker" style={{ marginTop: 8 }}>
        9/2 DRE [R] V1 Portfolio Objective
      </p>
      <p className="muted">
        Research memo. Not a calculator. Not Phase 3 policy. Not crates/risk. Candle path ≠ fill.
        {book === "78"
          ? "Forward feed is the derived-four 78/67 prior and the Austin 78/67 fit. Those two N values stay apart."
          : "Forward feed is Choosin Texas (Trade Breakdown, N=936) and Austin (Position Stratification, N=604) only."}
      </p>

      <div className="grid">
        <article className="wide">
          <h2>What we are aiming to do</h2>
          <p>
            Preserve demonstrated positive alpha first. Then choose the optimal amount of directional
            exposure for the current state. Do not blindly force delta to zero.
          </p>
          <pre>{`αP > 0
  ↓
observe Xt from Choosin Texas + Austin
  ↓
estimate remaining alpha
  ↓
measure current risk
  ↓
ΔP → ΔP*(Xt)`}</pre>
          <p>
            First written form: <code>ΔP → 0 | αP &gt; 0</code>. The vertical bar means subject to /
            conditional on. Alpha is not another hedge ratio.
          </p>
          <p>
            Eventual form: <code>ΔP → ΔP*(Xt)</code>. Sometimes nearly delta-neutral is correct.
            Sometimes retaining directional exposure is correct because remaining alpha pays for it.
          </p>
          <p className="muted small">
            Do not eliminate risk blindly; hold risk when compensated by demonstrated alpha, reduce
            risk when deterioration makes that exposure inefficient, and eliminate directional
            exposure when the marginal alpha no longer justifies the marginal risk.
          </p>
        </article>

        <article>
          <h2>Forward feed</h2>
          <pre>{`Choosin Texas  →  TradeBreakdown
Austin         →  PositionStratum
               →  DRE`}</pre>
          <p className="muted small">
            Adapter only. Missing is UNAVAILABLE, never $0. Live feed UNAVAILABLE. DRE does not
            invent Xt, L2, fills, or a third N.
          </p>
        </article>

        <article>
          <h2>Four questions</h2>
          <ol>
            <li>Why do we own this position? Positive demonstrated alpha.</li>
            <li>How much risk are we currently taking? Current exposure, including delta.</li>
            <li>Is that risk still efficient? Marginal alpha versus marginal risk.</li>
            <li>How should we change the position? Hold / hedge / reduce / restructure / exit — research labels only.</li>
          </ol>
        </article>

        <article className="wide">
          <h2>Core principle</h2>
          <p>Risk is not inherently bad. Uncompensated risk is bad.</p>
          <p>
            A perfectly flat book can be inferior to a slightly directional book if the extra risk
            is paid for by statistically demonstrated alpha and the execution assumptions are real.
            The A1 lesson remains: theoretical hedge ≠ executable hedge ≠ economically beneficial
            hedge. <code>Δ↓ ⇏ α↑</code>.
          </p>
        </article>

        <article>
          <h2>Greek stack (not computed)</h2>
          <ul>
            <li>Alpha — remaining E[Π | Xt]</li>
            <li>Delta — directional exposure</li>
            <li>Gamma — acceleration near the stop</li>
            <li>Vega-like — alpha vs state volatility</li>
            <li>Lambda — α deterioration rate −dα/dt</li>
            <li>Hazard — rate of entering the damaging branch</li>
          </ul>
          <p className="muted small">
            Deterioration is not beta. Λα ≠ Δ ≠ Γ ≠ β. Do not invent the derivative.
          </p>
        </article>

        <article>
          <h2>Build order</h2>
          <pre>{`Frozen Alpha Distribution
  → Conditional Alpha Surface
  → Delta Surface
  → State Volatility Surface
  → Tail Hazard Surface
  → THEN Λα`}</pre>
          <p className="muted small">
            Every action still has to pass observed → observable → executable → actual. SSOT:{" "}
            <code>research/dre/PORTFOLIO_OBJECTIVE_V1.md</code>
          </p>
        </article>
      </div>
    </section>
  );
}
