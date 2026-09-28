export type StaxRoute = "overview" | "strategies" | "results" | "history" | "automation" | "library";

export type CanonicalUniverse = {
  sport_family?: string;
  league_set?: string[];
  seasons?: string[];
  date_from?: string | null;
  date_to?: string | null;
};

export type StaxMember = {
  member_id: string;
  position: number;
  display_id?: string;
  label?: string;
  save_id?: string | null;
  roller_object_id?: string | null;
  research_object_id?: string | null;
  question?: Record<string, unknown> | null;
  draft?: Record<string, unknown> | null;
  universe?: CanonicalUniverse;
  question_hash?: string | null;
  query_hash?: string | null;
  dataset_hash?: string | null;
  status?: string;
};

export type StaxHead = {
  stax_id: string;
  name: string;
  description?: string;
  universe?: CanonicalUniverse | null;
  timezone?: string;
  automation_enabled?: boolean;
  automation_schedule?: string;
  latest_version?: string | null;
  latest_status?: string | null;
  last_run_at?: string | null;
  next_run_at?: string | null;
  strategy_count?: number;
  live_execution?: boolean;
};

export type StaxVersion = {
  stax_id?: string;
  version: string;
  kind?: string;
  parent_version?: string | null;
  created_at?: string;
  executed_at?: string | null;
  status?: string;
  definition_hash?: string;
  dataset_fingerprint?: string;
  strategy_count?: number;
  completed_count?: number;
  failed_count?: number;
  sum_of_strategy_n?: number;
  sum_of_strategy_n_label?: string;
  universe?: CanonicalUniverse;
  members?: StaxMember[];
  results?: StaxMemberResult[];
  overlap?: StaxOverlap;
  provenance?: Record<string, unknown>;
  unchanged?: boolean;
};

export type StaxMemberResult = {
  member_id: string;
  status: string;
  error?: { code?: string; message?: string } | null;
  envelope?: Record<string, unknown> | null;
  summary?: {
    n?: number | null;
    path_rate?: number | null;
    terminal?: number | null;
    ev?: number | null;
    execution_status?: string;
    dataset_version?: string | null;
  };
};

export type StaxOverlap = {
  overlap_method?: string;
  shared_game_count?: number | null;
  pairwise?: Array<{ a: string; b: string; shared_game_count: number; overlap_pct: number }>;
  independence_claim?: boolean;
  note?: string;
};

export type StaxCandidate = {
  save_id: string;
  name: string;
  population_n?: number | null;
  execution_status?: string | null;
  saved_at?: string;
  universe?: CanonicalUniverse | null;
  research_object_id?: string | null;
  question_hash?: string | null;
};

export type StaxCompareChange = {
  member_id: string;
  definition_changed?: boolean;
  dataset_changed?: boolean;
};

export type StaxCompareReorder = {
  member_id: string;
  from?: number;
  to?: number;
};

export type StaxCompare = {
  from?: string;
  to?: string;
  added?: Array<{ member_id?: string; label?: string }>;
  removed?: Array<{ member_id?: string; label?: string }>;
  changed?: StaxCompareChange[];
  reordered?: StaxCompareReorder[];
  unchanged?: string[];
  definition_hash_changed?: boolean;
  dataset_fingerprint_changed?: boolean;
};

export type LibraryRow = {
  stax_id: string;
  name: string;
  sport?: string;
  league_set?: string[];
  seasons?: string[];
  strategies?: number;
  latest_version?: string | null;
  automation?: string;
  last_run?: string | null;
  status?: string;
};
