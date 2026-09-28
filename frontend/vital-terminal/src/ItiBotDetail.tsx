import { useState } from "react";
import BookPane from "./BookPane";
import ExecutionBlotter from "./ExecutionBlotter";
import IntegrationProofPane from "./IntegrationProofPane";
import JournalPane from "./JournalPane";
import KalshiHealth from "./KalshiHealth";
import ParameterSheet from "./ParameterSheet";
import StrategyFrame from "./StrategyFrame";
import {
  activateVitalBot,
  metricText,
  promoteVitalBot,
  type VitalBankroll,
  type VitalBot,
  type VitalExecution,
  type VitalIntegrationProof,
  type VitalKalshi,
  type VitalKalshiHealth,
  type VitalLogs,
  type VitalParameters,
  type VitalRuntime,
  type VitalStatus,
  type VitalStrategy,
} from "./api/vitalApi";
import { activationLabel, bookEnvironment, sportLabel } from "./desk";
import { toneForLifecycle } from "./format";

type Props = {
  bot: VitalBot | null;
  status: VitalStatus | null;
  runtime: VitalRuntime | null;
  logs: VitalLogs | null;
  parameters: VitalParameters | null;
  kalshiHealth: VitalKalshiHealth | null;
  execution: VitalExecution | null;
  bankroll: VitalBankroll | null;
  kalshi: VitalKalshi | null;
  strategy: VitalStrategy | null;
  integration?: VitalIntegrationProof | null;
  error: string | null;
  onError: (message: string | null) => void;
  onRefresh: () => void;
};

const LIVE_CONFIRMATION = "ENABLE_LIVE_TRADING";

export default function ItiBotDetail({
  bot,
  status,
  runtime,
  logs,
  parameters,
  kalshiHealth,
  execution,
  bankroll,
  kalshi,
  strategy,
  integration = null,
  error,
  onError,
  onRefresh,
}: Props) {
  const [busy, setBusy] = useState(false);
  const [last, setLast] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState("");
  const environment = bookEnvironment(bot);
  const production = environment === "PRODUCTION";
  const canRetry = Boolean(bot && !production && !busy);
  const canPromote = Boolean(bot && !production && confirmation === LIVE_CONFIRMATION && !busy);
  const life = bot ? activationLabel(bot) : status?.lifecycle || "OBSERVATION_UNAVAILABLE";

  const onRetry = async () => {
    if (!bot || !canRetry) return;
    setBusy(true);
    onError(null);
    try {
      const body = await activateVitalBot(bot.bot_id, "");
      setLast(String(body.activation || body.status || "DEPLOY_REQUIRED"));
      onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const onPromote = async () => {
    if (!bot || !canPromote) return;
    setBusy(true);
    onError(null);
    try {
      const body = await promoteVitalBot(bot.bot_id, {
        mode: "live",
        live_enabled: true,
        confirmation: LIVE_CONFIRMATION,
      });
      setLast(String(body.activation || body.status || "DEPLOY_REQUIRED"));
      onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const settings = bot?.settings || {};
  const iti = bot?.iti || {};
  const attach = bot?.attach;
  const account = production ? bankroll?.account : bankroll?.demo_account;

  return (
    <div className="sa-page vital-desk">
      <header className="vital-desk-head">
        <div>
          <p className="ws-kicker">
            {sportLabel(bot)} · {environment} · {bot?.bot_id}
          </p>
          <h1 className="v2-page-title">{bot?.name || bot?.bot_id || "Bot"}</h1>
        </div>
        <p className={`vital-tone ${toneForLifecycle(life)}`}>{life}</p>
      </header>
      {error ? <p className="sa-error">{error}</p> : null}
      {last ? <p className="muted small">Last action: {last}</p> : null}
      <IntegrationProofPane proof={integration} variant="detail" />

      <dl className="vital-mini-dl">
        <div>
          <dt>Jump</dt>
          <dd>{bot?.jump_bot_id || "—"}</dd>
        </div>
        <div>
          <dt>Unit</dt>
          <dd>{bot?.aws_runtime_id || metricText(runtime?.service)}</dd>
        </div>
        <div>
          <dt>Attach</dt>
          <dd>{attach?.kalshi_demo?.status || "UNREAD"}</dd>
        </div>
        <div>
          <dt>Slot</dt>
          <dd>{bot?.slot_id || String(iti.slot_id || "—")}</dd>
        </div>
        <div>
          <dt>Entry / win / loss</dt>
          <dd>
            {bot?.engine?.prices?.entry_cents ?? "—"} / {bot?.engine?.prices?.win_cents ?? "—"} /{" "}
            {bot?.engine?.prices?.loss_cents ?? "—"}¢
          </dd>
        </div>
        <div>
          <dt>Size</dt>
          <dd>
            {String(settings.sizing_mode || "FIXED_CENTS")}{" "}
            {settings.amount_cents != null ? `${String(settings.amount_cents)}¢` : ""}
          </dd>
        </div>
      </dl>

      <div className="vital-split">
        <BookPane title={`${environment} book`} environment={environment} account={account} kalshi={kalshi} />
        <StrategyFrame strategy={strategy} />
      </div>
      <ParameterSheet botId={bot?.bot_id} parameters={parameters} onError={onError} onRefresh={onRefresh} />
      <div className="vital-split">
        <KalshiHealth health={kalshiHealth} />
        <JournalPane logs={logs?.logs || []} status={logs?.status} unit={logs?.unit} detail={logs?.detail} />
      </div>
      <ExecutionBlotter execution={execution} />

      {!production ? (
        <section className="vital-card" aria-label="Demo attach">
          <p className="ws-kicker">DEMO attach</p>
          <p className="muted small">Re-observe Demo and restart momento-demo@ if the host allows it. Does not submit.</p>
          <button type="button" className="btn-secondary" onClick={() => void onRetry()} disabled={!canRetry}>
            {busy ? "Working…" : "Retry attach"}
          </button>
        </section>
      ) : null}

      <section className="vital-card" aria-label="Turn on production">
        <p className="ws-kicker">Turn on production</p>
        <p className="muted small">
          Isolated momento-live@ only. Triple gate required. Does not start momento-live.service.
        </p>
        {production ? (
          <p className="muted small">This bot is already on the production book.</p>
        ) : (
          <div className="ws-labs-toolbar">
            <label>
              Confirmation
              <input
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
                placeholder={LIVE_CONFIRMATION}
                autoComplete="off"
              />
            </label>
            <button type="button" className="btn-primary" onClick={() => void onPromote()} disabled={!canPromote}>
              {busy ? "Promoting…" : "Turn on production"}
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
