import { apiFetch } from "./base";

export type VitalMetric = {
  value?: unknown;
  status?: string;
  detail?: string;
};

export type VitalProofStatus = {
  status?: string;
  detail?: string;
  value?: unknown;
};

export type VitalIntegrationProof = {
  proof_id?: string;
  name?: string;
  bot_id?: string;
  factory?: boolean;
  accepted?: boolean;
  lifecycle_claim?: string;
  highest_confirmed_stage?: string | null;
  strategy_status?: string;
  collapsed_to_running?: boolean;
  not_live?: boolean;
  not_trading?: boolean;
  blocking?: string[];
  suites?: Record<string, VitalProofStatus | Record<string, unknown>>;
  levels?: Record<string, VitalProofStatus | Record<string, unknown>>;
  chain?: Record<string, VitalProofStatus>;
  architecture?: Record<string, unknown>;
  http_200_not_running?: boolean;
};

export type VitalHealth = {
  status: string;
  product: string;
  code_version: string;
  schema_version?: string;
  phases?: Record<string, string>;
  bot_id?: string;
  live_execution?: boolean;
  canonical_owner?: boolean;
  http_200_not_running?: boolean;
  honesty?: Record<string, string | boolean>;
  caveats?: string[];
  integration_proof?: { id?: string; status?: string; accepted_only_if_suites_confirmed?: boolean };
};

export type VitalBot = {
  bot_id: string;
  name?: string;
  kind?: string;
  environment?: string;
  desired_environment?: string;
  status?: string;
  health?: string;
  activation?: string;
  jump_bot_id?: string;
  iti_lineage?: string;
  strategy_fingerprint?: string;
  slot_id?: string;
  settings?: Record<string, unknown>;
  iti?: Record<string, unknown>;
  aliases?: string[];
  engine_pointer?: string;
  strategy_pointer?: string;
  sport?: string;
  attach?: {
    autonomous?: boolean;
    unit_started?: boolean;
    kalshi_demo?: {
      status?: string;
      balance_cents?: number | null;
      fill_n?: number | null;
      position_n?: number | null;
      detail?: string | null;
    };
    aws?: {
      status?: string;
      session?: string;
      demo_secret?: string;
      detail?: string | null;
      region?: string;
    };
  };
  engine?: {
    kind?: string;
    sport?: string;
    source?: string;
    prices?: { entry_cents?: number | null; win_cents?: number | null; loss_cents?: number | null };
    implementation?: { spec?: string; worker?: string; submit?: boolean };
  };
  aws_runtime_id?: string;
  factory?: Record<string, unknown> | null;
  fingerprints?: { recorded_at?: string; moved?: boolean; targets?: { path: string; sha256?: string | null }[] };
  config_identity?: Record<string, unknown> | null;
  deployment_identity?: Record<string, unknown> | null;
};

export type VitalStatus = {
  bot_id: string;
  name?: string;
  environment?: string;
  lifecycle?: string;
  health?: string;
  desired?: Record<string, unknown>;
  observed?: Record<string, unknown>;
  confirmed?: Record<string, VitalMetric | unknown>;
  http_200_not_running?: boolean;
};

export type VitalRuntime = {
  lifecycle?: string;
  health?: string;
  host?: VitalMetric;
  service?: VitalMetric;
  process?: VitalMetric;
  version?: VitalMetric;
  heartbeat?: VitalMetric;
  kill_switch?: VitalMetric;
  live_armed?: VitalMetric;
  bankroll_cents?: VitalMetric;
  open_mlb_positions?: VitalMetric;
  reconciliation?: VitalMetric;
  reservations_n?: VitalMetric;
  unknown_orders?: VitalMetric;
  open_slots?: VitalMetric;
  order_submission?: VitalMetric;
  trading_health?: VitalMetric;
  occupancy_trap?: VitalMetric;
  mlb_yes_bid_n?: VitalMetric;
  first80_n?: VitalMetric;
  first81_n?: VitalMetric;
  submit_to_ack_n?: VitalMetric;
  submit_refused_n?: VitalMetric;
  last_mlb_ticker?: VitalMetric;
  last_mlb_bid_cents?: VitalMetric;
  last_mlb_ask_cents?: VitalMetric;
  heartbeat_markets?: VitalMetric;
  strategy_games?: VitalMetric;
  wnba_games?: VitalMetric;
  max_open_slots?: VitalMetric;
  journal_since?: VitalMetric;
  environment_fact?: VitalMetric;
  day_pnl?: VitalMetric;
  week_pnl?: VitalMetric;
  live_ev?: VitalMetric;
  sharpe?: VitalMetric;
  instance_id?: string;
  instance_verified?: boolean;
  confirmed?: Record<string, VitalMetric | unknown>;
  desired?: Record<string, unknown>;
  observed?: Record<string, unknown>;
};

