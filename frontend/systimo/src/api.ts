import type {
  ArtifactRow,
  ActionRow,
  AgentRow,
  AgentRunRow,
  DatasetRow,
  GraphPayload,
  QueryResponse,
  SystimoConnection,
  SystimoHealth,
  SystimoSystem,
  SystimoTree,
} from "./types";

const API_BASE = "/api";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  const body = (await res.json()) as T & { detail?: unknown };
  if (!res.ok) {
    const detail = body.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail && typeof detail === "object" && "message" in detail
          ? String((detail as { message: string }).message)
          : `GET ${path} failed`;
    throw new Error(message);
  }
  return body;
}

async function postJson<T>(path: string, payload: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = (await res.json()) as T & { detail?: unknown };
  if (!res.ok) {
    const detail = body.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail && typeof detail === "object" && "message" in detail
          ? String((detail as { message: string }).message)
          : `POST ${path} failed`;
    throw new Error(message);
  }
  return body;
}

export const api = {
  health: () => getJson<SystimoHealth>("/systimo/health"),
  systems: () => getJson<{ systems: SystimoSystem[] }>("/systimo/systems"),
  connections: () => getJson<{ connections: SystimoConnection[] }>("/systimo/connections"),
  tree: () => getJson<SystimoTree>("/systimo/tree"),
  graph: () => getJson<GraphPayload>("/systimo/graph"),
  datasets: () => getJson<{ datasets: DatasetRow[] }>("/systimo/datasets"),
  artifacts: () => getJson<{ artifacts: ArtifactRow[] }>("/systimo/artifacts"),
  actions: () => getJson<{ actions: ActionRow[] }>("/systimo/actions"),
  agents: () => getJson<{ agents: AgentRow[]; runs: AgentRunRow[] }>("/systimo/agents"),
  refresh: () => postJson<{ ok: boolean; checked: number }>("/systimo/refresh", {}),
  query: (query_type: string, system: string, extra: Record<string, string> = {}) =>
    postJson<QueryResponse>("/systimo/query", { query_type, system, ...extra }),
  traces: () => getJson<{ traces: Array<Record<string, string>>; n: number }>("/systimo/traces"),
  trace: (traceId: string) => getJson<Record<string, unknown>>(`/systimo/traces/${traceId}`),
  orchestra: (tradeId: string, asOf?: string) => {
    const suffix = asOf ? `?as_of=${encodeURIComponent(asOf)}` : "";
    return getJson<Record<string, unknown>>(`/systimo/orchestra/context/${encodeURIComponent(tradeId)}${suffix}`);
  },
  saveArtifact: (queryId: string, kind: "json" | "md") =>
    postJson<{ artifact_id: string }>(`/systimo/query/${queryId}/artifact`, { kind }),
  dryRun: (actionId: string) =>
    postJson<{ run_id: string; status: string }>(`/systimo/actions/${actionId}/dry-run`, {}),
  topology: () =>
    getJson<{
      status: string;
      services: Array<Record<string, string>>;
      bots: Array<Record<string, string>>;
      instances: Array<Record<string, string>>;
    }>("/systimo/topology"),
  plan: (scope: string) => getJson<{ services: string[]; arms_trading: boolean }>(`/systimo/plan?scope=${scope}`),
  session: (sourceNodeId: string, callerSessionId?: string) =>
    postJson<{ session_id: string; quadrant_id: string; scope_level: string }>("/systimo/scope/sessions", {
      source_node_id: sourceNodeId,
      caller_session_id: callerSessionId,
    }),
  endpoints: (sessionId: string) =>
    getJson<{ endpoints: Array<Record<string, unknown>>; shared: Array<Record<string, unknown>>; trading_armed: boolean }>(
      `/systimo/runtime/endpoints?session_id=${encodeURIComponent(sessionId)}`,
    ),
  bots: (sessionId: string) =>
    getJson<{ bots: Array<Record<string, string>>; trading_armed: boolean }>(
      `/systimo/bots?session_id=${encodeURIComponent(sessionId)}`,
    ),
};
