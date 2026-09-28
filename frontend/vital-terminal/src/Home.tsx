import BookPane from "./BookPane";
import BotBlotter from "./BotBlotter";
import IntegrationProofPane from "./IntegrationProofPane";
import LiveServicePane from "./LiveServicePane";
import StrategyFrame from "./StrategyFrame";
import type {
  VitalBankroll,
  VitalBot,
  VitalControls,
  VitalHealth,
  VitalIntegrationProof,
  VitalKalshi,
  VitalRuntime,
  VitalStatus,
  VitalStrategy,
} from "./api/vitalApi";
import { metricText, moneyText } from "./api/vitalApi";
import { sortBots } from "./desk";
import { toneForLifecycle } from "./format";

type Props = {
  health: VitalHealth | null;
  status: VitalStatus | null;
  runtime: VitalRuntime | null;
  bots: VitalBot[];
  bankroll: VitalBankroll | null;
  kalshi: VitalKalshi | null;
  strategy: VitalStrategy | null;
  error: string | null;
  observing: boolean;
  hostBusy?: boolean;
  builtAt?: string | null;
  controls?: VitalControls | null;
  integration?: VitalIntegrationProof | null;
  onOpenBots: () => void;
  onOpenDetail: (botId?: string) => void;
  onRefreshHost?: () => void;
};

export default function Home({
  health,
  status,
  runtime,
  bots,
  bankroll,
  kalshi,
  strategy,
  error,
  observing,
  hostBusy = false,
  builtAt,
  controls,
  integration,
  onOpenBots,
  onOpenDetail,
  onRefreshHost,
}: Props) {
  const lifecycle = status?.lifecycle || "OBSERVATION_UNAVAILABLE";
  const ranked = sortBots(bots);
  return (
    <div className="sa-page vital-desk">
      <header className="vital-desk-head">
        <div>
          <p className="ws-kicker">Desk</p>
          <h1 className="v2-page-title">Execution</h1>
        </div>
        <p className="muted small">
          {observing ? "Observing Kalshi…" : builtAt ? `Read ${builtAt}` : "Desk read"} · HTTP 200 ≠ RUNNING ·
          missing ≠ $0
        </p>
      </header>
      {error ? <p className="sa-error">{error}</p> : null}

      <LiveServicePane
        variant="desk"
        botId="mlb-001"
        runtime={runtime}
        controls={controls}
        hostBusy={hostBusy}
        onRefreshHost={onRefreshHost}
        onOpenDetail={() => onOpenDetail("mlb-001")}
      />

      <IntegrationProofPane proof={integration || null} variant="desk" />

      <div className="vital-hero">
        <div className="vital-card">
          <dt>MLB 001</dt>
          <dd>
            <span className={`vital-tone ${toneForLifecycle(lifecycle)}`}>{lifecycle}</span>
          </dd>
          <p className="muted small">
            Health {status?.health || "UNKNOWN"} · host {metricText(runtime?.host)} · kill{" "}
            {metricText(runtime?.kill_switch)}
          </p>
        </div>
        <div className="vital-card">
          <dt>API</dt>
          <dd>{health?.status === "ok" ? "UP" : "UNREAD"}</dd>
          <p className="muted small">{health?.code_version || "vital"}</p>
        </div>
        <div className="vital-card">
          <dt>Sports shard 3</dt>
          <dd>{moneyText(bankroll?.account?.mlb_shard_cents)}</dd>
          <p className="muted small">Demo {moneyText(bankroll?.demo_account?.mlb_shard_cents)} · not top-level</p>
        </div>
      </div>

      <div className="vital-split">
        <BookPane
          title="Production"
          environment="PRODUCTION"
          account={bankroll?.account}
          kalshi={kalshi}
        />
        <BookPane
          title="Demo"
          environment="DEMO"
          account={bankroll?.demo_account}
          kalshi={{
            status: bankroll?.demo_account?.top_level_cents?.status,
            observed_at:
              bankroll?.demo_account?.observed_at?.status === "CONFIRMED"
                ? String(bankroll.demo_account.observed_at.value || "")
                : undefined,
            detail: bankroll?.demo_account?.source?.detail,
          }}
        />
      </div>

      <StrategyFrame strategy={strategy} />
      <section className="vital-card" aria-label="Registry">
        <div className="vital-row-head">
          <p className="ws-kicker">Units</p>
          <button type="button" className="btn-secondary" onClick={onOpenBots}>
            Filter
          </button>
        </div>
        <BotBlotter bots={ranked} selectedId="mlb-001" onOpen={onOpenDetail} />
      </section>
    </div>
  );
}