export type VitalControls = {
  enabled?: boolean;
  control_env?: string;
  dispatch_mode?: string;
  dispatch_env?: string;
  confirmation_token_name?: string;
  actions?: string[];
  fail_closed?: boolean;
  note?: string;
  start_is_not_live_arm?: boolean;
  kill_is_not_stop?: boolean;
  kill_does_not_flatten?: boolean;
  default_status?: string;
};

export type VitalCommand = {
  command_id: string;
  action: string;
  command_status: string;
  desired_state?: string;
  requested_at?: string;
  detail?: string;
  lifecycle_after?: string;
  http_200_not_running?: boolean;
  start_is_not_live_arm?: boolean;
  kill_is_not_stop?: boolean;
};

async function parse<T>(res: Response): Promise<T> {
  const body = (await res.json()) as T & { detail?: string | { message?: string } };
  if (!res.ok) {
    const detail = body.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail && typeof detail === "object"
          ? detail.message || res.statusText
          : res.statusText;
    throw new Error(message || res.statusText);
  }
  return body;
}

export type VitalDeskHeaderBook = {
  environment?: string;
  top_level_cents?: VitalMetric;
  sports_shard_cents?: VitalMetric;
  catch_all_shard_cents?: VitalMetric;
  day_delta_cents?: VitalMetric;
  week_delta_cents?: VitalMetric;
  origin_pnl_cents?: VitalMetric;
  shard_label?: string;
  source?: VitalMetric;
  observed_at?: VitalMetric;
};

export type VitalDesk = {
  product?: string;
  surface?: "list" | "full";
  selected_id?: string;
  built_at?: string;
  observe_included?: boolean;
  health?: VitalHealth;
  bots?: VitalBot[];
  n?: number;
  bankroll?: VitalBankroll;
  header?: {
    PRODUCTION?: VitalDeskHeaderBook;
    DEMO?: VitalDeskHeaderBook;
  };
  focus?: {
    bot?: VitalBot;
    status?: VitalStatus;
    runtime?: VitalRuntime;
    kalshi?: VitalKalshi;
    strategy?: VitalStrategy;
    controls?: VitalControls;
    integration?: VitalIntegrationProof;
  };
  surfaces?: {
    parameters?: VitalParameters;
    kalshi_health?: VitalKalshiHealth;
    logs?: VitalLogs;
    execution?: VitalExecution;
    events?: Record<string, unknown>[];
    orders?: Record<string, unknown> | null;
    positions?: Record<string, unknown> | null;
    diagnose?: VitalDiagnose | null;
  };
};

export async function getVitalHealth(): Promise<VitalHealth> {
  const res = await apiFetch("/vital/health");
  return parse<VitalHealth>(res);
}

export async function getVitalDesk(
  botId?: string,
  surface: "list" | "full" = "list",
): Promise<VitalDesk> {
  const params = new URLSearchParams();
  if (botId) params.set("bot_id", botId);
  params.set("surface", surface);
  const res = await apiFetch(`/vital/desk?${params.toString()}`);
  return parse<VitalDesk>(res);
}

export async function listVitalBots(): Promise<{ bots: VitalBot[]; n: number }> {
  const res = await apiFetch("/vital/bots");
  return parse(res);
}

export async function getVitalBot(botId: string): Promise<VitalBot> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}`);
  return parse(res);
}

export async function getVitalStatus(botId: string): Promise<VitalStatus> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/status`);
  return parse(res);
}

