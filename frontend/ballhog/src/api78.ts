export class BallhogError extends Error {
  status: number;
  code: string;

  constructor(status: number, message: string, code = "") {
    super(message);
    this.status = status;
    this.code = code;
  }
}

function fail(res: Response, body: unknown, path: string): never {
  const detail =
    body && typeof body === "object" && "detail" in body
      ? (body as { detail?: { message?: string; code?: string } | string }).detail
      : null;
  const code = detail && typeof detail === "object" ? String(detail.code || "") : "";
  const message =
    (detail && typeof detail === "object" && detail.message) ||
    (typeof detail === "string" ? detail : null) ||
    `HTTP ${res.status} ${path}`;
  throw new BallhogError(res.status, String(message), code);
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path, { headers: { Accept: "application/json" } });
  const body = (await res.json().catch(() => null)) as T | { detail?: { message?: string } | string } | null;
  if (!res.ok) fail(res, body, path);
  return body as T;
}

async function postJson<T>(path: string, payload: Record<string, unknown>): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = (await res.json().catch(() => null)) as T | { detail?: { message?: string } | string } | null;
  if (!res.ok) fail(res, body, path);
  return body as T;
}

export function fetchHealth(): Promise<BallhogHealth> {
  return getJson<BallhogHealth>("/api/ballhog-first78/health");
}

export function fetchPositions(): Promise<BallhogPositionList> {
  return getJson<BallhogPositionList>("/api/ballhog-first78/positions");
}

export function fetchState(tradeId: string, asOf?: string | null, qDir?: string | number | null): Promise<BallhogState> {
  const search = new URLSearchParams();
  if (asOf) search.set("as_of", asOf);
  if (qDir != null && qDir !== "") search.set("q_dir", String(qDir));
  const suffix = search.toString() ? `?${search.toString()}` : "";
  return getJson<BallhogState>(`/api/ballhog-first78/state/${encodeURIComponent(tradeId)}${suffix}`);
}

export function fetchIntent(tradeId: string, asOf?: string | null, qDir?: string | number | null): Promise<BallhogIntent> {
  const search = new URLSearchParams();
  if (asOf) search.set("as_of", asOf);
  if (qDir != null && qDir !== "") search.set("q_dir", String(qDir));
  const suffix = search.toString() ? `?${search.toString()}` : "";
  return getJson<BallhogIntent>(`/api/ballhog-first78/intent/${encodeURIComponent(tradeId)}${suffix}`);
}

export function postDecision(
  tradeId: string,
  asOf?: string | null,
  qDir?: string | number | null,
): Promise<Record<string, unknown>> {
  return postJson("/api/ballhog-first78/decision", {
    trade_id: tradeId,
    as_of: asOf || undefined,
    q_dir: qDir ?? undefined,
  });
}

export type LoadState =
  | "NOT_LOADED"
  | "LOADING"
  | "LOADED"
  | "SOURCE_UNAVAILABLE"
  | "INVALID_AS_OF"
  | "QUERY_ERROR";

export type BallhogHealth = {
  product?: string;
  live_execution?: boolean;
  execution_enabled?: boolean;
  live_feed?: string;
  austin?: { n?: number; universe?: string; availability?: string };
  choosin_texas?: { n?: number; universe?: string; availability?: string };
  note?: string;
};

export type BallhogListRow = {
  position_id: string;
  trade_id?: string;
  ticker?: string;
  game?: string;
  team?: string;
  side?: string;
  display_name?: string;
  default_as_of?: string | null;
  replay_available?: boolean;
  entry_price_cents?: number | null;
  entry_timestamp?: string | null;
  last_observed_at?: string | null;
  last_observed_price_cents?: number | null;
  slice?: string | null;
};

export type BallhogPositionList = {
  n?: number;
  austin_n?: number;
  choosin_n?: number;
  live_feed?: string;
  default_as_of_rule?: string;
  positions: BallhogListRow[];
};

export type SurfaceCell = {
  q_dir?: number;
  q_hedge?: number;
  rho?: number | null;
  residual_qty?: number;
  hedge_price_cents?: number | null;
  austin_alpha_cents?: number;
  austin_alpha_per_unit?: number;
  portfolio_EV_after?: number;
  portfolio_ev_after?: number;
  portfolio_ev_before?: number;
  robust_portfolio_EV_after?: number | null;
  directional_alpha_removed?: number;
  economic_EV_cost_of_hedge?: number;
  risk_removed?: number | null;
  risk_metric?: string;
  fill_claimed?: boolean;
  execution_assumption?: string;
  price_relevant?: boolean;
  is_robust_positive?: boolean;
  is_frontier?: boolean;
  is_admissible?: boolean;
  note?: string;
  on_frontier?: boolean;
  admissible?: boolean;
  [key: string]: unknown;
};

export type BallhogIntent = {
  schema?: string;
  execution_enabled?: boolean;
  rho_star?: number | null;
  q_hedge?: number | null;
  q_star?: number | null;
  timing_state?: string;
  risk_intent?: string;
  hedge_feasibility?: string;
  intent_status?: string;
  decision_status?: string;
  explanation?: string;
  note?: string;
  [key: string]: unknown;
};

export type BallhogState = {
  schema?: string;
  product?: string;
  live_execution?: boolean;
  execution_enabled?: boolean;
  feed_mode?: string;
  live_feed?: string;
  as_of?: string;
  default_as_of?: string | null;
  explanation?: string;
  research_unit_qty?: number;
  q_dir?: number;
  q_hedge?: number | null;
  rho?: number | null;
  current_hedge_price?: string;
  position?: Record<string, unknown>;
  austin?: Record<string, unknown>;
  choosin_texas?: Record<string, unknown>;
  decision?: {
    decision_status?: string;
    risk_intent?: string;
    hedge_feasibility?: string;
    explanation?: string;
    rho_star?: number | null;
    q_star?: number | null;
    delta_star?: number | null;
    target_residual_qty?: number | null;
    reason_codes?: string[];
    timing?: { timing_state?: string; reason_codes?: string[]; note?: string; current_hedge_price?: string };
    surface?: { cells?: SurfaceCell[]; price_grid?: number[]; q_dir?: number };
    frontier?: {
      axes?: { x?: string; y?: string; y_metric?: string };
      frontier?: SurfaceCell[];
      admissible_frontier?: SurfaceCell[];
      points?: SurfaceCell[];
    };
    chosen_frontier_point?: SurfaceCell | null;
    current_hedge_price?: string;
  };
  transitions?: {
    availability?: string;
    sample_support?: number | null;
    support?: string | null;
    branches?: { label?: string; rate?: number; source?: string }[];
    note?: string;
  };
  intent?: BallhogIntent;
};
