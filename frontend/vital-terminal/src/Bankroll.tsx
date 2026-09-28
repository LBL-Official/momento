import { useState } from "react";
import {
  metricText,
  moneyText,
  observeVitalKalshi,
  postVitalAllocation,
  postVitalLimits,
  type VitalBankroll,
  type VitalBankrollBot,
  type VitalMetric,
} from "./api/vitalApi";

type Props = {
  bankroll: VitalBankroll | null;
  error: string | null;
  onError: (message: string | null) => void;
  onRefresh: () => void;
};

const MODES = [
  { id: "FIXED_CENTS", label: "Fixed cents" },
  { id: "PCT_CURRENT", label: "% of current Kalshi book" },
  { id: "PCT_WEEKLY", label: "% of weekly snap" },
] as const;

function statusOf(metric: VitalMetric | undefined | null): string {
  return metric?.status || "OBSERVATION_UNAVAILABLE";
}

function unitCents(metric: VitalMetric | undefined | null): number | null {
  if (!metric || metric.status !== "CONFIRMED" || !metric.value || typeof metric.value !== "object") {
    return null;
  }
  const unit = (metric.value as { unit_cents?: unknown }).unit_cents;
  return typeof unit === "number" && Number.isFinite(unit) ? unit : null;
}

function moneyFromCents(cents: number | null, fallback: string): string {
  if (cents == null) return fallback;
  return `$${(Math.abs(cents) / 100).toFixed(2)}`;
}

function desiredObject(row: VitalBankrollBot): {
  mode?: string;
  amount_cents?: number;
  allocation_bps?: number;
} {
  const raw = row.allocation?.desired?.value;
  return raw && typeof raw === "object" ? (raw as { mode?: string; amount_cents?: number; allocation_bps?: number }) : {};
}

function limitsObject(row: VitalBankrollBot): Record<string, number | null> {
  const raw = row.limits?.desired?.value;
  return raw && typeof raw === "object" ? (raw as Record<string, number | null>) : {};
}

