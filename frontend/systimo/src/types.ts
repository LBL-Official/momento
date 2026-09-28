export type SystimoHealth = {
  ok: boolean;
  product: string;
  live_execution: boolean;
  csv_valid: boolean;
  csv_error: string | null;
  row_counts: Record<string, number>;
  drift: Array<{ connection_id: string; reason: string; health: string }>;
  systems: number;
  connections: number;
  unavailable: number;
  position_management: string;
  note: string;
};

export type SystimoSystem = {
  system_id: string;
  name: string;
  product_name: string;
  domain: string;
  status: string;
  n_lock?: string;
  frontend_url: string;
  backend_package: string;
  api_namespace: string;
  canonical_role: string;
  description: string;
};

export type SystimoConnection = {
  connection_id: string;
  source_system_id: string;
  target_system_id: string;
  transport: string;
  permission: string;
  lifecycle: string;
  health: string;
  capability: string;
  expected_lock: string;
  notes: string;
  reason: string;
};

export type TreeSystem = {
  id: string;
  name: string;
  domain: string;
  reads: Array<{ connection_id: string; source: string; lifecycle: string; health: string }>;
  consumed_by: Array<{ connection_id: string; target: string; lifecycle: string; health: string }>;
};

export type SystimoTree = {
  generated_at: string;
  root: string;
  domains: Record<string, TreeSystem[]>;
};

export type GraphPayload = {
  generated_at: string;
  nodes: Array<{ id: string; name: string; domain: string }>;
  edges: Array<{
    id: string;
    source: string;
    target: string;
    lifecycle: string;
    health: string;
    permission: string;
  }>;
};

export type DatasetRow = {
  dataset_id: string;
  owner_system_id: string;
  name: string;
  universe: string;
  n_expected: string;
  location: string;
  notes: string;
};

export type ArtifactRow = {
  artifact_id: string;
  query_id: string;
  answer_id: string;
  format: string;
  checksum: string;
  created_at: string;
  rerun_of: string;
  path: string;
};

export type ActionRow = {
  action_id: string;
  action_type: string;
  target_system: string;
  status: string;
  dry_run_supported: string;
};

export type AgentRow = {
  agent_id: string;
  name: string;
  allowed_query_scopes: string;
  allowed_action_types: string;
  enabled: string;
};

export type AgentRunRow = {
  run_id: string;
  agent_id: string;
  status: string;
  started_at: string;
  proposed_action_ids: string;
};

export type QueryResponse = {
  query_id: string;
  answer_id: string;
  query_type: string;
  result: unknown;
  warnings: string[];
};

export const QUERY_TYPES = [
  "systems",
  "connections",
  "dependencies",
  "reverse_dependencies",
  "datasets",
  "interfaces",
  "health",
  "artifacts",
  "provenance",
  "paths",
  "path_back",
  "drift",
  "governance",
  "TRANSITION_TRACE",
  "CURRENT_POSITION_CHAIN",
  "POSITMAN_PLAN",
  "DREVO_DECISION",
  "TRANSITION_INTEGRITY",
  "TRANSITION_SOURCES",
  "UNRESOLVED_TRANSITIONS",
  "REJECTED_TRANSITIONS",
  "SOURCE_TO_DECISION_LINEAGE",
  "LATEST_STAGE",
  "ORCHESTRA_CONTEXT",
] as const;
