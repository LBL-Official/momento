import SuperasiDeskReport from "./SuperasiDeskReport";
import type { SuperasiDebaseInspect } from "./types/superasi";

function pct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(2)}%`;
}

function num(value: number | null | undefined, digits = 4): string {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

function rr(value: number | null | undefined, display?: string | null): string {
  if (display) return display;
  if (value == null || Number.isNaN(value)) return "—";
  return `${value.toFixed(2)}:1`;
}

function money(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

export default function SuperasiBResults({ inspect }: { inspect: SuperasiDebaseInspect }) {
  const observed = inspect.observed || {};
  const valuation = inspect.valuation || {};
  const profile = inspect.risk_profile || {};
  const components = inspect.components || {};
  const gate = inspect.instrument_gate || {};
  return (
    <>
      <header className="v2-view-header">
        <h1 className="v2-page-title">{inspect.strategy_name}</h1>
        <p className="v2-lede">
          BASE_GRADE {inspect.BASE_GRADE || "—"} · DEBASE_GRADE {inspect.DEBASE_GRADE || "—"}
          {inspect.borderline ? " · BORDERLINE" : ""} · candle path ≠ fill · LIVE_GRADE = UNAVAILABLE
        </p>
      </header>

      <SuperasiDeskReport
        desk={inspect.desk}
        instrument={inspect.instrument}
        profile={inspect.risk_profile}
        deskLayerNote="Layer = THEORETICAL. This Roller's entry/exit + IQR 1 (Q1) as the mean. Worst-form desk. Not DEBASE_GRADE."
        pCaption={`p used for Trade EV / Weekly EV = IQR 1 (worst-form mean) ${pct(inspect.desk?.p_used ?? inspect.p_working)}.`}
      />

      <section className="ws-level">
        <h2>Conservative evidence</h2>
        <p className="muted small">
          Working p = IQR 1 (Q1) of decided W/L, used as the mean. Same books as ROLLER: path WIN/LOSS, plus
          hold-YES / hold-NO only when the compiled win exit is HOLD. Header EV stays plan-level.
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
          <span>p_working (IQR 1)</span>
          <strong>{pct(inspect.p_working)}</strong>
        </div>
        <div className="stax-metric-row">
          <span>Roller p_BE</span>
          <strong>{pct(inspect.p_be_roller)}</strong>
        </div>
        <div className="stax-metric-row">
          <span>gross_ev / ev_debase</span>
          <strong>
            {num(inspect.gross_ev)} / {num(inspect.ev_debase)}
          </strong>
        </div>
        <div className="stax-metric-row">
          <span>R:R</span>
          <strong>{rr(inspect.risk_reward, inspect.risk_reward_display)}</strong>
        </div>
        {inspect.risk_reward_trade_mean != null &&
        inspect.risk_reward_plan != null &&
        Math.abs(inspect.risk_reward_trade_mean - inspect.risk_reward_plan) > 1e-6 ? (
          <div className="stax-metric-row">
            <span>R:R plan / ratio of means</span>
            <strong>
              {rr(inspect.risk_reward_plan)}
              {inspect.risk_reward_methods_disagree && inspect.risk_reward_ratio_of_means != null
                ? ` · ${rr(inspect.risk_reward_ratio_of_means)}`
                : ""}
            </strong>
          </div>
        ) : null}
      </section>

      <section className="ws-level">
        <h2>DeGrading</h2>
        <p className="muted small">Same grade_config_v1 bands. DEBASE_GRADE cannot exceed BASE_GRADE.</p>
        <div className="stax-metric-row">
          <span>BASE_GRADE</span>
          <strong>{inspect.BASE_GRADE || "—"}</strong>
        </div>
        <div className="stax-metric-row">
          <span>DEBASE_GRADE</span>
          <strong>{inspect.DEBASE_GRADE || "—"}</strong>
        </div>
        <div className="stax-metric-row">
          <span>Degradation</span>
          <strong>
            {inspect.capped_to_base ? `letter dropped (${inspect.DEBASE_GRADE_uncapped || "—"} → ${inspect.DEBASE_GRADE || "—"})` : "0"}
          </strong>
        </div>
        <div className="stax-metric-row">
          <span>Bottleneck</span>
          <strong>{inspect.bottleneck || "—"}</strong>
        </div>
        <div className="stax-metric-row">
          <span>To raise</span>
          <strong>{inspect.raise_requires || "—"}</strong>
        </div>
        {Object.entries(components).map(([name, letter]) => (
          <div className="stax-metric-row" key={name}>
            <span>{name}</span>
            <strong>{letter}</strong>
          </div>
        ))}
      </section>

      <section className="ws-level">
        <h2>DeComposition (IQR 1)</h2>
        <p className="muted small">Worst-form layer at IQR 1 as the mean. Same Theoretical desk as the panel above.</p>
        <div className="stax-metric-row">
          <span>R_w / R_l</span>
          <strong>
            {pct(valuation.R_w)} / {pct(valuation.R_l)}
          </strong>
        </div>
        <div className="stax-metric-row">
          <span>Weekly EV</span>
          <strong>{pct(valuation.weekly_ev)}</strong>
        </div>
        <div className="stax-metric-row">
          <span>Compounded 20-week</span>
          <strong>{pct(valuation.compounded_20_week)}</strong>
        </div>
        {valuation.weekly_table?.length ? (
          <div>
            <p className="muted small">Weekly win scenarios at p_working (this strategy’s R_w / R_l).</p>
            <ul className="sa-chart-list" aria-label="Weekly scenario probabilities">
              {valuation.weekly_table.map((row) => (
                <li className="sa-chart-row" key={`week-${row.wins ?? ""}`}>
                  <span>{row.wins ?? "—"}/10</span>
                  <span className="sa-chart-track">
                    <span className="sa-chart-fill" style={{ width: `${Math.max(0, Math.min(100, (row.probability || 0) * 100))}%` }} />
                  </span>
                  <strong>{pct(row.probability)}</strong>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {valuation.sensitivity?.length ? (
          <div>
            <p className="muted small">Sensitivity: p only. Roller reward/risk stay fixed.</p>
            <ul className="sa-chart-list" aria-label="Sensitivity weekly EV">
              {valuation.sensitivity.map((row) => (
                <li className="sa-chart-row" key={`sens-${row.p ?? ""}`}>
                  <span>{pct(row.p)}</span>
                  <span className="sa-chart-track">
                    <span
                      className="sa-chart-fill"
                      style={{
                        width: `${Math.max(0, Math.min(100, Math.abs(row.weekly_ev || 0) * 400))}%`,
                      }}
                    />
                  </span>
                  <strong>{pct(row.weekly_ev)}</strong>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </section>

      <section className="ws-level">
        <h2>A+ instrument gate</h2>
        <p className="muted small">Valuation gate on IQR-1 Monte Carlo. Not DEBASE_GRADE.</p>
        <div className="stax-metric-row">
          <span>Desk capital</span>
          <strong>
            {money(inspect.desk_settings?.bankroll_dollars ?? profile.bankroll_dollars)} ·{" "}
            {pct((inspect.desk_settings?.allocation_pct ?? profile.allocation_pct ?? 0) / 100)}
          </strong>
        </div>
        <div className="stax-metric-row">
          <span>A+ instrument gate</span>
          <strong>{gate.value || "—"}</strong>
        </div>
      </section>

      <p className="muted small">
        {inspect.files?.debase_filename} saved beside {inspect.files?.roller_filename} and {inspect.files?.abase_filename}
      </p>
    </>
  );
}
