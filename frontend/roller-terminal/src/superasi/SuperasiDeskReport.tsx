import type { SuperasiBaseInspect } from "./types/superasi";

function pct(value: number | null | undefined, status?: string): string {
  if (value == null || Number.isNaN(value)) {
    return status === "DATA_REQUIRED" ? "DATA_REQUIRED" : "UNAVAILABLE";
  }
  return `${(value * 100).toFixed(2)}%`;
}

function num(value: number | null | undefined, digits = 4, status?: string): string {
  if (value == null || Number.isNaN(value)) {
    return status === "DATA_REQUIRED" ? "DATA_REQUIRED" : "UNAVAILABLE";
  }
  return value.toFixed(digits);
}

type Props = {
  desk?: SuperasiBaseInspect["desk"];
  instrument?: SuperasiBaseInspect["instrument"];
  profile?: SuperasiBaseInspect["risk_profile"];
  pCaption?: string;
  deskLayerNote?: string;
};

export default function SuperasiDeskReport({ desk, instrument, profile, pCaption, deskLayerNote }: Props) {
  const panel = desk || {};
  const mc = profile || {};
  const unavailable = panel.status === "DATA_REQUIRED" || mc.status === "DATA_REQUIRED";
  return (
    <>
      <section className="ws-level">
        <h2>Theoretical desk</h2>
        <p className="muted small">
          {deskLayerNote ||
            "Layer = THEORETICAL. This Roller's entry/exit + observed win rate. Not BASE_GRADE."}
        </p>
        <div className="stax-metric-row">
          <span>Break-even p</span>
          <strong>{pct(panel.break_even_probability, panel.status)}</strong>
        </div>
        <div className="stax-metric-row">
          <span>Trade EV</span>
          <strong>{pct(panel.trade_ev, panel.status)}</strong>
        </div>
        <div className="stax-metric-row">
          <span>Weekly EV</span>
          <strong>{pct(panel.weekly_ev, panel.status)}</strong>
        </div>
        <div className="stax-metric-row">
          <span>Required p for 1% week</span>
          <strong>{pct(panel.required_win_probability, panel.status)}</strong>
        </div>
        {panel.p_used != null ? (
          <p className="muted small">
            {pCaption || `p used for Trade EV / Weekly EV = observed win rate ${pct(panel.p_used)}.`}
          </p>
        ) : null}
        {instrument ? (
          <p className="muted small">
            Instrument +20/−40 comparison: break-even {pct(instrument.break_even_probability)} · trade EV{" "}
            {pct(instrument.trade_ev)} · weekly EV {pct(instrument.weekly_ev)} · required p{" "}
            {pct(instrument.required_win_probability)}.
          </p>
        ) : null}
      </section>

      <section className="ws-level">
        <h2>Monte Carlo risk profile</h2>
        <p className="muted small">{mc.note || "This Roller's R:R + observed win rate. Not BASE_GRADE."}</p>
        <div className="stax-metric-row">
          <span>Horizon / paths</span>
          <strong>
            {mc.weeks ?? "—"}w · {mc.paths ?? "—"}
          </strong>
        </div>
        <div className="stax-metric-row">
          <span>P(min bankroll ≤ $15k)</span>
          <strong>{pct(mc.P_min_bankroll_le_floor, unavailable ? panel.status || mc.status : mc.status)}</strong>
        </div>
        <div className="stax-metric-row">
          <span>P(final ≥ $30k)</span>
          <strong>{pct(mc.P_final_ge_target, mc.status)}</strong>
        </div>
        <div className="stax-metric-row">
          <span>Mean terminal bankroll</span>
          <strong>{num(mc.mean_terminal_bankroll, 2, mc.status)}</strong>
        </div>
      </section>
    </>
  );
}
