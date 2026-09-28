import IntegrationProofPane from "./IntegrationProofPane";
import type {
  VitalDiagnose,
  VitalExecution,
  VitalIntegrationProof,
  VitalLogs,
  VitalMetric,
  VitalRuntime,
  VitalStatus,
} from "./api/vitalApi";
import { metricText } from "./api/vitalApi";
import { ageText, toneForLifecycle } from "./format";

type Props = {
  status: VitalStatus | null;
  runtime: VitalRuntime | null;
  logs: VitalLogs | null;
  execution: VitalExecution | null;
  diagnose: VitalDiagnose | null;
  integration: VitalIntegrationProof | null;
  error: string | null;
  hostBusy?: boolean;
  nowMs?: number;
  onRefreshHost?: () => void;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : null;
}

function metricObject(metric: VitalMetric | undefined | null): Record<string, unknown> | null {
  if (!metric || metric.value == null) return null;
  return asRecord(metric.value);
}

function field(record: Record<string, unknown> | null, key: string): string {
  if (!record || record[key] == null || record[key] === "") return "UNREAD";
  return String(record[key]);
}

function confirmedNumber(metric: VitalMetric | undefined | null): number | null {
  if (!metric || metric.status !== "CONFIRMED" || metric.value == null) return null;
  const n = typeof metric.value === "number" ? metric.value : Number(metric.value);
  return Number.isFinite(n) ? n : null;
}

function layerStatus(count: number | null): string {
  if (count == null) return "UNREAD";
  return count > 0 ? "YES" : "NO";
}

function freshnessOf(observed: Record<string, unknown> | null): string {
  const stamp = observed ? String(observed.observed_at || "") : "";
  if (!stamp) return "UNREAD";
  const ms = Date.parse(stamp);
  if (!Number.isFinite(ms)) return "UNREAD";
  const age = Date.now() - ms;
  if (age < 0 || age > 300_000) return "STALE";
  return "FRESH";
}

