export type MetricStatus =
  | "OBSERVED"
  | "DERIVED"
  | "HYPOTHETICAL"
  | "MODEL-ASSUMED"
  | "UNAVAILABLE"
  | "DATA_REQUIRED";

export type Frac = {
  numer?: number | null;
  denom?: number | null;
  status?: MetricStatus | string;
  held?: boolean;
  basis?: string;
};

export type SuperasiRoute = "sources" | "run" | "labs_phase_a" | "run_debase" | "labs_phase_b" | "iti";

export type SuperasiLabSource = {
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

export type SuperasiBaseInspect = {
  result_id: string;
  strategy_name: string;
  source_lab_id: string;
  created_at?: string;
  BASE_GRADE?: string;
  components?: Record<string, string>;
  composite_score?: number;
  borderline?: boolean;
  observed?: {
    population?: number;
    wins?: number;
    losses?: number;
    win_rate?: number | null;
    gross_ev?: number | null;
    wilson_lower?: number | null;
    wilson_upper?: number | null;
    p_iqr1?: number | null;
    p_iqr3?: number | null;
    decided_rate?: number | null;
    bad_settle_rate?: number | null;
  };
  desk?: {
    mode?: string;
    seed?: number;
    status?: string;
    note?: string;
    source?: string;
    p_used?: number | null;
    break_even_probability?: number | null;
    trade_ev?: number | null;
    weekly_ev?: number | null;
    required_win_probability?: number | null;
  };
  instrument?: {
    mode?: string;
    seed?: number;
    break_even_probability?: number | null;
    trade_ev?: number | null;
    weekly_ev?: number | null;
    required_win_probability?: number | null;
    note?: string;
    source?: string;
  };
  risk_profile?: {
    status?: string;
    source?: string;
    weeks?: number;
    paths?: number;
    P_min_bankroll_le_floor?: number | null;
    P_final_ge_target?: number | null;
    mean_terminal_bankroll?: number | null;
    note?: string;
    bankroll_dollars?: number;
    allocation_pct?: number;
    floor_dollars?: number;
    target_dollars?: number;
  };
  checks?: Array<{ id?: string; ok?: boolean; severity?: string; detail?: string }>;
  honesty?: Record<string, string>;
  files?: {
    roller_filename?: string;
    abase_filename?: string;
    abase_sha256?: string;
    source_csv_sha256?: string;
  };
};

export type SuperasiBaseResult = {
  result_id: string;
  folder?: string;
  strategy_name: string;
  source_lab_id?: string;
  created_at?: string;
  roller_filename?: string;
  abase_filename?: string;
  BASE_GRADE?: string;
  abase_sha256?: string;
  source_csv_sha256?: string;
  components?: Record<string, string>;
  borderline?: boolean;
  rows?: number | null;
  header_population?: number | null;
  population_matches_rows?: boolean;
};

export type SuperasiDebaseInspect = {
  result_id: string;
  strategy_name: string;
  source_lab_id?: string;
  phase_a_result_id?: string;
  created_at?: string;
  BASE_GRADE?: string;
  DEBASE_GRADE?: string;
  components?: Record<string, string>;
  bottleneck?: string;
  raise_requires?: string;
  composite_score?: number;
  borderline?: boolean;
  capped_to_base?: boolean;
  DEBASE_GRADE_uncapped?: string;
  desk?: SuperasiBaseInspect["desk"];
  instrument?: SuperasiBaseInspect["instrument"];
  p_working?: number;
  p_working_basis?: string;
  p_iqr1?: number;
  p_iqr3?: number;
  p_be_roller?: number;
  ev_debase?: number | null;
  gross_ev?: number | null;
  risk_reward?: number | null;
  risk_reward_plan?: number | null;
  risk_reward_trade_mean?: number | null;
  risk_reward_display?: string | null;
  risk_reward_basis?: string | null;
  risk_reward_methods_disagree?: boolean;
  risk_reward_ratio_of_means?: number | null;
  desk_settings?: {
    bankroll_dollars?: number;
    allocation_pct?: number;
    floor_dollars?: number;
    target_dollars?: number;
  };
  instrument_gate?: {
    value?: string;
    passed?: boolean;
    reasons?: string[];
    expected_20_week_return?: number | null;
    P_min_bankroll_le_floor?: number | null;
    note?: string;
  };
  observed?: SuperasiBaseInspect["observed"];
  valuation?: {
    R_w?: number;
    R_l?: number;
    weekly_ev?: number;
    compounded_20_week?: number;
    weekly_table?: Array<{
      wins?: number;
      losses?: number;
      weekly_return?: number;
      probability?: number;
    }>;
    sensitivity?: Array<{
      p?: number;
      weekly_ev?: number;
      P_min_bankroll_le_floor?: number | null;
      P_final_ge_target?: number | null;
    }>;
  };
  risk_profile?: SuperasiBaseInspect["risk_profile"];
  question_status?: string;
  checks?: Array<{ id?: string; ok?: boolean; severity?: string; detail?: string }>;
  honesty?: Record<string, string>;
  files?: {
    roller_filename?: string;
    abase_filename?: string;
    debase_filename?: string;
    debase_sha256?: string;
    abase_sha256?: string;
    source_csv_sha256?: string;
  };
};

export type SuperasiDebaseResult = {
  result_id: string;
  folder?: string;
  strategy_name: string;
  source_lab_id?: string;
  phase_a_result_id?: string;
  created_at?: string;
  roller_filename?: string;
  abase_filename?: string;
  debase_filename?: string;
  BASE_GRADE?: string;
  DEBASE_GRADE?: string;
  bottleneck?: string;
  debase_sha256?: string;
  components?: Record<string, string>;
  rows?: number | null;
  header_population?: number | null;
  population_matches_rows?: boolean;
};

export type FillAlgorithm =
  | "LEDGER_RULE"
  | "FIRST_BARRIER_CLOSE"
  | "PRINTED_OR_CLOSE"
  | "PLUS_1M"
  | "PLUS_5M"
  | "MIN_5M"
  | "PLANNING_2_5"
  | "FAST_GAP_TAKER";

export type FeeScenario = "CURRENT" | "MODERATE" | "CONSERVATIVE";
export type AdverseP = "70" | "73" | "75" | "K" | "historical";

export type SuperasiErrorBody = {
  status?: string;
  code?: string;
  message?: string;
  detail?: SuperasiErrorBody | string;
};

export type FourCell = {
  n: number;
  cells: {
    W_and_not_T40: number | null;
    W_and_T40: number | null;
    L_and_not_T40: number | null;
    L_and_T40: number | null;
  };
  p: Frac;
  alpha: Frac;
  s_W: Frac;
  s_L: Frac;
  S: Frac;
  note?: string;
  status?: string;
  path_survivors?: number;
  path_losses?: number;
};

export type MixSummary = {
  id: FillAlgorithm | string;
  definition?: string;
  n_path_loss?: number;
  n_available?: number | null;
  n_unavailable?: number | null;
  mean_L?: Frac | null;
  mean_exit?: Frac | null;
  EV?: Frac | null;
  G?: number;
  S?: Frac;
  research_status?: string;
  not_a_fill?: boolean;
};

export type PackageIdentity = {
  package_id: string;
  schema_version?: string;
  source?: string;
  imported_at?: string;
  population_n?: number;
  name?: string | null;
  research_object_id?: string | null;
  question_hash?: string | null;
  hashes?: Record<string, string>;
  research_spec?: { identity?: { name?: string | null } | null };
  roller_handoff?: { workflow_draft?: unknown };
  dataset_version?: string | null;
  spec_fingerprint?: string | null;
  compile_fingerprint?: string | null;
  trade_origin?: string | null;
  code_version?: string;
  semantics_version?: string;
  live_execution?: boolean;
  price_basis?: string;
  caveats?: string[];
  analysis_gross_pre_superasi?: {
    label?: string;
    observed?: unknown;
    book?: unknown;
    settlement?: unknown;
    note?: string;
  } | null;
  empirical_four_cell?: FourCell;
  seed_locks?: Record<string, unknown>;
};

export type LibraryItem = {
  package_id: string;
  source?: string;
  population_n?: number;
  imported_at?: string;
  name?: string | null;
  research_object_id?: string | null;
  question_hash?: string | null;
  dataset_version?: string | null;
  trade_origin?: string | null;
  sport?: string | null;
  decomposition_status?: string;
  code_version?: string;
  workflow_draft?: unknown;
};

export type SuperasiTrade = {
  ticker: string;
  observation_id?: string;
  internal_game_id?: string;
  sport?: string;
  slice?: string;
  league?: string;
  dataset_split?: string;
  te?: Record<string, unknown> | null;
  alignment?: string | null;
  hyp_pnl_cents?: number | null;
  path_steps?: string[] | null;
  entry_ts?: string;
  entry_close?: number | null;
  entry_ask?: number | null;
  entry_spread?: number | null;
  entry_ask_status?: string;
  entry_spread_status?: string;
  entry_tradable_status?: string;
  exit_ts?: string;
  exit_close?: number | null;
  exit_outcome?: string;
  path_true?: boolean | null;
  win_exit?: boolean | null;
  loss_exit?: boolean | null;
  terminal_yes?: boolean | null;
  T40?: boolean | null;
  price_basis?: string;
  window_derived?: {
    ticker?: string;
    prior_close?: number | null;
    t40_close?: number | null;
    close_1m?: number | null;
    close_5m?: number | null;
    min_close_5m?: number | null;
    printed_at_barrier?: boolean;
    fast_gap?: boolean;
  };
};

export type PathWindowRow = {
  ticker?: string;
  offset: number;
  yes_bid_close?: number | null;
  yes_ask_close?: number | null;
  yes_bid_low?: number | null;
  last?: number | null;
  spread?: number | null;
  tradable?: boolean | null;
  candle_ts?: string | null;
  status?: string;
};

export type Decomp = {
  package_id: string;
  decomposed_at?: string;
  live_execution?: boolean;
  settings?: {
    fill_algorithm?: string;
    fee_scenario?: string;
    adverse_p?: string;
    window?: string;
  };
  four_cell?: FourCell;
  gross_pre_superasi?: PackageIdentity["analysis_gross_pre_superasi"];
  fill_algorithms?: Record<string, MixSummary>;
  active_mix?: MixSummary;
  entry_cents?: number;
  gain_cents?: number;
  gain_status?: string;
  fees?: Record<string, unknown>;
  net_estimate?: Record<string, unknown> | null;
  adverse_terminal?: {
    label?: string;
    kind?: string;
    not_a_forecast?: boolean;
    p_key?: string;
    p?: Frac;
    s_W?: Frac;
    s_L?: Frac;
    S_stressed?: Frac;
    EV_adverse?: Frac;
    held_s_W?: boolean;
    held_s_L?: boolean;
    note?: string;
    status?: string;
    code?: string;
  };
  path_windows?: {
    path_loss_n?: number;
    n_window_rows?: number;
    offsets?: Record<
      string,
      {
        n: number;
        sum?: number | null;
        mean?: Frac | null;
        median?: number | null;
      }
    >;
    pre_t40_38_40_trades?: number;
    note?: string;
    status?: string;
  };
  liquidity?: {
    taker?: number;
    maker?: number;
    unavailable?: number;
    note?: string;
  };
  capital_overlay?: Record<string, unknown>;
  caveats?: string[];
  stop_path_status?: string;
  question_hash?: string | null;
  dataset_version?: string | null;
  checksums?: { trades?: string | null };
};

export type PackageGet = {
  package: PackageIdentity;
  population_n: number;
  trades_n: number;
  path_windows_n: number;
  decomp: Decomp | null;
  trades: SuperasiTrade[];
  path_windows: PathWindowRow[];
  sample_trades?: SuperasiTrade[];
};

export type ImportResponse = {
  package_id: string;
  population_n?: number;
  source?: string;
  message?: string;
  execution_status?: string;
  question_hash?: string | null;
  dataset_version?: string | null;
  trade_origin?: string | null;
};

export const FILL_ALGORITHMS: { id: FillAlgorithm; label: string }[] = [
  { id: "LEDGER_RULE", label: "Ledger rule" },
  { id: "FIRST_BARRIER_CLOSE", label: "First barrier close" },
  { id: "PRINTED_OR_CLOSE", label: "Printed or close" },
  { id: "PLUS_1M", label: "+1m close" },
  { id: "PLUS_5M", label: "+5m close" },
  { id: "MIN_5M", label: "Min +1…+5" },
  { id: "PLANNING_2_5", label: "Planning +2.50¢" },
  { id: "FAST_GAP_TAKER", label: "Fast-gap taker" },
];

export const FEE_SCENARIOS: { id: FeeScenario; label: string }[] = [
  { id: "CURRENT", label: "Current" },
  { id: "MODERATE", label: "Moderate" },
  { id: "CONSERVATIVE", label: "Conservative" },
];

export const ADVERSE_OPTIONS: { id: AdverseP; label: string }[] = [
  { id: "70", label: "70%" },
  { id: "73", label: "73%" },
  { id: "75", label: "75%" },
  { id: "K", label: "K = 80%" },
  { id: "historical", label: "Historical p" },
];
