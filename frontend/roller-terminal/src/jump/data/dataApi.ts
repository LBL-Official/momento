import { apiFetch } from "../../api/base";

export type DataNode = {
  id: string;
  label: string;
  owner: string;
  availability: string;
  payload?: unknown;
  children?: DataNode[];
};

export type JumpContext = {
  identity?: { trade_id?: string; ticker?: string; event_id?: string; game_id?: string };
  as_of?: string | null;
  Austin?: Record<string, unknown>;
  Choosin?: Record<string, unknown>;
  Ballhog?: Record<string, unknown>;
  TKUltra?: Record<string, unknown>;
  Vital?: Record<string, unknown>;
  game_state?: Record<string, unknown>;
  market_state?: Record<string, unknown>;
  lineage?: Record<string, unknown>;
  source_health?: Record<string, string>;
  universes?: Record<string, { id: string; n: number }>;
  tree?: { nodes: DataNode[] };
  live_execution?: boolean;
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

export async function getDataContext(tradeId: string, asOf?: string): Promise<JumpContext> {
  const q = asOf ? `?as_of=${encodeURIComponent(asOf)}` : "";
  const res = await apiFetch(`/jump/data/context/${encodeURIComponent(tradeId)}${q}`);
  return parse(res);
}

export async function postDataQuery(capability: string, extra: Record<string, unknown> = {}) {
  const res = await apiFetch("/jump/data/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ capability, ...extra }),
  });
  return parse(res);
}

export async function getLineage(resourceId: string, extra: Record<string, string> = {}) {
  const params = new URLSearchParams();
  Object.entries(extra).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  const q = params.toString();
  const res = await apiFetch(`/jump/data/lineage/${encodeURIComponent(resourceId)}${q ? `?${q}` : ""}`);
  return parse(res);
}

export async function postExport(datasetId: string) {
  const res = await apiFetch("/jump/data/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset_id: datasetId }),
  });
  return parse(res);
}

export async function getSources() {
  const res = await apiFetch("/jump/data/sources");
  return parse(res);
}

export const DEFAULT_TRADE = "f84fd059fc0e1429";