export async function getVitalBotHealth(botId: string): Promise<Record<string, unknown>> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/health`);
  return parse(res);
}

export async function getVitalRuntime(botId: string): Promise<VitalRuntime> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/runtime`);
  return parse(res);
}

export async function getVitalDeployment(botId: string): Promise<Record<string, unknown>> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/deployment`);
  return parse(res);
}

export async function getVitalLogs(botId: string): Promise<VitalLogs> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/logs`);
  return parse(res);
}

export async function getVitalParameters(botId: string): Promise<VitalParameters> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/parameters`);
  return parse(res);
}

export async function patchVitalParameters(
  botId: string,
  body: {
    iti_entry_cents?: number;
    iti_win_cents?: number;
    iti_loss_cents?: number;
    max_position_budget_cents?: number;
  },
): Promise<VitalParameters> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/parameters`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parse(res);
}

export async function getVitalKalshiHealth(botId: string): Promise<VitalKalshiHealth> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/kalshi-health`);
  return parse(res);
}

export async function getVitalOrders(botId: string): Promise<Record<string, unknown>> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/orders`);
  return parse(res);
}

export async function getVitalPositions(botId: string): Promise<Record<string, unknown>> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/positions`);
  return parse(res);
}

export type VitalExecutionSummary = {
  total_trades?: VitalMetric;
  open?: VitalMetric;
  closed?: VitalMetric;
  total_fills?: VitalMetric;
};

export type VitalFill = {
  fill_id?: string;
  source?: string;
  observation_status?: string;
  market?: VitalMetric;
  side?: VitalMetric;
  timestamp?: VitalMetric;
  price_cents?: VitalMetric;
  contracts?: VitalMetric;
  amount_cents?: VitalMetric;
  fee_cents?: VitalMetric;
  fee_kind?: VitalMetric;
};

export type VitalTrade = {
  trade_id?: string;
  status?: string;
  source?: string;
  observation_status?: string;
  market?: VitalMetric;
  game?: VitalMetric;
  entry_date?: VitalMetric;
  entry_amount?: VitalMetric;
  entry_price?: VitalMetric;
  entry_price_cents?: VitalMetric;
  entry_contracts?: VitalMetric;
  amount_risked_cents?: VitalMetric;
  exit_date?: VitalMetric;
  exit_amount?: VitalMetric;
  exit_price?: VitalMetric;
  exit_price_cents?: VitalMetric;
  exit_contracts?: VitalMetric;
  amount_traded_cents?: VitalMetric;
  amount_exited_cents?: VitalMetric;
  bankroll_at_entry_cents?: VitalMetric;
  pct_bankroll_allocated_bp?: VitalMetric;
  pct_bankroll_returned_bp?: VitalMetric;
  pct_allocated_pnl_bp?: VitalMetric;
  gross_realized_cents?: VitalMetric;
  fee_cents?: VitalMetric;
  net_realized_cents?: VitalMetric;
  standard_row?: Record<string, VitalMetric | undefined>;
};

export type VitalKalshi = {
  status?: string;
  detail?: string;
  observed_at?: string | null;
  read_only?: boolean;
  submits?: boolean;
  fill_n?: number;
  position_n?: number;
  mlb_shard_cents?: number | null;
  exchange_index?: number | null;
  last_reject_code?: string | null;
};

export type VitalParameterRow = {
  key: string;
  value?: unknown;
  unit?: string;
  source?: string;
  editable?: boolean;
  locked_reason?: string | null;
};

export type VitalParameters = {
  bot_id?: string;
  kind?: string;
  environment?: string;
  editable?: boolean;
  spec_status?: string;
  parameters?: VitalParameterRow[];
  note?: string;
  patched?: boolean;
  apply?: { ok?: boolean; reason?: string | null; attempted?: boolean };
};

export type VitalKalshiHealth = {
  status?: string;
  environment?: string;
  last_poll_ts?: string | null;
  last_series?: string | null;
  last_http_class?: number | null;
  last_reject_code?: string | null;
  last_submit_refused?: string | null;
  last_poll_error?: string | null;
  mlb_shard_cents?: number | null;
  shard_status?: string;
  book_status?: string;
  observed_at?: string | null;
  detail?: string;
  unit?: string | null;
};

export type VitalLogs = {
  logs?: string[];
  status?: string;
  detail?: string;
  unit?: string;
  kalshi_health?: VitalKalshiHealth;
};

export type VitalExecution = {
  bot_id?: string;
  status?: string;
  trades_status?: string;
  fills_status?: string;
  trades?: VitalTrade[] | null;
  fills?: VitalFill[] | null;
  summary?: VitalExecutionSummary;
  observation?: string;
  detail?: string;
  grouping?: string;
  ticker_group_when_confirmed?: boolean;
  kalshi?: VitalKalshi;
  source?: { host?: VitalMetric; catalog?: VitalMetric };
};

export async function getVitalExecution(botId: string): Promise<VitalExecution> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/execution`);
  return parse(res);
}

