import type { VitalStrategy } from "./api/vitalApi";

type Props = {
  strategy: VitalStrategy | null;
};

function text(value: unknown, fallback = "OBSERVATION_UNAVAILABLE"): string {
  if (value == null || value === "") return fallback;
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return fallback;
}

export default function StrategyFrame({ strategy }: Props) {
  if (!strategy) {
    return (
      <section className="vital-card vital-frame" aria-label="Strategy">
        <p className="ws-kicker">Strategy</p>
        <p className="muted small">Strategy spec unread.</p>
      </section>
    );
  }
  const entry = strategy.entry_rules || {};
  const exit = strategy.exit_rules || {};
  const order = strategy.order_rules || {};
  const prices = strategy.prices || {};
  const constants = strategy.constants || {};
  const mismatch = strategy.spec_status === "SPEC_MISMATCH";
  return (
    <section className="vital-card vital-frame" aria-label="Strategy">
      <p className="ws-kicker">Strategy</p>
      <h2>{text(strategy.kind || strategy.signal, "Spec")}</h2>
      <p className="muted small">{text(strategy.looking_for, strategy.note || "Rules unread")}</p>
      <p className="muted small">
        Observation {text(entry.observation, "YES_BID")} · spec {text(strategy.spec_status, "CONFIRMED")}
      </p>
      {mismatch ? <p className="sa-error">SPEC_MISMATCH — prices do not match the committed spec.</p> : null}
      <p>
        Entry {text(entry.kind || "FIRST 80 / 81", "entry")}{" "}
        {text(prices.entry_cents ?? constants.min_entry_cents ?? entry.entry_cents ?? entry.first_touch_cents)}¢
        {entry.confirm_cents != null ? ` then confirm ${String(entry.confirm_cents)}¢` : ""}
        {entry.band_cents ? ` · band ${String(entry.band_cents)}` : ""}
      </p>
      <p>Limit {text(entry.limit, "observed YES bid")} · {text(entry.order_type || order.entry)}</p>
      <p>
        Exit {text(exit.kind || (exit.lock_cents != null ? "89 lock + VWAP stop" : "REACH"))}{" "}
        {exit.win_cents != null ? `win ${String(exit.win_cents)}¢` : ""}
        {exit.loss_cents != null ? ` / loss ${String(exit.loss_cents)}¢` : ""}
        {exit.lock_cents != null ? `lock ${String(exit.lock_cents)}¢` : ""}
        {exit.stop ? ` · ${String(exit.stop)}` : ""}
      </p>
      <p className="muted small">
        Orders {text(order.entry)} → {text(order.exit)}. Risk {text(order.risk)}. Browser does not submit.
      </p>
      {strategy.candle_path_not_fill ? (
        <p className="muted small">Candle path ≠ fill. YES bid is the observation basis, not last-trade.</p>
      ) : null}
      {strategy.iti ? (
        <p className="muted small">
          ITI {text(strategy.iti.slot_id)} · {text(strategy.iti.folder)} · BASE {text(strategy.iti.BASE_GRADE)} ·
          DEBASE {text(strategy.iti.DEBASE_GRADE)}
        </p>
      ) : null}
    </section>
  );
}
