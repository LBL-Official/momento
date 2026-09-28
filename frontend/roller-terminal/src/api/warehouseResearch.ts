import { apiFetch } from "./base";
import type { ResearchQuestionJson } from "../v2/warehouse/researchQuestionFromDraft";
import type { TeFilters } from "../v2/workflow/types";

export type WarehouseExecuteOpts = {
  include_reference?: boolean;
  teFilters?: TeFilters;
  exposureUnit?: "GAME" | "TICKER" | "TEAM" | "EVENT";
  maxEntriesPerGame?: number;
  exposureEnforcementMode?: "strategy_enforced" | "results_verify_only";
};

export type WarehouseCompile = {
  status?: string;
  syntactic_errors?: string[];
  question?: ResearchQuestionJson;
  plan?: Record<string, unknown>;
  plan_hash?: string;
  capability?: {
    status?: string;
    required?: string[];
    satisfied?: string[];
    missing_data?: string[];
    missing_operations?: string[];
    matrix?: Record<string, string>;
  };
  observation_basis?: string;
  resolution?: string;
  pit_field?: string;
  compiler_version?: string;
  warehouse_version?: string;
  catalog_version?: string;
  identity_version?: string;
  source?: string;
  te_filters?: Record<string, unknown> | null;
  result?: Record<string, unknown> | null;
  results_contract?: WarehouseResultsContract | null;
  difference_count?: number;
};

export type WarehouseResultsContract = {
  research_question?: ResearchQuestionJson;
  plan_hash?: string;
  compiler_version?: string;
  warehouse_version?: string;
  identity_version?: string;
  catalog_version?: string;
  observation_basis?: string;
  resolution?: string;
  pit_field?: string;
  entry?: Array<Record<string, unknown>>;
  win_exit?: Array<Record<string, unknown>>;
  loss_exit?: Array<Record<string, unknown>>;
  terminal?: string;
  population?: number;
  classification?: Record<string, number>;
  statistics?: {
    population?: number;
    W?: number;
    L?: number;
    classified_n?: number;
    unresolved_n?: number;
    path_win_n?: number;
    path_loss_n?: number;
    terminal_win_n?: number;
    terminal_loss_n?: number;
    official_w_n?: number;
    official_l_n?: number;
    official_w_rate?: number | null;
    win_rate?: number | null;
    loss_rate?: number | null;
    reward_e4?: number | null;
    risk_e4?: number | null;
    rr?: number | null;
    rr_trade_mean?: number | null;
    ev_e4?: number | null;
    ev_status?: string;
    assumption?: string;
    basis?: string;
    not?: string[];
  };
  settlement_crosstab?: {
    held_yes?: number;
    held_no?: number;
    held_missing?: number;
    path_win?: number;
    path_loss?: number;
    terminal_win?: number;
    terminal_loss?: number;
    unresolved?: number;
    official_w?: number;
    official_l?: number;
  };
  te_scope?: {
    requested?: Record<string, unknown> | null;
    n_entry?: number;
    n_scoped?: number;
    n_dropped?: number;
  };
  exposure?: {
    status?: string;
    exposure_unit?: string;
    declared_unit?: string;
    max_entries_per_unit?: number | null;
    reason?: string;
    n_unique_games?: number | null;
    n_rows?: number | null;
    strategy_statistics_permitted?: boolean;
    enforcement_mode?: string;
    execution_enforced?: boolean;
    selection_policy?: string | null;
    n_unchanged?: boolean;
  };
  win_hold?: boolean;
  loss_hold?: boolean;
  coverage?: {
    nominal_universe?: { games?: number; markets?: number };
    executed_population?: number;
    exclusions?: Record<string, number>;
    missing_data?: string[];
    unsupported_operations?: string[];
    context?: Record<string, unknown>;
  };
  exclusions?: Record<string, number>;
  audit_rows?: Array<Record<string, unknown>>;
  reproducibility?: Record<string, unknown>;
  label?: string;
};

function warehouseBody(question: ResearchQuestionJson, opts?: WarehouseExecuteOpts): Record<string, unknown> {
  const payload: Record<string, unknown> = { question };
  if (opts?.teFilters) payload.te_filters = opts.teFilters;
  if (opts?.exposureUnit) payload.exposure_unit = opts.exposureUnit;
  if (opts?.maxEntriesPerGame != null) payload.max_entries_per_unit = opts.maxEntriesPerGame;
  if (opts?.exposureEnforcementMode) payload.exposure_enforcement_mode = opts.exposureEnforcementMode;
  if (opts?.include_reference) payload.include_reference = true;
  return payload;
}