export type VitalBankrollAccount = {
  environment?: string;
  demo_not_mixed?: boolean;
  top_level_cents?: VitalMetric;
  mlb_shard_cents?: VitalMetric;
  factory_bankroll_cents?: VitalMetric;
  factory_unit_cents?: VitalMetric;
  factory_allocation_bps?: VitalMetric;
  day_delta_cents?: VitalMetric;
  week_delta_cents?: VitalMetric;
  exchange_index?: VitalMetric;
  source?: VitalMetric;
  observed_at?: VitalMetric;
};

export type VitalDemoAccount = {
  environment?: string;
  production_not_mixed?: boolean;
  top_level_cents?: VitalMetric;
  mlb_shard_cents?: VitalMetric;
  catch_all_shard_cents?: VitalMetric;
  shard_label?: string;
  origin_cents?: VitalMetric;
  origin_pnl_cents?: VitalMetric;
  day_delta_cents?: VitalMetric;
  week_delta_cents?: VitalMetric;
  fallback_bankroll_cents?: VitalMetric;
  default_unit_cents?: VitalMetric;
  source?: VitalMetric;
  observed_at?: VitalMetric;
  seeded_from_mcp?: boolean;
};

export type VitalDemoReport = {
  environment?: string;
  trade_n?: VitalMetric;
  settled_n?: VitalMetric;
  wins?: VitalMetric;
  losses?: VitalMetric;
  fill_result_sum_cents?: VitalMetric;
  day_fill_result_cents?: VitalMetric;
  week_fill_result_cents?: VitalMetric;
  last_trade?: VitalMetric;
  origin_pnl_cents?: VitalMetric;
  fill_result_is_not_account_pnl?: boolean;
  live_ev?: string;
  sharpe?: string;
};

export type VitalBankrollBot = {
  bot_id: string;
  name?: string;
  environment?: string;
  kind?: string;
  allocation?: {
    desired?: VitalMetric;
    observed?: VitalMetric;
    confirmed?: VitalMetric;
    unit_cents?: VitalMetric;
    unit_bp?: VitalMetric;
    apply_status?: string;
  };
  limits?: {
    desired?: VitalMetric;
    observed?: VitalMetric;
    confirmed?: VitalMetric;
    remaining?: VitalMetric;
    hit?: VitalMetric;
    one_bet_per_game?: boolean;
    block_new_entries_only?: boolean;
    day_clock?: string;
  };
};

export type VitalBankroll = {
  account?: VitalBankrollAccount;
  demo_account?: VitalDemoAccount;
  demo_report?: VitalDemoReport;
  bots?: VitalBankrollBot[];
  n?: number;
  honesty?: Record<string, string | boolean>;
  kalshi_mcp?: boolean;
  seeded_from_mcp?: boolean;
};

export async function getVitalBankroll(): Promise<VitalBankroll> {
  const res = await apiFetch("/vital/bankroll");
  return parse(res);
}

export async function postVitalAllocation(
  botId: string,
  body: {
    mode: string;
    amount_cents?: number;
    allocation_bps?: number;
    confirmation?: string;
  },
): Promise<Record<string, unknown>> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/allocation`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parse(res);
}

export async function postVitalLimits(
  botId: string,
  body: {
    max_daily_entries?: number;
    max_daily_wins?: number;
    max_daily_losses?: number;
    max_daily_win_cents?: number;
    max_daily_loss_cents?: number;
    confirmation?: string;
  },
): Promise<Record<string, unknown>> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/limits`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parse(res);
}

