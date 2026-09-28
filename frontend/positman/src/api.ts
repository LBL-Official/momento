export class PositmanError extends Error {
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
  throw new PositmanError(res.status, String(message), code);
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

export type PositmanBook = "78" | "80";

function positmanRoot(book: PositmanBook): string {
  return book === "78" ? "/api/positman-first78" : "/api/positman";
}

export function fetchHealth(book: PositmanBook = "80"): Promise<PositmanHealth> {
  return getJson<PositmanHealth>(`${positmanRoot(book)}/health`);
}

export function fetchSources(book: PositmanBook = "80"): Promise<Record<string, unknown>> {
  return getJson<Record<string, unknown>>(`${positmanRoot(book)}/sources`);
}

export function fetchState(tradeId: string, asOf?: string | null, book: PositmanBook = "80"): Promise<Record<string, unknown>> {
  return getJson<Record<string, unknown>>(`${positmanRoot(book)}/state/${encodeURIComponent(tradeId)}${stamp(asOf)}`);
}

export function fetchDecision(tradeId: string, asOf?: string | null, book: PositmanBook = "80"): Promise<Record<string, unknown>> {
  const root = book === "78" ? "/api/dre-first78" : "/api/dre";
  return getJson<Record<string, unknown>>(`${root}/decision/${encodeURIComponent(tradeId)}${stamp(asOf)}`);
}

export function fetchTrace(traceId: string, book: PositmanBook = "80"): Promise<Record<string, unknown>> {
  return getJson<Record<string, unknown>>(`${positmanRoot(book)}/trace/${encodeURIComponent(traceId)}`);
}

export function fetchPositions(book: PositmanBook = "80"): Promise<{ positions?: TradeOption[] }> {
  const root = book === "78" ? "/api/ballhog-first78" : "/api/ballhog";
  return getJson<{ positions?: TradeOption[] }>(`${root}/positions`);
}

function stamp(asOf?: string | null): string {
  const search = new URLSearchParams();
  if (asOf) search.set("as_of", asOf);
  const query = search.toString();
  return query ? `?${query}` : "";
}

export function fetchPlan(tradeId: string, asOf?: string | null, book: PositmanBook = "80"): Promise<PositmanPlan> {
  return getJson<PositmanPlan>(`${positmanRoot(book)}/plan/${encodeURIComponent(tradeId)}${stamp(asOf)}`);
}

export type TradeOption = {
  trade_id?: string;
  game?: string;
  team?: string;
  ticker?: string;
};

export function postPlan(tradeId: string, asOf?: string | null): Promise<PositmanPlan> {
  return postJson<PositmanPlan>("/api/positman/plan", { trade_id: tradeId, as_of: asOf || undefined });
}

export type PositmanHealth = {
  ok: boolean;
  product: string;
  live_execution: boolean;
  execution_enabled: boolean;
  submits: boolean;
  note?: string;
};

export type PositmanPlan = {
  schema?: string;
  product?: string;
  trace_id?: string;
  trade_id?: string;
  as_of?: string | null;
  match_status?: string;
  risk_intent?: string | null;
  requested_reduction_qty?: number | null;
  requested_rho?: unknown;
  current_exposure?: number | null;
  target_exposure?: unknown;
  route_preference?: string | null;
  position_route?: string;
  planned_qty?: number | null;
  plan_status?: string;
  reason_codes?: string[];
  quantity_source?: string;
  route_source?: string;
  execution_enabled?: boolean;
  live_execution?: boolean;
  A_contract?: string | null;
  B_contract?: string | null;
  identity?: Record<string, unknown>;
  route_economic_context?: Record<string, unknown>;
};
