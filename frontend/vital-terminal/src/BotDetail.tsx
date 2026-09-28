import { useState } from "react";
import BookPane from "./BookPane";
import ExecutionBlotter from "./ExecutionBlotter";
import IntegrationProofPane from "./IntegrationProofPane";
import JournalPane from "./JournalPane";
import KalshiHealth from "./KalshiHealth";
import LiveServicePane from "./LiveServicePane";
import ParameterSheet from "./ParameterSheet";
import StrategyFrame from "./StrategyFrame";
import type {
  VitalBankroll,
  VitalBot,
  VitalCommand,
  VitalControls,
  VitalDiagnose,
  VitalExecution,
  VitalIntegrationProof,
  VitalKalshi,
  VitalKalshiHealth,
  VitalLogs,
  VitalParameters,
  VitalRuntime,
  VitalStatus,
  VitalStrategy,
} from "./api/vitalApi";
import { observeVitalHost, observeVitalKalshi, postVitalCommand, startVitalIfArmed } from "./api/vitalApi";
import { toneForLifecycle } from "./format";

type Props = {
  bot: VitalBot | null;
  status: VitalStatus | null;
  runtime: VitalRuntime | null;
  logs: VitalLogs | null;
  parameters: VitalParameters | null;
  kalshiHealth: VitalKalshiHealth | null;
  events: Record<string, unknown>[];
  orders: Record<string, unknown> | null;
  positions: Record<string, unknown> | null;
  execution: VitalExecution | null;
  bankroll: VitalBankroll | null;
  kalshi: VitalKalshi | null;
  strategy: VitalStrategy | null;
  diagnose: VitalDiagnose | null;
  controls: VitalControls | null;
  integration: VitalIntegrationProof | null;
  error: string | null;
  onError: (message: string | null) => void;
  onRefresh: () => void;
};

export default function BotDetail({
  bot,
  status,
  runtime,
  logs,
  parameters,
  kalshiHealth,
  events,
  orders,
  positions,
  execution,
  bankroll,
  kalshi,
  strategy,
  diagnose,
  controls,
  integration,
  error,
  onError,
  onRefresh,
}: Props) {
  const [confirmation, setConfirmation] = useState("");
  const [last, setLast] = useState<VitalCommand | null>(null);
  const [busy, setBusy] = useState(false);
  const [observeBusy, setObserveBusy] = useState(false);
  const [hostBusy, setHostBusy] = useState(false);
  const [armBusy, setArmBusy] = useState(false);
  const lifecycle = status?.lifecycle || "OBSERVATION_UNAVAILABLE";

  const onRefreshHost = async () => {
    if (!bot) return;
    setHostBusy(true);
    onError(null);
    try {
      await observeVitalHost(bot.bot_id);
      onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    } finally {
      setHostBusy(false);
    }
  };

  const onObserveKalshi = async () => {
    if (!bot) return;
    setObserveBusy(true);
    onError(null);
    try {
      await observeVitalKalshi(bot.bot_id);
      onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    } finally {
      setObserveBusy(false);
    }
  };

  const onStartIfArmed = async () => {
    if (!bot) return;
    setArmBusy(true);
    onError(null);
    try {
      const body = await startVitalIfArmed(bot.bot_id, confirmation);
      setLast({
        command_id: "start-if-armed",
        action: "start",
        command_status: body.command_status || "REJECTED",
        detail: body.detail,
        http_200_not_running: true,
      });
      onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    } finally {
      setArmBusy(false);
    }
  };

  const onCommand = async (action: "deploy" | "start" | "stop" | "restart" | "kill") => {
    if (!bot) return;
    setBusy(true);
    onError(null);
    try {
      const body = await postVitalCommand(bot.bot_id, action, confirmation);
      setLast(body);
      onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="sa-page vital-desk">
      <header className="vital-desk-head">
        <div>
          <p className="ws-kicker">MLB 001 factory</p>
          <h1 className="v2-page-title">{bot?.name || "MLB 001"}</h1>
        </div>
        <p className={`vital-tone ${toneForLifecycle(lifecycle)}`}>{lifecycle}</p>
      </header>
      {error ? <p className="sa-error">{error}</p> : null}

      <LiveServicePane
        variant="detail"
        botId={bot?.bot_id}
        runtime={runtime}
        controls={controls}
        diagnose={diagnose}
        confirmation={confirmation}
        last={last}
        busy={busy}
        hostBusy={hostBusy}
        onConfirmation={setConfirmation}
        onCommand={(action) => void onCommand(action)}
        onRefreshHost={() => void onRefreshHost()}
      />

      <IntegrationProofPane proof={integration} variant="detail" />

      <div className="vital-split">
        <BookPane title="Production" environment="PRODUCTION" account={bankroll?.account} kalshi={kalshi} />
        <StrategyFrame strategy={strategy} />
      </div>
      <ParameterSheet
        botId={bot?.bot_id}
        parameters={parameters || diagnose?.parameters || null}
        onError={onError}
        onRefresh={onRefresh}
      />
      <div className="vital-split">
        <KalshiHealth health={kalshiHealth} />
        <section className="vital-card" aria-label="Diagnose">
          <p className="ws-kicker">Diagnose</p>
          <p className="muted small">
            Host {diagnose?.host_confirmed ? "CONFIRMED" : "UNREAD"} · service{" "}
            {diagnose?.service_active ? "active" : diagnose?.host_confirmed ? "inactive" : "unread"} · live.toml{" "}
            {diagnose?.live_toml?.armed ? "armed" : diagnose?.live_toml?.reason || "unread"}
          </p>
          <p className="muted small">{diagnose?.note || "Start only if already armed and down."}</p>
          <div className="ws-labs-toolbar">
            <button
              type="button"
              className="btn-primary"
              disabled={armBusy || !bot || diagnose?.can_start_if_armed !== true}
              onClick={() => void onStartIfArmed()}
            >
              {armBusy ? "Starting…" : "Start if armed"}
            </button>
            <button type="button" className="btn-secondary" disabled={observeBusy || !bot} onClick={() => void onObserveKalshi()}>
              {observeBusy ? "Observing…" : "Observe Kalshi"}
            </button>
          </div>
        </section>
      </div>

      <p className="muted small">
        Orders {String((orders as { orders?: { status?: string } } | null)?.orders?.status || "UNREAD")} · book
        positions {String((positions as { positions?: { status?: string } } | null)?.positions?.status || "UNREAD")}
      </p>

      <ExecutionBlotter execution={execution} />

      <JournalPane logs={logs?.logs || []} status={logs?.status} unit={logs?.unit} detail={logs?.detail} />

      <section>
        <p className="ws-kicker">Events</p>
        <ul className="vital-journal">
          {events.slice(-20).map((row, i) => (
            <li key={i} className="muted small">
              {String(row.ts || "")} {String(row.kind || "")} {String(row.status || row.command_status || "")}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