export async function activateVitalBot(
  botId: string,
  confirmation: string,
): Promise<Record<string, unknown>> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/activate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirmation }),
  });
  return parse(res);
}

export async function getVitalIntegration(botId: string): Promise<VitalIntegrationProof> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/integration`);
  return parse(res);
}

export async function postVitalDemoLifecycle(
  botId: string,
  confirmation: string,
): Promise<Record<string, unknown>> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/integration/demo-lifecycle`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirmation }),
  });
  return parse(res);
}

export async function postVitalIntegrationHandshake(
  botId: string,
  body: Record<string, unknown> = {},
): Promise<Record<string, unknown>> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/integration/handshake`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parse(res);
}

export async function observeVitalHost(botId: string): Promise<{
  refreshed?: boolean;
  lifecycle?: string;
  health?: string;
  runtime?: VitalRuntime;
  detail?: string;
}> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/host/observe`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  return parse(res);
}

export async function observeVitalKalshi(
  botId: string,
  environment?: "DEMO" | "PRODUCTION",
): Promise<Record<string, unknown>> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/kalshi/observe`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(environment ? { environment } : {}),
  });
  return parse(res);
}

export async function getVitalExecutionTrade(botId: string, tradeId: string): Promise<{ trade?: VitalTrade | null; status?: string; detail?: string }> {
  const res = await apiFetch(
    `/vital/bots/${encodeURIComponent(botId)}/execution/trades/${encodeURIComponent(tradeId)}`,
  );
  return parse(res);
}

export async function getVitalEvents(botId: string): Promise<{ events?: Record<string, unknown>[] }> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/events`);
  return parse(res);
}

export async function getVitalPlane(botId: string): Promise<Record<string, unknown>> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/plane`);
  return parse(res);
}

export async function getVitalConfiguration(botId: string): Promise<Record<string, unknown>> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/configuration`);
  return parse(res);
}

export type VitalStrategy = {
  bot_id?: string;
  kind?: string;
  signal?: string;
  looking_for?: string;
  note?: string;
  spec_status?: string;
  candle_path_not_fill?: boolean;
  prices?: { entry_cents?: number | null; win_cents?: number | null; loss_cents?: number | null };
  constants?: {
    min_entry_cents?: number;
    confirm_cents?: number;
    max_entry_cents?: number;
    lock_cents?: number;
  };
  entry_rules?: Record<string, unknown>;
  exit_rules?: Record<string, unknown>;
  order_rules?: Record<string, unknown>;
  iti?: {
    folder?: string;
    slot_id?: string;
    BASE_GRADE?: string;
    DEBASE_GRADE?: string;
  };
};

export async function getVitalStrategy(botId: string): Promise<VitalStrategy> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/strategy`);
  return parse(res);
}

export async function getVitalKalshi(botId: string): Promise<VitalKalshi> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/kalshi`);
  return parse(res);
}

export type VitalDiagnose = {
  bot_id?: string;
  lifecycle?: string;
  host_confirmed?: boolean;
  service_active?: boolean;
  live_toml?: { armed?: boolean; reason?: string | null; ok?: boolean };
  kalshi?: VitalKalshi;
  parameters?: VitalParameters;
  factory_locked?: boolean;
  control_enabled?: boolean;
  can_start_if_armed?: boolean;
  started?: boolean;
  command_status?: string;
  detail?: string;
  note?: string;
  http_200_not_running?: boolean;
  invented_fills?: boolean;
};

export async function getVitalDiagnose(botId: string): Promise<VitalDiagnose> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/diagnose`);
  return parse(res);
}

export async function promoteVitalBot(
  botId: string,
  body: { mode: string; live_enabled: boolean; confirmation: string },
): Promise<Record<string, unknown>> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/production`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parse(res);
}

export async function startVitalIfArmed(
  botId: string,
  confirmation: string,
): Promise<VitalDiagnose> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/start-if-armed`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirmation }),
  });
  return parse(res);
}

export async function getVitalRisk(botId: string): Promise<Record<string, unknown>> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/risk`);
  return parse(res);
}

export async function getVitalHeartbeat(botId: string): Promise<Record<string, unknown>> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/heartbeat`);
  return parse(res);
}

export async function getVitalControls(botId: string): Promise<VitalControls> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/controls`);
  return parse(res);
}