export default function LiveObservatory({
  status,
  runtime,
  logs,
  execution,
  diagnose,
  integration,
  error,
  hostBusy = false,
  nowMs = Date.now(),
  onRefreshHost,
}: Props) {
  const lifecycle = runtime?.lifecycle || status?.lifecycle || "OBSERVATION_UNAVAILABLE";
  const observed = asRecord(runtime?.observed);
  const desired = asRecord(runtime?.desired);
  const confirmed = asRecord(runtime?.confirmed);
  const service = metricObject(runtime?.service);
  const process = metricObject(runtime?.process);
  const version = metricObject(runtime?.version);
  const env = metricObject(runtime?.environment_fact) || asRecord(runtime?.environment_fact);
  const trap = metricObject(runtime?.occupancy_trap);
  const trapped = trap?.trapped === true;
  const freshness = freshnessOf(observed);
  const source = observed ? String(observed.source || "UNREAD") : "UNREAD";
  const instance = String(runtime?.instance_id || observed?.instance_id || "UNREAD");
  const unit = field(service, "name") !== "UNREAD" ? field(service, "name") : "momento-live.service";
  const sha = field(version, "binary_sha256");
  const trading = metricObject(runtime?.trading_health);
  const tradingStatus = trading ? field(trading, "status") : metricText(runtime?.trading_health);
  const authorized = trading?.authorized_to_submit === true;
  const hostFill = execution?.source?.host;
  const watching = confirmedNumber(runtime?.mlb_yes_bid_n);
  const first80 = confirmedNumber(runtime?.first80_n);
  const first81 = confirmedNumber(runtime?.first81_n);
  const submitAck = confirmedNumber(runtime?.submit_to_ack_n);
  const fillBody =
    hostFill && typeof hostFill === "object" && "fill_body" in hostFill
      ? String((hostFill as { fill_body?: string }).fill_body || "UNREAD")
      : execution?.fills_status || "UNREAD";

  return (
    <div className="sa-page vital-desk vital-live-obs">
      <header className="vital-desk-head">
        <div>
          <p className="ws-kicker">Live service</p>
          <h1 className="v2-page-title">momento-live.service</h1>
        </div>
        <p className="muted small">
          Observe only · MLB 001 · HTTP 200 ≠ RUNNING · watching ≠ signal ≠ submit ≠ fill
        </p>
      </header>
      {error ? <p className="sa-error">{error}</p> : null}
      {trapped ? (
        <p className="sa-error" role="status">
          Occupancy trap: open_slots at cap with zero tracker fills. This is the ghost-five
          failure. open_mlb_positions=0 is not an empty cap.
        </p>
      ) : null}

      <section className="vital-card" aria-label="Communication">
        <div className="vital-row-head">
          <div>
            <p className="ws-kicker">Communication</p>
            <h2>Vital ↔ host</h2>
          </div>
          <p className={`vital-tone ${freshness === "FRESH" && source === "ssm" ? "is-live" : "is-unread"}`}>
            {freshness}
          </p>
        </div>
        <p className="muted small">
          desired ≠ observed ≠ confirmed · stale or unread is OBSERVATION_UNAVAILABLE, never leftover
          RUNNING
        </p>
        <dl className="vital-mini-dl">
          <div>
            <dt>Source</dt>
            <dd>{source}</dd>
          </div>
          <div>
            <dt>Instance</dt>
            <dd>{instance}</dd>
          </div>
          <div>
            <dt>Service</dt>
            <dd>{String(observed?.service || unit)}</dd>
          </div>
          <div>
            <dt>Observed at</dt>
            <dd>{observed?.observed_at ? String(observed.observed_at) : "UNREAD"}</dd>
          </div>
          <div>
            <dt>Age</dt>
            <dd>{ageText(observed?.observed_at ? String(observed.observed_at) : null, nowMs)}</dd>
          </div>
          <div>
            <dt>Desired</dt>
            <dd>{String(desired?.lifecycle || "OBSERVATION_UNAVAILABLE")}</dd>
          </div>
          <div>
            <dt>Observed guess</dt>
            <dd>{String(observed?.lifecycle_guess || "UNREAD")}</dd>
          </div>
          <div>
            <dt>Confirmed</dt>
            <dd className={`vital-tone ${toneForLifecycle(lifecycle)}`}>{lifecycle}</dd>
          </div>
        </dl>
      </section>

      <section className="vital-card" aria-label="Process">
        <div className="vital-row-head">
          <div>
            <p className="ws-kicker">Process</p>
            <h2>{unit}</h2>
          </div>
          <p className={`vital-tone ${toneForLifecycle(lifecycle)}`}>{field(service, "active")}</p>
        </div>
        <dl className="vital-mini-dl">
          <div>
            <dt>PID</dt>
            <dd>{field(process, "main_pid")}</dd>
          </div>
          <div>
            <dt>Started</dt>
            <dd>{field(service, "started_at")}</dd>
          </div>
          <div>
            <dt>Restarts</dt>
            <dd>{field(service, "n_restarts")}</dd>
          </div>
          <div>
            <dt>CWD</dt>
            <dd>{field(process, "cwd") !== "UNREAD" ? field(process, "cwd") : field(service, "working_directory")}</dd>
          </div>
          <div>
            <dt>SHA256</dt>
            <dd>{sha === "UNREAD" ? "UNREAD" : `${sha.slice(0, 16)}…`}</dd>
          </div>
          <div>
            <dt>Fragment</dt>
            <dd>{field(service, "fragment")}</dd>
          </div>
          <div>
            <dt>Exec</dt>
            <dd>{field(service, "exec_start")}</dd>
          </div>
          <div>
            <dt>Kill</dt>
            <dd>{metricText(runtime?.kill_switch)}</dd>
          </div>
        </dl>
      </section>

      <section className="vital-card" aria-label="Occupancy">
        <div className="vital-row-head">
          <div>
            <p className="ws-kicker">Occupancy</p>
            <h2>Risk cap ≠ fills</h2>
          </div>
          <p className={`vital-tone ${trapped ? "is-risk" : "is-idle"}`}>
            {trapped ? "TRAP" : metricText(runtime?.occupancy_trap) === "UNREAD" ? "UNREAD" : "CLEAR"}
          </p>
        </div>
        <p className="muted small">
          open_mlb_positions is tracker fills. open_slots is Risk occupancy including pending ghosts.
        </p>
        <dl className="vital-mini-dl">
          <div>
            <dt>Open slots</dt>
            <dd>
              {metricText(runtime?.open_slots)} / {metricText(runtime?.max_open_slots) === "UNREAD" ? "5" : metricText(runtime?.max_open_slots)}
            </dd>
          </div>
          <div>
            <dt>Reservations</dt>
            <dd>{metricText(runtime?.reservations_n)}</dd>
          </div>
          <div>
            <dt>Unknown orders</dt>
            <dd>{metricText(runtime?.unknown_orders)}</dd>
          </div>
          <div>
            <dt>Open MLB fills</dt>
            <dd>{metricText(runtime?.open_mlb_positions)}</dd>
          </div>
        </dl>
      </section>

      <section className="vital-card" aria-label="Recon and submit">
        <div className="vital-row-head">
          <div>
            <p className="ws-kicker">Recon / submit</p>
            <h2>Can it enter?</h2>
          </div>
          <p className={`vital-tone ${authorized ? "is-live" : "is-risk"}`}>
            {authorized ? "authorized" : tradingStatus}
          </p>
        </div>
        <dl className="vital-mini-dl">
          <div>
            <dt>Reconciliation</dt>
            <dd>{metricText(runtime?.reconciliation)}</dd>
          </div>
          <div>
            <dt>Order submission</dt>
            <dd>{metricText(runtime?.order_submission)}</dd>
          </div>
          <div>
            <dt>Trading health</dt>
            <dd>{tradingStatus}</dd>
          </div>
          <div>
            <dt>Authorized to submit</dt>
            <dd>{authorized ? "YES" : "NO"}</dd>
          </div>
          <div>
            <dt>Live armed</dt>
            <dd>{metricText(runtime?.live_armed)}</dd>
          </div>
          <div>
            <dt>Kill</dt>
            <dd>{metricText(runtime?.kill_switch)}</dd>
          </div>
        </dl>
      </section>

      <section className="vital-card" aria-label="Today MLB">
        <div className="vital-row-head">
          <div>
            <p className="ws-kicker">Today MLB</p>
            <h2>Watching ≠ trading</h2>
          </div>
        </div>
        <p className="muted small">
          Journal since {metricText(runtime?.journal_since)} · last book is not a fill
        </p>
        <dl className="vital-mini-dl">
          <div>
            <dt>Last ticker</dt>
            <dd>{metricText(runtime?.last_mlb_ticker)}</dd>
          </div>
          <div>
            <dt>Last bid / ask</dt>
            <dd>
              {metricText(runtime?.last_mlb_bid_cents)} / {metricText(runtime?.last_mlb_ask_cents)}
            </dd>
          </div>
          <div>
            <dt>YES bid updates</dt>
            <dd>{metricText(runtime?.mlb_yes_bid_n)}</dd>
          </div>
          <div>
            <dt>Markets / MLB games</dt>
            <dd>
              {metricText(runtime?.heartbeat_markets)} / {metricText(runtime?.strategy_games)}
            </dd>
          </div>
          <div>
            <dt>WATCHING</dt>
            <dd>{layerStatus(watching)}</dd>
          </div>
          <div>
            <dt>SIGNAL First80 / 81</dt>
            <dd>
              {layerStatus(first80)} / {layerStatus(first81)} ({metricText(runtime?.first80_n)} /{" "}
              {metricText(runtime?.first81_n)})
            </dd>
          </div>
          <div>
            <dt>SUBMIT ack / refused</dt>
            <dd>
              {layerStatus(submitAck)} / {metricText(runtime?.submit_refused_n)}
            </dd>
          </div>
          <div>
            <dt>FILL body</dt>
            <dd>{fillBody}</dd>
          </div>
        </dl>
      </section>

      <section className="vital-card" aria-label="Gates">
        <div className="vital-row-head">
          <div>
            <p className="ws-kicker">Gates</p>
            <h2>live.toml / env names</h2>
          </div>
          <p className="vital-tone is-idle">
            {diagnose?.live_toml?.armed ? "ARMED" : diagnose?.live_toml?.reason || "UNREAD"}
          </p>
        </div>
        <p className="muted small">Values only for gates. Secret path contents are never shown.</p>
        <dl className="vital-mini-dl">
          <div>
            <dt>Repo live.toml</dt>
            <dd>{diagnose?.live_toml?.armed ? "triple gate present" : diagnose?.live_toml?.reason || "UNREAD"}</dd>
          </div>
          <div>
            <dt>Kalshi env name</dt>
            <dd>{field(env, "kalshi_env_name")}</dd>
          </div>
          <div>
            <dt>Kalshi env</dt>
            <dd>{field(env, "kalshi_env") !== "UNREAD" ? field(env, "kalshi_env") : field(env, "label")}</dd>
          </div>
          <div>
            <dt>Env names</dt>
            <dd>
              {Array.isArray(env?.env_names) ? (env?.env_names as string[]).join(" ") || "UNREAD" : "UNREAD"}
            </dd>
          </div>
        </dl>
      </section>

      <section className="vital-card" aria-label="Execution ledger">
        <div className="vital-row-head">
          <div>
            <p className="ws-kicker">Ledger</p>
            <h2>Observed fills</h2>
          </div>
          <p className="vital-tone is-unread">{execution?.fills_status || "UNREAD"}</p>
        </div>
        <p className="muted small">Unread fill body stays OBSERVATION_UNAVAILABLE. Missing is not $0.</p>
        <dl className="vital-mini-dl">
          <div>
            <dt>Execution</dt>
            <dd>{execution?.status || "UNREAD"}</dd>
          </div>
          <div>
            <dt>Fills</dt>
            <dd>{execution?.fills_status || "UNREAD"}</dd>
          </div>
          <div>
            <dt>Trades</dt>
            <dd>{execution?.trades_status || "UNREAD"}</dd>
          </div>
          <div>
            <dt>Host fill body</dt>
            <dd>{fillBody}</dd>
          </div>
        </dl>
      </section>

      <section className="vital-card" aria-label="Journal">
        <div className="vital-row-head">
          <div>
            <p className="ws-kicker">Journal</p>
            <h2>Last host lines</h2>
          </div>
          <p className="muted small">{logs?.status || "UNREAD"}</p>
        </div>
        <pre className="vital-journal">
          {(logs?.logs || []).slice(-12).join("\n") || "UNREAD"}
        </pre>
      </section>

      <IntegrationProofPane proof={integration} variant="detail" />

      <div className="ws-labs-toolbar">
        <button type="button" className="btn-secondary" disabled={hostBusy} onClick={onRefreshHost}>
          {hostBusy ? "Reading host…" : "Refresh host"}
        </button>
        <p className="muted small">
          Control start/stop/kill stays on Unit. This page does not enable VITAL_AWS_CONTROL.
          Confirmed lifecycle {confirmed && "lifecycle" in confirmed ? "present" : "UNREAD"}.
        </p>
      </div>
    </div>
  );
}
