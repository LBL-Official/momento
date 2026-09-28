import { apiFetch } from "../../api/base";

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

export type WarehouseRecord = {
  id: string;
  display_name: string;
  sport: string;
  jump_sport: string;
  status: string;
  source_uri: string;
  storage_type: string;
  query_adapter: string;
  read_only: boolean;
  season: string;
  description: string;
  unavailable_reason?: string | null;
  manifest?: Record<string, unknown> | null;
};

export type WarehouseTable = {
  name: string;
  logical_name: string;
  kind: string;
  status: string;
  row_count: number;
  partitioned: boolean;
  pit_field?: string | null;
  pit_status?: string | null;
  used_by?: string[];
  sort?: string[];
};

export type WarehouseColumn = {
  name: string;
  type: string;
  nullable: boolean;
  description?: string;
  pit?: boolean;
};

export type TableDetail = {
  warehouse_id: string;
  name: string;
  logical_name: string;
  kind: string;
  status: string;
  row_count: number;
  partitioned: boolean;
  months?: { month: string; path: string; rows: number; bytes: number }[];
  pit_field?: string | null;
  pit_status?: string | null;
  observation_basis?: string;
  used_by?: string[];
  sort?: string[];
  columns: WarehouseColumn[];
  source_uri: string;
};

export type RowFilter = { column: string; op: string; value?: string };

export type RowPage = {
  warehouse_id: string;
  table: string;
  columns: string[];
  rows: Record<string, unknown>[];
  limit: number;
  page: number;
  offset: number;
  returned: number;
  filtered_row_count: number;
  table_row_count: number;
  sort?: string | null;
  order?: string;
};

export type SavedQuery = {
  id: string;
  kind: string;
  warehouse_id: string;
  name: string;
  sql: string;
  description?: string;
  materialized?: boolean;
};

export type RelationshipGraph = {
  warehouse_id: string;
  nodes: { id: string; label: string; x: number; y: number }[];
  edges: {
    id: string;
    from_table: string;
    from_column: string;
    to_table: string;
    to_column: string;
    cardinality: string;
    status: string;
    origin: string;
    trusted?: boolean;
  }[];
  candidates: {
    id: string;
    from_table: string;
    from_column: string;
    to_table: string;
    to_column: string;
    status: string;
    trusted?: boolean;
    note?: string;
  }[];
};

export async function listWarehouses(): Promise<{ warehouses: WarehouseRecord[] }> {
  const res = await apiFetch("/jump/warehouses");
  return parse(res);
}

export async function getWarehouse(
  id: string
): Promise<WarehouseRecord & { tables?: WarehouseTable[]; unavailable?: boolean }> {
  const res = await apiFetch(`/jump/warehouses/${encodeURIComponent(id)}`);
  return parse(res);
}

export async function getWarehouseTables(id: string): Promise<{ tables: WarehouseTable[] }> {
  const res = await apiFetch(`/jump/warehouses/${encodeURIComponent(id)}/tables`);
  return parse(res);
}

export async function getWarehouseTable(id: string, table: string): Promise<TableDetail> {
  const res = await apiFetch(`/jump/warehouses/${encodeURIComponent(id)}/tables/${encodeURIComponent(table)}`);
  return parse(res);
}

export async function getTableRows(
  id: string,
  table: string,
  params: {
    limit?: number;
    page?: number;
    sort?: string;
    order?: string;
    columns?: string[];
    filters?: RowFilter[];
  }
): Promise<RowPage> {
  const q = new URLSearchParams();
  q.set("limit", String(params.limit ?? 100));
  q.set("page", String(params.page ?? 1));
  if (params.sort) q.set("sort", params.sort);
  if (params.order) q.set("order", params.order);
  if (params.columns?.length) q.set("columns", params.columns.join(","));
  if (params.filters?.length) q.set("filters", JSON.stringify(params.filters));
  const res = await apiFetch(
    `/jump/warehouses/${encodeURIComponent(id)}/tables/${encodeURIComponent(table)}/rows?${q.toString()}`
  );
  return parse(res);
}

export async function getTableStats(id: string, table: string, compute = false): Promise<Record<string, unknown>> {
  const suffix = compute ? "?compute=1" : "";
  const res = await apiFetch(
    `/jump/warehouses/${encodeURIComponent(id)}/tables/${encodeURIComponent(table)}/stats${suffix}`
  );
  return parse(res);
}

export async function getTableLineage(id: string, table: string): Promise<Record<string, unknown>> {
  const res = await apiFetch(
    `/jump/warehouses/${encodeURIComponent(id)}/tables/${encodeURIComponent(table)}/lineage`
  );
  return parse(res);
}

export async function getDictionary(id: string): Promise<Record<string, unknown>> {
  const res = await apiFetch(`/jump/warehouses/${encodeURIComponent(id)}/dictionary`);
  return parse(res);
}

export async function getPhysicalFiles(id: string): Promise<Record<string, unknown>> {
  const res = await apiFetch(`/jump/warehouses/${encodeURIComponent(id)}/files`);
  return parse(res);
}

export async function getRelationships(id: string): Promise<RelationshipGraph> {
  const res = await apiFetch(`/jump/warehouses/${encodeURIComponent(id)}/relationships`);
  return parse(res);
}

export async function saveRelationshipLayout(
  id: string,
  layout: Record<string, { x: number; y: number }>
): Promise<RelationshipGraph> {
  const res = await apiFetch(`/jump/warehouses/${encodeURIComponent(id)}/relationships/layout`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ layout }),
  });
  return parse(res);
}

export async function runWarehouseQuery(
  id: string,
  sql: string,
  limit = 100
): Promise<{ columns: string[]; rows: Record<string, unknown>[]; returned: number; sql: string }> {
  const res = await apiFetch(`/jump/warehouses/${encodeURIComponent(id)}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sql, limit }),
  });
  return parse(res);
}

export async function refreshWarehouse(id: string): Promise<Record<string, unknown>> {
  const res = await apiFetch(`/jump/warehouses/${encodeURIComponent(id)}/refresh`, { method: "POST" });
  return parse(res);
}

export async function validateWarehouse(id: string): Promise<Record<string, unknown>> {
  const res = await apiFetch(`/jump/warehouses/${encodeURIComponent(id)}/validate`, { method: "POST" });
  return parse(res);
}

export async function listSavedQueries(warehouseId?: string): Promise<{ queries: SavedQuery[] }> {
  const suffix = warehouseId ? `?warehouse_id=${encodeURIComponent(warehouseId)}` : "";
  const res = await apiFetch(`/jump/queries${suffix}`);
  return parse(res);
}

export async function createSavedQuery(body: {
  warehouse_id: string;
  name: string;
  sql: string;
  description?: string;
}): Promise<SavedQuery> {
  const res = await apiFetch("/jump/queries", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parse(res);
}

export async function patchSavedQuery(id: string, body: Partial<SavedQuery>): Promise<SavedQuery> {
  const res = await apiFetch(`/jump/queries/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parse(res);
}

export async function deleteSavedQuery(id: string): Promise<{ status: string }> {
  const res = await apiFetch(`/jump/queries/${encodeURIComponent(id)}`, { method: "DELETE" });
  return parse(res);
}

export async function listViews(id: string): Promise<{ views: SavedQuery[] }> {
  const res = await apiFetch(`/jump/warehouses/${encodeURIComponent(id)}/views`);
  return parse(res);
}

export async function createView(
  id: string,
  body: { name: string; sql: string; description?: string }
): Promise<SavedQuery> {
  const res = await apiFetch(`/jump/warehouses/${encodeURIComponent(id)}/views`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parse(res);
}