export async function getVitalBoundary(botId: string): Promise<Record<string, unknown>> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/boundary`);
  return parse(res);
}

export async function getVitalWorker(botId: string): Promise<Record<string, unknown>> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/worker`);
  return parse(res);
}

export async function getVitalPipeline(botId: string): Promise<Record<string, unknown>> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/pipeline`);
  return parse(res);
}

export async function postVitalCommand(
  botId: string,
  action: string,
  confirmation: string,
): Promise<VitalCommand> {
  const res = await apiFetch(`/vital/bots/${encodeURIComponent(botId)}/commands`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, confirmation }),
  });
  return parse(res);
}

function compactObject(value: Record<string, unknown>): string {
  const instanceId = value.instance_id;
  if (typeof instanceId === "string" && instanceId) {
    return value.verified === true ? instanceId : `${instanceId} unverified`;
  }
  const name = value.name;
  if (typeof name === "string" && name) {
    const active = value.active ?? value.active_state ?? value.sub_state;
    return active ? `${name} ${String(active)}` : name;
  }
  const unit = value.unit_cents;
  if (typeof unit === "number" && Number.isFinite(unit)) {
    return `$${(Math.abs(unit) / 100).toFixed(2)}`;
  }
  const keys = Object.keys(value).filter((key) => value[key] != null).slice(0, 2);
  if (!keys.length) return "CONFIRMED";
  return keys.map((key) => `${key}=${String(value[key])}`).join(" ");
}

export function metricText(metric: VitalMetric | undefined | null): string {
  if (!metric) return "UNREAD";
  if (metric.status !== "CONFIRMED" || metric.value === null || metric.value === undefined) {
    if (metric.status === "OBSERVATION_UNAVAILABLE") return "UNREAD";
    return metric.status || "UNREAD";
  }
  if (typeof metric.value === "boolean") return metric.value ? "YES" : "NO";
  if (typeof metric.value === "object") return compactObject(metric.value as Record<string, unknown>);
  return String(metric.value);
}

function confirmedNumber(metric: VitalMetric | undefined | null): number | null {
  if (!metric || metric.status !== "CONFIRMED" || metric.value === null || metric.value === undefined) {
    return null;
  }
  if (typeof metric.value === "number" && Number.isFinite(metric.value)) return metric.value;
  if (typeof metric.value === "string" && metric.value.trim() !== "") {
    const parsed = Number(metric.value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

export function moneyText(metric: VitalMetric | undefined | null, signed = false): string {
  const value = confirmedNumber(metric);
  if (value === null) {
    if (metric?.status === "OBSERVATION_UNAVAILABLE") return "UNREAD";
    return metric?.status || "UNREAD";
  }
  const sign = value < 0 ? "-" : signed && value > 0 ? "+" : "";
  return `${sign}$${(Math.abs(value) / 100).toFixed(2)}`;
}

export function priceText(metric: VitalMetric | undefined | null): string {
  const value = confirmedNumber(metric);
  if (value === null) {
    if (metric?.status === "OBSERVATION_UNAVAILABLE") return "UNREAD";
    return metric?.status || "UNREAD";
  }
  return `${value}¢`;
}

export function bpText(metric: VitalMetric | undefined | null): string {
  const value = confirmedNumber(metric);
  if (value === null) {
    if (metric?.status === "OBSERVATION_UNAVAILABLE") return "UNREAD";
    return metric?.status || "UNREAD";
  }
  const sign = value < 0 ? "-" : "";
  return `${sign}${(Math.abs(value) / 100).toFixed(2)}%`;
}

export function entryExitText(amount: VitalMetric | undefined | null, price: VitalMetric | undefined | null): string {
  const money = moneyText(amount);
  const px = priceText(price);
  if (money === "UNREAD" && px === "UNREAD") return "UNREAD";
  if (amount?.status !== "CONFIRMED" && price?.status !== "CONFIRMED") {
    return amount?.status === "OBSERVATION_UNAVAILABLE" ? "UNREAD" : amount?.status || price?.status || "UNREAD";
  }
  return `${money} @ ${px}`;
}
