export type FrontendTarget = {
  kind: string;
  url: string;
  product?: string;
  mode?: string;
};

export type SystemRow = {
  id: string;
  display_name: string;
  short_name: string;
  visual_subtitle?: string | null;
  extra?: { visual_subtitle?: string };
  bracket_round: string;
  purpose: string;
  status: string;
  version: string;
  implementation_paths: string[];
  research_paths: string[];
  frontend_target: FrontendTarget;
  backend_target: { kind: string; host?: string; port?: number; namespaces?: string[] };
  api_namespace: string;
  upstream_systems: string[];
  downstream_systems: string[];
  input_contracts: string[];
  output_contracts: string[];
  health_check: string;
  feature_flags: string[];
  live_capability: boolean;
  migration_sources: string[];
  notes: string;
};

export type LogicPayload = {
  system_id: string;
  status: string;
  logic: string;
  implementation_paths: string[];
  limitations: string;
  live_execution: boolean;
};

export type HealthRow = {
  system_id: string;
  state: string;
  ok: boolean | null;
  live_execution: boolean;
  detail: string;
  frontend_probe?: string;
};

export type BdrCard = {
  slug: string;
  number: number;
  title: string;
  kind: string;
  path: string;
  blurb: string;
  hash: string;
};

export type BdrCatalog = {
  live_execution: boolean;
  system_id: string;
  title: string;
  subtitle: string;
  note: string;
  documents: BdrCard[];
  related: { title: string; path: string }[];
};

export type BdrDocument = BdrCard & {
  markdown: string;
  live_execution: boolean;
};

export type HealthAggregate = {
  live_execution: boolean;
  nba_bot: string;
  count: number;
  states_present: string[];
  frontend_probe?: string;
  systems: HealthRow[];
};

export type MarketProbe = {
  warehouse_id: string;
  status: string;
  query: string;
  reason?: string | null;
  returned?: number | null;
  n?: number | null;
  rows?: Record<string, unknown>[];
};

export type ResearchProbe = {
  status: string;
  execution_path?: string | null;
  available?: string[];
  unavailable?: string[];
  leagues?: string[];
  reason?: string;
};

export type ConnectionPayload = {
  schema: string;
  live_execution: boolean;
  roller: { status: string; port: number; health: string };
  markets: { nba: MarketProbe; ncaab: MarketProbe };
  research_query: { nba: ResearchProbe; ncaab: ResearchProbe; combined: ResearchProbe };
  connected: boolean;
  detail: string;
  probe_sql: string;
};

export type WarehouseQueryResult = {
  warehouse_id: string;
  columns: string[];
  rows: Record<string, unknown>[];
  returned: number;
  read_only: boolean;
};

export type TkUltraStep = {
  id: string;
  label: string;
  value: string;
  numer: number;
  denom: number;
};

export type TkUltraAssess = {
  schema?: string;
  live_execution: boolean;
  system_id?: string;
  method: string;
  status: string;
  binary_formula_is_truth: boolean;
  reading?: string;
  missing?: string[];
  detail?: string;
  pair?: string | null;
  corridor_cents?: string | null;
  corridor_note?: string;
  relationship_multiplier?: string;
  expected_wing_move?: string;
  expected_wing?: string;
  residual?: string;
  rv_ticks?: string;
  steps?: TkUltraStep[];
};

export type TkUltraHealth = {
  ok: boolean;
  product: string;
  live_execution: boolean;
  execution_enabled: boolean;
  live_feed: string;
  model_modes: string[];
  austin: { universe: string; n: number; availability: string; adapter: string };
  choosin_texas: { universe: string; n: number; availability: string; adapter: string };
  ballhog: { availability: string; role: string };
  position_management: string;
};

export type TkUltraSources = {
  feed_mode: string;
  live_feed: string;
  austin: { universe: string; n: number; adapter: string };
  choosin_texas: { universe: string; n: number; adapter: string; pit_kind: string };
  ballhog: { role: string };
};