export default function Bankroll({ bankroll, error, onError, onRefresh }: Props) {
  const [observeBusy, setObserveBusy] = useState<string | null>(null);
  const [editId, setEditId] = useState<string | null>(null);
  const [mode, setMode] = useState<(typeof MODES)[number]["id"]>("FIXED_CENTS");
  const [amount, setAmount] = useState("100");
  const [bps, setBps] = useState("1250");
  const [entries, setEntries] = useState("");
  const [wins, setWins] = useState("");
  const [losses, setLosses] = useState("");
  const [winCents, setWinCents] = useState("");
  const [lossCents, setLossCents] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);

  const account = bankroll?.account;
  const demoAccount = bankroll?.demo_account;
  const demoReport = bankroll?.demo_report;
  const bots = bankroll?.bots || [];
  const productionBots = bots.filter((row) => (row.environment || "PRODUCTION") === "PRODUCTION");
  const demoBots = bots.filter((row) => row.environment === "DEMO");

  const onObserve = async (environment: "DEMO" | "PRODUCTION") => {
    const botId =
      environment === "DEMO"
        ? demoBots[0]?.bot_id || "mlb-001"
        : productionBots[0]?.bot_id || "mlb-001";
    setObserveBusy(environment);
    onError(null);
    try {
      await observeVitalKalshi(botId, environment);
      onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    } finally {
      setObserveBusy(null);
    }
  };

  const openEdit = (row: VitalBankrollBot) => {
    const desired = desiredObject(row);
    const limits = limitsObject(row);
    const nextMode = (desired.mode as (typeof MODES)[number]["id"] | undefined) || "FIXED_CENTS";
    setEditId(row.bot_id);
    setMode(MODES.some((item) => item.id === nextMode) ? nextMode : "FIXED_CENTS");
    setAmount(String(desired.amount_cents || (row.environment === "DEMO" ? 100 : 331)));
    setBps(String(desired.allocation_bps || 1250));
    setEntries(limits.max_daily_entries ? String(limits.max_daily_entries) : "");
    setWins(limits.max_daily_wins ? String(limits.max_daily_wins) : "");
    setLosses(limits.max_daily_losses ? String(limits.max_daily_losses) : "");
    setWinCents(limits.max_daily_win_cents ? String(limits.max_daily_win_cents) : "");
    setLossCents(limits.max_daily_loss_cents ? String(limits.max_daily_loss_cents) : "");
    setConfirmation("");
  };

  const onSave = async (botId: string) => {
    setBusy(true);
    onError(null);
    try {
      const confirm = confirmation.trim();
      await postVitalAllocation(botId, {
        mode,
        amount_cents: mode === "FIXED_CENTS" ? Number(amount) : undefined,
        allocation_bps: mode === "FIXED_CENTS" ? undefined : Number(bps),
        confirmation: confirm || undefined,
      });
      const limits: Record<string, number | undefined> = {};
      if (entries) limits.max_daily_entries = Number(entries);
      if (wins) limits.max_daily_wins = Number(wins);
      if (losses) limits.max_daily_losses = Number(losses);
      if (winCents) limits.max_daily_win_cents = Number(winCents);
      if (lossCents) limits.max_daily_loss_cents = Number(lossCents);
      await postVitalLimits(botId, { ...limits, confirmation: confirm || undefined });
      setEditId(null);
      onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="sa-page">
      <header className="stax-count-head">
        <p className="ws-kicker">Bankroll</p>
        <h1 className="v2-page-title">Two Kalshi books</h1>
        <p className="v2-lede">
          Production cash and demo cash are different books. Desired size is not live size. Browser
          does not submit orders. Demo observe uses the official Kalshi demo Trade API, not
          production.
        </p>
      </header>

      {error ? <p className="sa-error">{error}</p> : null}

      <div className="vital-books">
        <section className="vital-book" aria-label="Production Kalshi account">
          <p className="ws-kicker">Production</p>
          <p className="vital-book-hero">{moneyText(account?.top_level_cents)}</p>
          <dl className="ws-universe-dl">
            <div>
              <dt>Day</dt>
              <dd>{moneyText(account?.day_delta_cents, true)}</dd>
            </div>
            <div>
              <dt>Week</dt>
              <dd>{moneyText(account?.week_delta_cents, true)}</dd>
            </div>
            <div>
              <dt>Sports shard 3</dt>
              <dd>{moneyText(account?.mlb_shard_cents)}</dd>
            </div>
            <div>
              <dt>Factory snap</dt>
              <dd>{moneyText(account?.factory_bankroll_cents)}</dd>
            </div>
            <div>
              <dt>Factory unit</dt>
              <dd>{moneyText(account?.factory_unit_cents)}</dd>
            </div>
            <div>
              <dt>Source</dt>
              <dd>{metricText(account?.source)}</dd>
            </div>
          </dl>
          <div className="ws-labs-toolbar">
            <button
              type="button"
              className="btn-secondary"
              disabled={observeBusy != null}
              onClick={() => void onObserve("PRODUCTION")}
            >
              {observeBusy === "PRODUCTION" ? "Observing…" : "Observe production"}
            </button>
          </div>
        </section>

        <section className="vital-book" aria-label="Demo Kalshi account">
          <p className="ws-kicker">Demo</p>
          <p className="vital-book-hero">{moneyText(demoAccount?.top_level_cents)}</p>
          <dl className="ws-universe-dl">
            <div>
              <dt>Day</dt>
              <dd>{moneyText(demoAccount?.day_delta_cents, true)}</dd>
            </div>
            <div>
              <dt>Week</dt>
              <dd>{moneyText(demoAccount?.week_delta_cents, true)}</dd>
            </div>
            <div>
              <dt>Sports shard</dt>
              <dd>{moneyText(demoAccount?.mlb_shard_cents)}</dd>
            </div>
            <div>
              <dt>Catch-all shard</dt>
              <dd>{moneyText(demoAccount?.catch_all_shard_cents)}</dd>
            </div>
            <div>
              <dt>Origin</dt>
              <dd>{moneyText(demoAccount?.origin_cents)}</dd>
            </div>
            <div>
              <dt>Account P&L</dt>
              <dd>{moneyText(demoAccount?.origin_pnl_cents, true)}</dd>
            </div>
            <div>
              <dt>Default unit</dt>
              <dd>{moneyText(demoAccount?.default_unit_cents)}</dd>
            </div>
            <div>
              <dt>Source</dt>
              <dd>
                {metricText(demoAccount?.source)}
                {demoAccount?.source?.detail ? (
                  <span className="muted small"> {demoAccount.source.detail}</span>
                ) : null}
              </dd>
            </div>
          </dl>
          <div className="ws-labs-toolbar">
            <button
              type="button"
              className="btn-secondary"
              disabled={observeBusy != null}
              onClick={() => void onObserve("DEMO")}
            >
              {observeBusy === "DEMO" ? "Observing…" : "Observe demo"}
            </button>
          </div>
        </section>
      </div>

      <section className="vital-book" aria-label="Demo account report">
        <p className="ws-kicker">Demo report</p>
        <h2 className="stax-count">Fills and P&L</h2>
        <p className="muted small">
          Account P&L is cash minus demo origin. Fill-result sums are a different fact. Live EV and
          Sharpe stay UNAVAILABLE.
        </p>
        <dl className="ws-universe-dl">
          <div>
            <dt>Account P&L</dt>
            <dd>{moneyText(demoReport?.origin_pnl_cents, true)}</dd>
          </div>
          <div>
            <dt>Wins</dt>
            <dd>{metricText(demoReport?.wins)}</dd>
          </div>
          <div>
            <dt>Losses</dt>
            <dd>{metricText(demoReport?.losses)}</dd>
          </div>
          <div>
            <dt>Trades</dt>
            <dd>{metricText(demoReport?.trade_n)}</dd>
          </div>
          <div>
            <dt>Fill-result</dt>
            <dd>{moneyText(demoReport?.fill_result_sum_cents, true)}</dd>
          </div>
          <div>
            <dt>Fill day</dt>
            <dd>{moneyText(demoReport?.day_fill_result_cents, true)}</dd>
          </div>
          <div>
            <dt>Fill week</dt>
            <dd>{moneyText(demoReport?.week_fill_result_cents, true)}</dd>
          </div>
          <div>
            <dt>Last fill</dt>
            <dd>{metricText(demoReport?.last_trade)}</dd>
          </div>
        </dl>
      </section>

      <BotTable
        title="Production bots"
        note="MLB 001 observed unit stays $6.25 until the host confirms a new policy."
        rows={productionBots}
        onEdit={openEdit}
      />
      <BotTable
        title="Demo bots"
        note="Demo default is $1.00 per trade. Next demo.toml deploy picks up FIXED_CENTS 100."
        rows={demoBots}
        onEdit={openEdit}
      />

      {editId ? (
        <section className="vital-book" aria-label="Edit allocation">
          <p className="ws-kicker">Edit {editId}</p>
          <p className="muted small">Desired stored is not the live unit. Never use ENABLE_LIVE_TRADING here.</p>
          <div className="vital-edit-grid">
            <label className="muted small">
              Mode
              <select value={mode} onChange={(event) => setMode(event.target.value as (typeof MODES)[number]["id"])}>
                {MODES.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            {mode === "FIXED_CENTS" ? (
              <label className="muted small">
                Amount (cents)
                <input value={amount} onChange={(event) => setAmount(event.target.value)} inputMode="numeric" />
              </label>
            ) : (
              <label className="muted small">
                Allocation (bps)
                <input value={bps} onChange={(event) => setBps(event.target.value)} inputMode="numeric" />
              </label>
            )}
            <label className="muted small">
              Max entries today
              <input value={entries} onChange={(event) => setEntries(event.target.value)} inputMode="numeric" />
            </label>
            <label className="muted small">
              Max wins today (count)
              <input value={wins} onChange={(event) => setWins(event.target.value)} inputMode="numeric" />
            </label>
            <label className="muted small">
              Max losses today (count)
              <input value={losses} onChange={(event) => setLosses(event.target.value)} inputMode="numeric" />
            </label>
            <label className="muted small">
              Max win today (cents)
              <input value={winCents} onChange={(event) => setWinCents(event.target.value)} inputMode="numeric" />
            </label>
            <label className="muted small">
              Max loss today (cents)
              <input value={lossCents} onChange={(event) => setLossCents(event.target.value)} inputMode="numeric" />
            </label>
            <label className="muted small">
              Confirmation (optional apply token)
              <input value={confirmation} onChange={(event) => setConfirmation(event.target.value)} />
            </label>
          </div>
          <div className="ws-labs-toolbar">
            <button type="button" className="btn-primary" disabled={busy} onClick={() => void onSave(editId)}>
              Save desired
            </button>
            <button type="button" className="btn-secondary" disabled={busy} onClick={() => setEditId(null)}>
              Cancel
            </button>
          </div>
        </section>
      ) : null}
    </div>
  );
}

function limitsLabel(row: VitalBankrollBot): string {
  const remaining = row.limits?.remaining;
  if (remaining?.status === "CONFIRMED") return metricText(remaining);
  const desired = limitsObject(row);
  const hasCap = Object.values(desired).some((value) => typeof value === "number" && value > 0);
  return hasCap ? "session unread" : "none";
}

function BotTable({
  title,
  note,
  rows,
  onEdit,
}: {
  title: string;
  note: string;
  rows: VitalBankrollBot[];
  onEdit: (row: VitalBankrollBot) => void;
}) {
  return (
    <section aria-label={title}>
      <header className="stax-count-head">
        <p className="ws-kicker">{title}</p>
        <h2 className="stax-count">
          {rows.length} {rows.length === 1 ? "bot" : "bots"}
        </h2>
        <p className="muted small">{note}</p>
      </header>
      <div className="stax-table-wrap">
        <table className="stax-table vital-bankroll-table">
          <thead>
            <tr>
              <th>Bot</th>
              <th>Desired</th>
              <th>Observed</th>
              <th>Confirmed</th>
              <th>Limits</th>
              <th>Apply</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={7} className="muted small">
                  OBSERVATION_UNAVAILABLE
                </td>
              </tr>
            ) : (
              rows.map((row) => {
                const desired = unitCents(row.allocation?.desired);
                const confirmed = unitCents(row.allocation?.confirmed);
                return (
                  <tr key={row.bot_id}>
                    <td>{row.name || row.bot_id}</td>
                    <td>{moneyFromCents(desired, statusOf(row.allocation?.desired))}</td>
                    <td>{moneyFromCents(unitCents(row.allocation?.observed), statusOf(row.allocation?.observed))}</td>
                    <td>{moneyFromCents(confirmed, statusOf(row.allocation?.confirmed))}</td>
                    <td>{limitsLabel(row)}</td>
                    <td>{row.allocation?.apply_status || "APPLY_REQUIRED"}</td>
                    <td>
                      <button type="button" className="btn-secondary" onClick={() => onEdit(row)}>
                        Edit
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
