import type {
  AskedSixPage,
  AustinQueryResult,
  AustinReplay,
  Dallas,
  NbaPath,
  ExecutionValidationPage,
  PairedReplay,
  ResearchBook,
  SugarlandPage,
  Universe,
} from "./types";

export class UniverseError extends Error {
  status: number;
  payload: Universe | null;

  constructor(status: number, message: string, payload: Universe | null) {
    super(message);
    this.status = status;
    this.payload = payload;
  }
}

async function getJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, { headers: { Accept: "application/json" }, ...init });
  const body = (await res.json().catch(() => null)) as T | { detail?: Universe | string } | null;
  if (!res.ok) {
    const detail = body && typeof body === "object" && "detail" in body ? body.detail : null;
    const payload = detail && typeof detail === "object" ? (detail as Universe) : null;
    const message =
      payload?.message ||
      (typeof detail === "string" ? detail : null) ||
      `HTTP ${res.status} ${path}`;
    throw new UniverseError(res.status, message, payload);
  }
  return body as T;
}

export function fetchUniverse(): Promise<Universe> {
  return getJson<Universe>("/api/choosin-texas/universe");
}

export function fetchFirst78(variant: "67" | "65" | "60"): Promise<Record<string, unknown>> {
  return getJson<Record<string, unknown>>(`/api/choosin-texas/first78?variant=${variant}`);
}

export function fetchUniverse60(): Promise<Universe> {
  return getJson<Universe>("/api/choosin-texas/universe-60");
}

export function fetchPairedReplay(): Promise<PairedReplay> {
  return getJson<PairedReplay>("/api/choosin-texas/paired-replay");
}

export function fetchExecutionValidation(): Promise<ExecutionValidationPage> {
  return getJson<ExecutionValidationPage>("/api/choosin-texas/paired-execution-validation");
}

export function fetchUniverse75(): Promise<Universe> {
  return getJson<Universe>("/api/choosin-texas/universe-75");
}

export function fetchNbaPath(): Promise<NbaPath> {
  return getJson<NbaPath>("/api/choosin-texas/nba-path");
}

export function fetchNbaPath75(): Promise<NbaPath> {
  return getJson<NbaPath>("/api/choosin-texas/nba-path-75");
}

export function fetchUniverse77(): Promise<Universe> {
  return getJson<Universe>("/api/choosin-texas/universe-77");
}

export function fetchNbaPath77(): Promise<NbaPath> {
  return getJson<NbaPath>("/api/choosin-texas/nba-path-77");
}

export function fetchAskedSix(): Promise<AskedSixPage> {
  return getJson<AskedSixPage>("/api/choosin-texas/asked-six");
}

export function fetchUniverse81(): Promise<Universe> {
  return getJson<Universe>("/api/choosin-texas/universe-81");
}

export function fetchUniverse83(): Promise<Universe> {
  return getJson<Universe>("/api/choosin-texas/universe-83");
}

export function fetchDallas(): Promise<Dallas> {
  return getJson<Dallas>("/api/choosin-texas/dallas");
}

export function fetchBook(): Promise<ResearchBook> {
  return getJson<ResearchBook>("/api/choosin-texas/book");
}

export function fetchSugarland(): Promise<SugarlandPage> {
  return getJson<SugarlandPage>("/api/choosin-texas/sugarland");
}

export function fetchKaty(): Promise<Record<string, unknown>> {
  return getJson<Record<string, unknown>>("/api/choosin-texas/katy");
}

export function fetchKatyExperiment(id: string): Promise<Record<string, unknown>> {
  return getJson<Record<string, unknown>>(`/api/choosin-texas/katy/${encodeURIComponent(id)}`);
}

export function fetchAustin<T>(path: string): Promise<T> {
  return getJson<T>(`/api/austin/${path}`);
}

async function postAustin(path: string, body: Record<string, unknown>): Promise<AustinQueryResult> {
  const res = await fetch(`/api/austin/${path}`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = (await res.json().catch(() => null)) as AustinQueryResult | { detail?: { message?: string } } | null;
  if (!res.ok) {
    const detail = payload && typeof payload === "object" && "detail" in payload ? payload.detail : null;
    const message =
      (detail && typeof detail === "object" && detail.message) ||
      `HTTP ${res.status} /api/austin/${path}`;
    throw new UniverseError(res.status, String(message), null);
  }
  return payload as AustinQueryResult;
}

export function postAustinQuery(body: Record<string, unknown>): Promise<AustinQueryResult> {
  return postAustin("query", body);
}

export function postAustinHistorical(body: Record<string, unknown>): Promise<AustinQueryResult> {
  return postAustin("query/historical", body);
}

export function fetchAustinReplay(tradeId: string): Promise<AustinReplay> {
  return getJson<AustinReplay>(`/api/austin/replay/${encodeURIComponent(tradeId)}`);
}

export function fetchLubbock<T>(): Promise<T> {
  return getJson<T>("/api/choosin-texas/lubbock", { cache: "no-store" });
}

export function fetchAustinMoments(gameId: string, side: string): Promise<{ marks?: { label: string; timestamp_utc: string; price_cents?: number; quarter?: number; seconds_remaining?: number }[] }> {
  const q = new URLSearchParams({ side });
  return getJson(`/api/austin/games/${encodeURIComponent(gameId)}/moments?${q.toString()}`);
}

export function fetchAustin78<T>(path: string): Promise<T> {
  return getJson<T>(`/api/austin-first78/${path}`);
}

async function postAustin78(path: string, body: Record<string, unknown>): Promise<AustinQueryResult> {
  const res = await fetch(`/api/austin-first78/${path}`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = (await res.json().catch(() => null)) as AustinQueryResult | { detail?: { message?: string } } | null;
  if (!res.ok) {
    const detail = payload && typeof payload === "object" && "detail" in payload ? payload.detail : null;
    const message =
      (detail && typeof detail === "object" && detail.message) ||
      `HTTP ${res.status} /api/austin-first78/${path}`;
    throw new UniverseError(res.status, String(message), null);
  }
  return payload as AustinQueryResult;
}

export function postAustin78Query(body: Record<string, unknown>): Promise<AustinQueryResult> {
  return postAustin78("query", body);
}

export function postAustin78Historical(body: Record<string, unknown>): Promise<AustinQueryResult> {
  return postAustin78("query/historical", body);
}

export function fetchAustin78Replay(tradeId: string): Promise<AustinReplay> {
  return getJson<AustinReplay>(`/api/austin-first78/replay/${encodeURIComponent(tradeId)}`);
}

export function fetchAustin78Moments(gameId: string, side: string): Promise<{ marks?: { label: string; timestamp_utc: string; price_cents?: number; quarter?: number; seconds_remaining?: number }[] }> {
  const q = new URLSearchParams({ side });
  return getJson(`/api/austin-first78/games/${encodeURIComponent(gameId)}/moments?${q.toString()}`);
}
