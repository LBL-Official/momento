import type {
  BdrCatalog,
  BdrDocument,
  ConnectionPayload,
  HealthAggregate,
  HealthRow,
  LogicPayload,
  SystemRow,
  TkUltraAssess,
  TkUltraDesk,
  TkUltraHealth,
  TkUltraSources,
  TkUltraV0Assess,
  WarehouseQueryResult,
} from "./types";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`${path} ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function fetchSystems(): Promise<SystemRow[]> {
  const body = await getJson<{ systems: SystemRow[] }>("/api/momento/systems");
  return body.systems;
}

export async function fetchSystem(id: string): Promise<SystemRow> {
  return getJson<SystemRow>(`/api/momento/systems/${id}`);
}

export async function fetchLogic(id: string): Promise<LogicPayload> {
  return getJson<LogicPayload>(`/api/momento/systems/${id}/logic`);
}

export async function fetchSystemHealth(id: string): Promise<HealthRow> {
  return getJson<HealthRow>(`/api/momento/systems/${id}/health`);
}

export async function fetchHealth(): Promise<HealthAggregate> {
  return getJson<HealthAggregate>("/api/momento/health");
}

export async function fetchConnection(): Promise<ConnectionPayload> {
  return getJson<ConnectionPayload>("/api/momento/connection");
}

export async function runWarehouseQuery(
  warehouseId: string,
  sql: string,
  limit = 100,
): Promise<WarehouseQueryResult> {
  return postJson<WarehouseQueryResult>(`/api/jump/warehouses/${warehouseId}/query`, {
    sql,
    limit,
  });
}

export async function fetchIngestion(): Promise<Record<string, unknown>> {
  return getJson<Record<string, unknown>>("/api/momento/ingestion");
}

export async function fetchBdrCatalog(): Promise<BdrCatalog> {
  return getJson<BdrCatalog>("/api/momento/bdr");
}

export async function fetchBdrDocument(slug: string): Promise<BdrDocument> {
  return getJson<BdrDocument>(`/api/momento/bdr/${slug}`);
}

export async function fetchTkUltra(): Promise<TkUltraDesk> {
  return getJson<TkUltraDesk>("/api/momento/tk-ultra");
}

export async function fetchTkUltraAssess(fields: {
  wing_price: string;
  base_price: string;
  beta: string;
  wing_anchor: string;
  base_anchor: string;
  ticks_per_handle: string;
  pair?: string;
  corridor_cents?: string;
}): Promise<TkUltraAssess> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(fields)) {
    if (value) query.set(key, value);
  }
  const suffix = query.toString();
  return getJson<TkUltraAssess>(`/api/momento/tk-ultra/assess${suffix ? `?${suffix}` : ""}`);
}

async function postJson<T>(path: string, body: object): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    let extra = "";
    try {
      const err = (await response.json()) as { detail?: { message?: string; code?: string } | string };
      if (typeof err.detail === "string") extra = err.detail;
      else extra = err.detail?.message || err.detail?.code || "";
    } catch {
      extra = "";
    }
    throw new Error(`${path} ${response.status}${extra ? ` ${extra}` : ""}`);
  }
  return (await response.json()) as T;
}

export async function fetchTkUltraHealth(): Promise<TkUltraHealth> {
  return getJson<TkUltraHealth>("/api/momento/tk-ultra/health");
}

export async function fetchTkUltraSources(): Promise<TkUltraSources> {
  return getJson<TkUltraSources>("/api/momento/tk-ultra/sources");
}

export async function fetchTkUltra78(): Promise<TkUltraDesk> {
  return getJson<TkUltraDesk>("/api/momento/tk-ultra-first78");
}

export async function fetchTkUltra78Assess(fields: {
  wing_price: string;
  base_price: string;
  beta: string;
  wing_anchor: string;
  base_anchor: string;
  ticks_per_handle: string;
  pair?: string;
  corridor_cents?: string;
}): Promise<TkUltraAssess> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(fields)) {
    if (value) query.set(key, value);
  }
  const suffix = query.toString();
  return getJson<TkUltraAssess>(`/api/momento/tk-ultra-first78/assess${suffix ? `?${suffix}` : ""}`);
}

export async function fetchTkUltra78Health(): Promise<TkUltraHealth> {
  return getJson<TkUltraHealth>("/api/momento/tk-ultra-first78/health");
}

export async function postTkUltra78AssessV0(body: Record<string, string>): Promise<TkUltraV0Assess> {
  const payload: Record<string, string> = {};
  for (const [key, value] of Object.entries(body)) {
    if (value !== "") payload[key] = value;
  }
  return postJson<TkUltraV0Assess>("/api/momento/tk-ultra-first78/assess", payload);
}

export async function postTkUltraAssessV0(body: Record<string, string>): Promise<TkUltraV0Assess> {
  const payload: Record<string, string> = {};
  for (const [key, value] of Object.entries(body)) {
    if (value !== "") payload[key] = value;
  }
  return postJson<TkUltraV0Assess>("/api/momento/tk-ultra/assess", payload);
}
