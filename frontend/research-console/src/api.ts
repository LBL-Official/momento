const TOKEN_KEY = "momento_research_token";

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || "momento-local";
}

export function setToken(t: string) {
  localStorage.setItem(TOKEN_KEY, t);
}

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("x-research-token", getToken());
  if (init.body && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  const res = await fetch(path, { ...init, headers });
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => req<{ ok: boolean; production: number }>("/api/health"),
  system: () => req<Record<string, unknown>>("/api/system"),
  datasets: () => req<Dataset[]>("/api/datasets"),
  strategies: () => req<Strategy[]>("/api/strategies"),
  models: () => req<Model[]>("/api/models"),
  candidates: () => req<Candidate[]>("/api/candidates"),
  experiments: () => req<Experiment[]>("/api/experiments"),
  experiment: (id: string) => req<Experiment>(`/api/experiments/${id}`),
  hypotheses: (id: string) => req<Hypothesis[]>(`/api/experiments/${id}/hypotheses`),
  createExperiment: (body: unknown) =>
    req<Experiment>("/api/experiments", { method: "POST", body: JSON.stringify(body) }),
  runExperiment: (id: string) =>
    req<Job>(`/api/experiments/${id}/run`, { method: "POST", body: "{}" }),
  reproduce: (id: string) =>
    req<Experiment>(`/api/experiments/${id}/reproduce`, { method: "POST", body: "{}" }),
  promote: (id: string, to: string, reason: string) =>
    req<unknown>(`/api/experiments/${id}/promote`, {
      method: "POST",
      body: JSON.stringify({ to, reason }),
    }),
  jobs: () => req<Job[]>("/api/jobs"),
  job: (id: string) => req<Job>(`/api/jobs/${id}`),
  cancelJob: (id: string) =>
    req<Job>(`/api/jobs/${id}/cancel`, { method: "POST", body: "{}" }),
  features: () => req<{ available: boolean; values?: Record<string, string[]> }>("/api/features"),
  parameterCatalog: () => req<ParamDoc[]>("/api/parameter-catalog"),
  promotions: (id: string) => req<Promotion[]>(`/api/experiments/${id}/promotions`),
  orchestration: () => req<Record<string, unknown>>("/api/orchestration"),
  estimate: (parameters: ParameterInput[]) =>
    req<{ hypotheses: number }>("/api/estimate", {
      method: "POST",
      body: JSON.stringify({ parameters }),
    }),
  prospective83: () => req<Record<string, unknown>>("/api/prospective83"),
};

export type Promotion = {
  id: string;
  experiment_id: string;
  from_status: string;
  to_status: string;
  reason: string;
  created_at: string;
  created_by: string;
};

export type ParamDoc = { name: string; group: string; kind: string; notes: string };

export type ParameterInput = {
  name: string;
  values: string[];
  kind?: string;
  min?: number | null;
  max?: number | null;
  step?: number | null;
};

export type Dataset = {
  id: string;
  version: string;
  name: string;
  event_definition: string;
  source: string;
  features_sqlite?: string | null;
  game_count?: number | null;
  capabilities: Record<string, boolean>;
  quality: Record<string, unknown>;
  provenance: Record<string, unknown>;
  status: string;
};

export type Strategy = {
  id: string;
  version: string;
  name: string;
  description: string;
  research_status: string;
  production_status: string;
};

export type Model = {
  id: string;
  strategy_id: string;
  version: string;
  dataset_id: string;
  health: string;
  status: string;
};

export type Candidate = {
  id: string;
  experiment_id: string;
  condition: string;
  status: string;
  payload: Record<string, unknown>;
};

export type Experiment = {
  id: string;
  status: string;
  definition: {
    name: string;
    description: string;
    dataset_id: string;
    dataset_version: string;
    strategy_id: string;
    strategy_version: string;
    feature_set: string;
    train_before: string;
    val_before: string;
    test_end?: string | null;
    search_method: string;
    parameters: { name: string; values: string[] }[];
    parent_experiment_id?: string | null;
    execution_model: string;
    fees_cents: number;
    slippage_cents: number;
    position_qty?: number | null;
    capital_cents: number;
    fdr_method: string;
    fdr_alpha: number;
    min_train: number;
    min_val: number;
    min_test: number;
    random_seed: number;
    created_by: string;
  };
  created_at: string;
  updated_at: string;
  hypothesis_count: number;
  result_summary?: Record<string, unknown> | null;
  artifact_dir?: string | null;
};

export type Job = {
  id: string;
  experiment_id: string;
  status: string;
  progress_done: number;
  progress_total: number;
  current_hypothesis?: string | null;
  error?: string | null;
  logs: string[];
};

export type Hypothesis = {
  rank?: number;
  condition: string;
  train?: Split;
  validation?: Split;
  test?: Split;
  train_n?: number;
  val_n?: number;
  test_n?: number;
  train_ev?: number;
  val_ev?: number;
  test_ev?: number;
  q_value?: number | null;
  classification?: string;
  equity?: { date: string; cumulative_usd: number; split: string }[];
};

export type Split = {
  n?: number;
  win_rate?: number | null;
  ev_cents?: number | null;
  sharpe?: number | null;
  pnl_usd?: number;
};