export type TkUltraV0Relationship = {
  status?: string;
  expected_wing?: string;
  observed_wing?: string;
  tk_residual?: string;
  rv_state?: string;
  a_ref?: string;
  a_ref_basis?: string;
  observed_wing_basis?: string;
  relationship_basis_label?: string;
  relationship_route_collinear?: boolean;
  anchor_validity?: string;
  note?: string;
};

export type TkUltraV0Route = {
  direct_exit_price?: string;
  synthetic_exit_price?: string;
  gross_route_edge?: string;
  route_preference?: string;
  preference_note?: string;
  b_route_parity_price?: string;
  route_execution_quality?: string;
};

export type TkUltraV0Budget = {
  a_entry?: string;
  a_stop_benchmark?: string;
  stop_pnl_benchmark?: string;
  stop_equivalent_b_avg?: string;
  current_hedge_fraction?: string;
  hedge_fraction?: string;
  remaining_fraction?: string;
  current_avg_b_price?: string;
  max_remaining_avg_price?: string;
  hedge_runway_vs_ask?: string;
  cost_cushion_vs_existing_avg?: string;
  completed_now_b_avg?: string;
  locked_pnl_if_completed_now?: string;
  gross_improvement_vs_stop_if_completed_now?: string;
  fees?: string;
  slippage?: string;
};

export type TkUltraV0Sibling = {
  availability?: string;
  note?: string;
  q_star?: number | string | null;
  rho_star?: number | string | null;
  risk_intent?: string;
  decision_status?: string;
  intent_status?: string;
  position_management?: string;
};

export type TkUltraV0Assess = {
  schema: string;
  model_mode: string;
  status: string;
  live_execution: boolean;
  feed_mode: string;
  live_feed: string;
  expected_wing?: string;
  tk_residual?: string;
  rv_state?: string;
  relationship_route_collinear?: boolean;
  synthetic_exit_price?: string;
  gross_route_edge?: string;
  route_preference?: string;
  stop_equivalent_b_avg?: string;
  max_remaining_avg_price?: string;
  hedge_runway_vs_ask?: string;
  locked_pnl_if_completed_now?: string;
  completed_now_b_avg?: string;
  position_management?: string;
  relationship?: TkUltraV0Relationship;
  route?: TkUltraV0Route;
  hedge_budget?: TkUltraV0Budget;
  sibling_context?: TkUltraV0Sibling | string;
  austin?: { universe: string; n: number; availability: string; adapter: string };
  choosin_texas?: { universe: string; n: number; availability: string; adapter: string };
  quantity_specific_assessment?: unknown;
  reason_codes?: string[];
};

export type TkUltraDesk = {
  schema: string;
  live_execution: boolean;
  system_id: string;
  title: string;
  subtitle: string;
  product: string;
  named_for: string;
  note: string;
  model_mode_generic?: string;
  model_mode_first80?: string;
  limitations: string[];
  source_letter: {
    from_name: string;
    from_email: string;
    date: string;
    to: string;
    subject: string;
    path: string;
    body: string;
  };
  formula: {
    method: string;
    steps: string[];
    reading: Record<string, string>;
  };
  worked_example: {
    wing_name: string;
    base_name: string;
    wing_price: string;
    base_price: string;
    beta: string;
    beta_note: string;
    wing_anchor: string;
    base_anchor: string;
    ticks_per_handle: number;
    published: {
      multiplier: string;
      expected_move: string;
      residual: string;
      rv_ticks: string;
      note: string;
    };
    engine: TkUltraAssess;
  };
  corridor: {
    owner_when: string;
    owner_rich_cheap: string;
    windows: { cents: number; role: string; bdr: string; tk: string }[];
    pair: {
      base: string;
      wing: string;
      beta_same_direction: string;
      beta_inverse: string;
      ticks_per_handle: string;
    };
    implementation: string[];
  };
};
