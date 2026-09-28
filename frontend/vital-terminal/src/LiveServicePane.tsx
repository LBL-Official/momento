import type {
  VitalCommand,
  VitalControls,
  VitalDiagnose,
  VitalMetric,
  VitalRuntime,
} from "./api/vitalApi";
import { metricText } from "./api/vitalApi";
import { toneForLifecycle } from "./format";

type Props = {
  variant: "desk" | "detail";
  botId?: string;
  runtime: VitalRuntime | null;
  controls?: VitalControls | null;
  diagnose?: VitalDiagnose | null;
  confirmation?: string;
  last?: VitalCommand | null;
  busy?: boolean;
  hostBusy?: boolean;
  onConfirmation?: (value: string) => void;
  onCommand?: (action: "deploy" | "start" | "stop" | "restart" | "kill") => void;
  onRefreshHost?: () => void;
  onOpenDetail?: () => void;
};

const ACTIONS = ["deploy", "start", "stop", "restart", "kill"] as const;

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

function serviceActive(runtime: VitalRuntime | null): string {
  const service = metricObject(runtime?.service);
  if (!service) return metricText(runtime?.service);
  return field(service, "active") !== "UNREAD" ? field(service, "active") : field(service, "active_state");
}

function controlState(controls: VitalControls | null | undefined): string {
  if (!controls) return "UNREAD";
  if (!controls.enabled) return "CONTROL_DISABLED";
  if (controls.dispatch_mode === "mock") return "MOCK";
  if (controls.dispatch_mode === "ssm") return "ARMED";
  return controls.dispatch_mode || "CONTROL_DISABLED";
}

export default function LiveServicePane({
  variant,
  botId,
  runtime,
  controls,
  diagnose,
  confirmation = "",
  last,
  busy = false,
  hostBusy = false,
  onConfirmation,
  onCommand,
  onRefreshHost,
  onOpenDetail,
}: Props) {
  const lifecycle = runtime?.lifecycle || "OBSERVATION_UNAVAILABLE";
  const service = metricObject(runtime?.service);
  const process = metricObject(runtime?.process);
  const version = metricObject(runtime?.version);
  const heartbeat = metricObject(runtime?.heartbeat);
  const trading = metricObject(runtime?.trading_health);
  const tradingStatus = trading ? field(trading, "status") : metricText(runtime?.trading_health);
  const authorized = trading?.authorized_to_submit === true;
  const observed = asRecord(runtime?.observed);
  const gate = controlState(controls);
  const unit = field(service, "name") !== "UNREAD" ? field(service, "name") : "momento-live.service";
  const instance =
    runtime?.instance_id ||
    (metricObject(runtime?.host) ? field(metricObject(runtime?.host), "instance_id") : "UNREAD");

  return (
    <section className="vital-card vital-live-service" aria-label="Live service">
      <div className="vital-row-head">
        <div>
          <p className="ws-kicker">Live service</p>
          <h2>{unit}</h2>
        </div>
        <p className={`vital-tone ${toneForLifecycle(lifecycle)}`}>{lifecycle}</p>
      </div>
      <p className="muted small">
        {botId || "mlb-001"} · source {String(observed?.source || "UNREAD")} · inspect{" "}
        {String(observed?.status || "UNREAD")} · control {gate}
        {controls?.enabled ? ` · dispatch ${controls.dispatch_mode || "UNREAD"}` : ""}
      </p>
      <dl className="vital-mini-dl">
        <div>
          <dt>Active</dt>
          <dd>{serviceActive(runtime)}</dd>
        </div>
        <div>
          <dt>Substate</dt>
          <dd>{field(service, "sub_state")}</dd>
        </div>
        <div>
          <dt>PID</dt>
          <dd>{field(process, "main_pid")}</dd>
        </div>
        <div>
          <dt>Started</dt>
          <dd>{field(service, "started_at")}</dd>
        </div>
        <div>
          <dt>Instance</dt>
          <dd>
            {instance}
            {runtime?.instance_verified === false ? " unverified" : ""}
          </dd>
        </div>
        <div>
          <dt>Binary</dt>
          <dd>
            {version?.binary_exists === false
              ? "MISSING"
              : field(version, "binary_sha256") === "UNREAD"
                ? "UNREAD"
                : `${field(version, "binary_sha256").slice(0, 12)}…`}
          </dd>
        </div>
        <div>
          <dt>Kill</dt>
          <dd>{metricText(runtime?.kill_switch)}</dd>
        </div>
        <div>
          <dt>Live armed</dt>
          <dd>{metricText(runtime?.live_armed)}</dd>
        </div>
        <div>
          <dt>Open MLB</dt>
          <dd>{metricText(runtime?.open_mlb_positions)}</dd>
        </div>
        <div>
          <dt>Open slots</dt>
          <dd>{metricText(runtime?.open_slots)}</dd>
        </div>
        <div>
          <dt>Recon</dt>
          <dd>{metricText(runtime?.reconciliation)}</dd>
        </div>
        <div>
          <dt>Submit</dt>
          <dd>{metricText(runtime?.order_submission)}</dd>
        </div>
        <div>
          <dt>Trading health</dt>
          <dd>{tradingStatus}</dd>
        </div>
        <div>
          <dt>Authorized</dt>
          <dd>{authorized ? "YES" : "NO"}</dd>
        </div>
        <div>
          <dt>Heartbeat</dt>
          <dd>{field(heartbeat, "updated_at")}</dd>
        </div>
      </dl>
      {diagnose ? (
        <p className="muted small">
          Diagnose · host {diagnose.host_confirmed ? "CONFIRMED" : "UNREAD"} · service{" "}
          {diagnose.service_active ? "active" : diagnose.host_confirmed ? "inactive" : "unread"} · live.toml{" "}
          {diagnose.live_toml?.armed ? "armed" : diagnose.live_toml?.reason || "unread"}
        </p>
      ) : null}
      <div className="ws-labs-toolbar">
        <button type="button" className="btn-secondary" disabled={hostBusy} onClick={onRefreshHost}>
          {hostBusy ? "Reading host…" : "Refresh host"}
        </button>
        {variant === "desk" && onOpenDetail ? (
          <button type="button" className="btn-primary" onClick={onOpenDetail}>
            Open unit
          </button>
        ) : null}
      </div>
      {variant === "detail" ? (
        <>
          <p className="muted small">
            {controls?.note ||
              "Host writes require VITAL_AWS_CONTROL=1 and confirmation=VITAL_ENABLE_CONTROL. Start is not live arm. Kill does not flatten."}
          </p>
          <label>
            Confirmation
            <input
              value={confirmation}
              onChange={(e) => onConfirmation?.(e.target.value)}
              placeholder={controls?.confirmation_token_name || "VITAL_ENABLE_CONTROL"}
              autoComplete="off"
            />
          </label>
          <div className="ws-labs-toolbar">
            {ACTIONS.map((action) => (
              <button
                key={action}
                type="button"
                className={action === "kill" ? "btn-primary" : "btn-secondary"}
                disabled={busy || !onCommand}
                onClick={() => onCommand?.(action)}
              >
                {action}
              </button>
            ))}
          </div>
          {last ? (
            <p className="muted small">
              {last.action} · {last.command_status} · after {last.lifecycle_after || "—"}
              {last.detail ? ` · ${last.detail}` : ""}
            </p>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
