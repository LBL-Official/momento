import { useDeskSettings } from "../settings/useDeskSettings";

export default function SettingsView() {
  const {
    bankrollDollars,
    setBankrollDollars,
    allocationPct,
    setAllocationPct,
    saving,
    error,
    saved,
    save,
  } = useDeskSettings();
  const allocationDollars = (bankrollDollars * allocationPct) / 100;
  const floor = saved?.floor_dollars ?? bankrollDollars * 0.75;
  const target = saved?.target_dollars ?? bankrollDollars * 1.5;

  return (
    <div className="v2-docs-article research-object">
      <h1 className="v2-page-title">Settings</h1>
      <p className="v2-lede">
        Bankroll and risk per trade apply to new Results sizing, Risk, SuperASI A, and SuperASI B until you change
        them. Existing Labs and SuperASI folders keep the numbers they were run with.
      </p>
      <section className="ws-level">
        <p className="v2-kicker">Desk capital</p>
        <div className="ws-capital-inputs">
          <label>
            Allocated bankroll $
            <input
              type="number"
              min={1}
              step={1}
              value={bankrollDollars}
              onChange={(e) => setBankrollDollars(Number(e.target.value) || 0)}
            />
          </label>
          <label>
            Risk per trade %
            <input
              type="number"
              min={0.01}
              max={100}
              step={0.01}
              value={allocationPct}
              onChange={(e) => setAllocationPct(Number(e.target.value) || 0)}
            />
          </label>
        </div>
        <p className="muted small">
          ${allocationDollars.toLocaleString(undefined, { maximumFractionDigits: 2 })} per trade · floor $
          {floor.toLocaleString(undefined, { maximumFractionDigits: 2 })} (0.75×) · target $
          {target.toLocaleString(undefined, { maximumFractionDigits: 2 })} (1.50×)
        </p>
        <button type="button" className="btn-primary" disabled={saving} onClick={() => void save()}>
          {saving ? "Saving…" : "Save settings"}
        </button>
        {error ? <p className="muted small">{error}</p> : null}
        {saved?.updated_at ? <p className="muted small">Saved {saved.updated_at}</p> : null}
      </section>
      <p className="muted small">
        Candle-path research is not a fill. These numbers size hypothetical allocation. They do not arm live trading
        and they do not bypass the Risk Decision Engine.
      </p>
    </div>
  );
}
