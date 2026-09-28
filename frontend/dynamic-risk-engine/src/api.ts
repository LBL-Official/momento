export class DreError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path, { headers: { Accept: "application/json" } });
  const body = (await res.json().catch(() => null)) as T | { detail?: { message?: string } | string } | null;
  if (!res.ok) {
    const detail = body && typeof body === "object" && "detail" in body ? body.detail : null;
    const message =
      (detail && typeof detail === "object" && detail.message) ||
      (typeof detail === "string" ? detail : null) ||
      `HTTP ${res.status} ${path}`;
    throw new DreError(res.status, String(message));
  }
  return body as T;
}

export type DreBook = "78" | "80";

function dreRoot(book: DreBook = "80"): string {
  return book === "78" ? "/api/dre-first78" : "/api/dre";
}

export function fetchDre<T>(path: string, book: DreBook = "80"): Promise<T> {
  return getJson<T>(`${dreRoot(book)}/${path}`);
}

export function fetchDreDesk(book: DreBook = "80"): Promise<DreDesk> {
  return getJson<DreDesk>(dreRoot(book));
}

export function fetchPositionList(params?: { q?: string; slice?: string }, book: DreBook = "80"): Promise<DrePositionList> {
  const search = new URLSearchParams();
  if (params?.q) search.set("q", params.q);
  if (params?.slice) search.set("slice", params.slice);
  const suffix = search.toString() ? `?${search.toString()}` : "";
  return getJson<DrePositionList>(`${dreRoot(book)}/positions${suffix}`);
}

export function fetchPosition(positionId: string, asOf?: string | null, book: DreBook = "80"): Promise<DrePositionState> {
  const search = new URLSearchParams();
  if (asOf) search.set("as_of", asOf);
  const suffix = search.toString() ? `?${search.toString()}` : "";
  return getJson<DrePositionState>(`${dreRoot(book)}/positions/${encodeURIComponent(positionId)}${suffix}`);
}

export function fetchDecision(tradeId: string, asOf?: string | null, book: DreBook = "80"): Promise<DrevoDecision> {
  const search = new URLSearchParams();
  if (asOf) search.set("as_of", asOf);
  const suffix = search.toString() ? `?${search.toString()}` : "";
  return getJson<DrevoDecision>(`${dreRoot(book)}/decision/${encodeURIComponent(tradeId)}${suffix}`);
}

export type DrevoDecision = {
  schema?: string;
  product?: string;
  trace_id?: string;
  structural_status?: string;
  decision_status?: string;
  execution_authorized?: boolean;
  execution_enabled?: boolean;
  policy_status?: string;
  reason_codes?: string[];
  positman_ref?: Record<string, unknown>;
  execution_boundary?: Record<string, unknown>;
  note?: string;
};

export type DreDesk = {
  product?: string;
  live_execution?: boolean;
  submits?: boolean;
  phase3_is_execution_policy?: boolean;
  live_feed?: string;
  hold_reason_intact?: string;
  note?: string;
  objective?: {
    id?: string;
    status?: string;
    calculus?: string;
    ssot?: string;
    eventual_form?: string;
  };
  trade_breakdown?: {
    status?: string;
    n?: number | null;
    W?: number | null;
    L?: number | null;
    S_display?: string | null;
    universe?: string;
    note?: string;
    detail?: string;
  };
  stratum?: {
    status?: string;
    book_n?: number | null;
    live_feed?: string;
    dataset_version?: string | null;
    universe?: string;
    note?: string;
    detail?: string;
  };
};

export type DreListRow = {
  position_id: string;
  trade_id?: string;
  ticker?: string;
  sport?: string;
  game?: string;
  home_team?: string;
  away_team?: string;
  team?: string;
  side?: string;
  position_label?: string;
  entry_price_cents?: number | null;
  entry_timestamp?: string | null;
  last_observed_price_cents?: number | null;
  last_observed_at?: string | null;
  slice?: string | null;
  quarter?: number | null;
  game_date?: string | null;
  dataset_split?: string | null;
  mode?: string;
  live_feed?: string;
  position_status?: string;
};

export type DrePositionList = {
  schema_version?: string;
  mode?: string;
  live_feed?: string;
  book_n?: number;
  n?: number;
  positions: DreListRow[];
  note?: string;
};

export type AvailabilityCell = {
  value?: unknown;
  availability?: string;
  detail?: string;
};

export type EvidenceEvent = {
  event: string;
  timestamp?: string | null;
  market_price_cents?: number | null;
  austin_conditional_ev_cents?: number | null;
  source?: string;
  note?: string;
};

export type DrePositionState = {
  schema_version: string;
  mode: string;
  position_id: string;
  as_of: string | null;
  generated_at?: string;
  live_feed?: string;
  live_execution?: boolean;
  submits?: boolean;
  position?: {
    game?: string;
    ticker?: string;
    sport?: string;
    team?: string;
    opponent?: string;
    side?: string;
    position_label?: string;
    entry_price_cents?: number | null;
    entry_timestamp?: string | null;
    quantity?: number | null;
    current_price_cents?: number | null;
    current_timestamp?: string | null;
    price_change_cents?: number | null;
    unrealized_pnl_cents?: number | null;
    unrealized_pnl_basis?: string;
    period?: number | string | null;
    clock?: string | null;
    home_score?: number | null;
    away_score?: number | null;
    position_status?: string;
    slice?: string | null;
    live_feed?: string;
    as_of?: string | null;
  } | null;
  trade_context?: Record<string, unknown> | null;
  live_state?: Record<string, unknown> | null;
  dynamic_risk?: {
    observation_state?: string;
    insufficient_support?: boolean;
    hold_reason_status?: string;
    dynamic_risk_class?: string;
    austin_conditional_ev?: number | null;
    change_from_entry?: number | null;
    historical_support?: string | null;
    reason?: string;
    unresolved?: string[];
    ev_blocks?: Record<string, Record<string, unknown>>;
    note?: string;
  };
  intervention?: {
    authorized?: boolean;
    policy_id?: string;
    policy_status?: string;
    current_action?: string;
    action_reason?: string;
    execution?: string;
    execution_enabled?: boolean;
  };
  evidence_timeline?: EvidenceEvent[];
  future_state_legend?: { state: string; availability: string }[];
  chart?: {
    entry_cents?: number;
    loss_barrier_cents?: number;
    as_of?: string | null;
    path?: { t?: string; price_cents?: number | null }[];
  };
  freshness?: Record<string, unknown>;
  provenance?: Record<string, unknown>;
};