export async function compileWarehouseResearch(
  question: ResearchQuestionJson,
  opts?: WarehouseExecuteOpts,
): Promise<WarehouseCompile> {
  const res = await apiFetch("/warehouse-research/compile", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(warehouseBody(question, opts)),
  });
  const body = (await res.json()) as WarehouseCompile & { detail?: string };
  if (!res.ok) throw new Error(body.detail || "Warehouse compile failed");
  return body;
}

export async function executeWarehouseResearch(
  question: ResearchQuestionJson,
  opts?: WarehouseExecuteOpts,
): Promise<WarehouseCompile> {
  const res = await apiFetch("/warehouse-research/execute", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(warehouseBody(question, opts)),
  });
  const body = (await res.json()) as WarehouseCompile & { detail?: string };
  if (!res.ok) throw new Error(body.detail || "Warehouse execute failed");
  return body;
}

export type WarehouseLab = {
  lab_id: string;
  folder: string;
  strategy_name: string;
  filename: string;
  created_at?: string;
  csv_sha256?: string;
  result_hash?: string;
  plan_hash?: string;
  warehouse_version?: string;
  status?: string;
  rows?: number | null;
  header_population?: number | null;
  population_matches_rows?: boolean;
};

export async function saveWarehouseLab(input: {
  name: string;
  folder?: string;
  labId?: string | null;
  question?: ResearchQuestionJson;
  payload: WarehouseCompile;
}): Promise<WarehouseLab> {
  const res = await apiFetch("/warehouse-research/labs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: input.name,
      folder: input.folder || "NBA",
      lab_id: input.labId || undefined,
      question: input.question,
      payload: input.payload,
    }),
  });
  const body = (await res.json()) as WarehouseLab & { detail?: string };
  if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Lab save failed");
  return body;
}

export async function listWarehouseLabs(folder?: string): Promise<{
  labs: WarehouseLab[];
  folders: string[];
  n: number;
}> {
  const q = folder ? `?folder=${encodeURIComponent(folder)}` : "";
  const res = await apiFetch(`/warehouse-research/labs${q}`);
  const body = (await res.json()) as { labs?: WarehouseLab[]; folders?: string[]; n?: number; detail?: string };
  if (!res.ok) throw new Error(body.detail || "Lab list failed");
  return { labs: body.labs || [], folders: body.folders || [], n: body.n || 0 };
}

export async function getWarehouseLab(labId: string): Promise<WarehouseLab> {
  const res = await apiFetch(`/warehouse-research/labs/${encodeURIComponent(labId)}`);
  const body = (await res.json()) as WarehouseLab & { detail?: string };
  if (!res.ok) throw new Error(body.detail || "Lab not found");
  return body;
}

export type DeskSettings = {
  schema_version?: string;
  bankroll_cents: number;
  allocation_bps: number;
  bankroll_dollars: number;
  allocation_pct: number;
  floor_cents?: number;
  target_cents?: number;
  floor_dollars: number;
  target_dollars: number;
  updated_at?: string;
  source?: string;
};

export async function getDeskSettings(): Promise<DeskSettings> {
  const res = await apiFetch("/warehouse-research/settings");
  const body = (await res.json()) as DeskSettings & { detail?: string };
  if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Settings load failed");
  return body;
}

export async function saveDeskSettings(input: {
  bankroll_dollars: number;
  allocation_pct: number;
}): Promise<DeskSettings> {
  const res = await apiFetch("/warehouse-research/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  const body = (await res.json()) as DeskSettings & { detail?: string };
  if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Settings save failed");
  return body;
}

export function warehouseLabCsvUrl(labId: string): string {
  return `/warehouse-research/labs/${encodeURIComponent(labId)}/csv`;
}

export async function downloadWarehouseLabCsv(labId: string, filename: string): Promise<void> {
  const res = await apiFetch(`/warehouse-research/labs/${encodeURIComponent(labId)}/csv`);
  if (!res.ok) throw new Error("CSV download failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
