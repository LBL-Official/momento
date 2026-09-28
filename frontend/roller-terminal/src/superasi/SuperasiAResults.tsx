import SuperasiDeskReport from "./SuperasiDeskReport";
import type { SuperasiBaseInspect } from "./types/superasi";

function pct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "UNAVAILABLE";
  return `${(value * 100).toFixed(2)}%`;
}

function num(value: number | null | undefined, digits = 4): string {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

export default function SuperasiAResults({
  inspect,
  embedded = false,
}: {
  inspect: SuperasiBaseInspect;
  embedded?: boolean;
}) {
  const observed = inspect.observed || {};
  const components = inspect.components || {};
  return (
    <>
      {embedded ? (
        <p className="v2-kicker">SuperASI A — Base</p>
      ) : (
        <header className="v2-view-header">
          <h1 className="v2-page-title">{inspect.strategy_name}</h1>
          <p className="v2-lede">
            BASE_GRADE {inspect.BASE_GRADE || "—"}
            {inspect.borderline ? " · BORDERLINE" : ""} · candle path ≠ fill · LIVE_GRADE = UNAVAILABLE
          </p>
        </header>
      )}

      <section className="ws-level">
        <h2>Observed evidence</h2>
        <p className="muted small">
          Layer = OBSERVED. Every warehouse lab uses the same ROLLER trade: path WIN/LOSS plus
          hold-YES / hold-NO. Official YES does not un-do a path LOSS.
        </p>
        <div className="stax-metric-row">
          <span>Population N</span>
          <strong>{observed.population ?? "—"}</strong>
        </div>
        <div className="stax-metric-row">
          <span>W / L</span>
          <strong>
            {observed.wins ?? "—"} / {observed.losses ?? "—"}
          </strong>
        </div>
        <div className="stax-metric-row">
          <span>Observed win rate</span>
          <strong>{pct(observed.win_rate)}</strong>
        </div>
        <div className="stax-metric-row">
          <span>Wilson CI</span>
          <strong>
            {pct(observed.wilson_lower)} – {pct(observed.wilson_upper)}
          </strong>
        </div>
        <div className="stax-metric-row">
          <span>gross_ev (Roller header)</span>
          <strong>{num(observed.gross_ev)}</strong>
        </div>
      </section>

      <section className="ws-level">
        <h2>Letter grades</h2>
        <p className="muted small">BASE_GRADE = min(components). Composite does not raise the letter.</p>
        <div className="stax-metric-row">
          <span>BASE_GRADE</span>
          <strong>{inspect.BASE_GRADE || "—"}</strong>
        </div>
        {Object.entries(components).map(([name, letter]) => (
          <div className="stax-metric-row" key={name}>
            <span>{name}</span>
            <strong>{letter}</strong>
          </div>
        ))}
        <div className="stax-metric-row">
          <span>Composite (rank only)</span>
          <strong>{num(inspect.composite_score, 2)}</strong>
        </div>
      </section>

      <SuperasiDeskReport desk={inspect.desk} instrument={inspect.instrument} profile={inspect.risk_profile} />

      <section className="ws-level">
        <h2>Validation</h2>
        {(inspect.checks || []).map((check) => (
          <div className="stax-metric-row" key={check.id}>
            <span>{check.id}</span>
            <strong>{check.ok ? "PASS" : "FAIL"}</strong>
          </div>
        ))}
      </section>

      {embedded ? null : (
        <p className="muted small">
          {inspect.files?.abase_filename} saved beside {inspect.files?.roller_filename}
        </p>
      )}
    </>
  );
}
