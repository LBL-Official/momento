export type FractionView = {
  numer: number;
  denom: number;
  status?: string;
};

export type RateBlock = {
  wins: number;
  losses: number;
  p?: FractionView;
  S?: FractionView;
  loss_rate?: FractionView;
  p_display?: string;
  p_pct_display?: string;
  p_bar_pct?: number;
  S_display?: string;
  S_pct_display?: string;
  S_bar_pct?: number;
  loss_display?: string;
  loss_pct_display?: string;
  note?: string;
  ev_display?: string;
  ev_per_trade_display?: string;
  book_cents?: number;
  ev_bar_pct?: number;
  stop_cents?: number;
  n?: number;
};

export type FourCell = {
  W_and_not_T40: number;
  W_and_T40: number;
  L_and_not_T40: number;
  L_and_T40: number;
};

export type TradePath = RateBlock & {
  key: string;
  stop_cents: number;
  n: number;
  excluded_hit_86?: number;
  excluded_hit_81?: number;
  excluded_hit_83?: number;
  gain_cents?: number;
  loss_cents?: number;
  filter?: {
    entry_yes_bid_lt?: number;
    excluded_hit_86?: number;
    excluded_hit_81?: number;
    excluded_hit_83?: number;
    n_full?: number;
    note?: string;
  };
};

export type Trade8055 = TradePath & {
  cells?: {
    W_and_not_T55: number;
    W_and_T55: number;
    L_and_not_T55: number;
    L_and_T55: number;
  };
};

export type Partition = {
  partition_id: string;
  sport_label: string;
  slice_label: string;
  role: string;
  n: number;
  W: number;
  L: number;
  cells: FourCell;
  terminal: RateBlock;
  trade_80_40?: RateBlock;
  trade_75_40?: RateBlock;
  trade_75_55?: Trade8055;
  trade_77_40?: RateBlock;
  trade_77_55?: Trade8055;
  trade_80_55?: Trade8055;
  trade_80_60?: TradePath & {
    cells?: {
      W_and_not_T60: number;
      W_and_T60: number;
      L_and_not_T60: number;
      L_and_T60: number;
    };
    loss_cents?: number;
    gain_cents?: number;
  };
  path_ladder_status?: string;
  path_ladder_note?: string;
  paths?: TradePath[];
  ledger_rank?: string[];
  mid_paths?: TradePath[];
  mid_ledger_rank?: string[];
  band?: TradePath[];
  band_rank?: string[];
  n_share_display?: string;
  n_share_pct_display?: string;
  n_bar_pct?: number;
};

export type AskedSixTauBook = TradePath & {
  tau?: number;
  rule?: string;
  status?: string;
  message?: string;
  paths?: TradePath[];
  ledger_rank?: string[];
  n_55?: number;
  excluded_55?: number;
  entry_cents?: number;
  entry_cap_cents?: number;
  note?: string;
};

export type AskedSixSlice = {
  partition_id: string;
  sport_label?: string;
  slice_label?: string;
  ncaab_window_note?: string | null;
  books?: Record<string, AskedSixTauBook>;
};

export type AskedSixOosSlice = {
  status?: string;
  partition_id?: string;
  sport_label?: string;
  slice_label?: string;
  n?: number;
  message?: string;
  paths?: TradePath[];
};

export type AskedSixOosBook = {
  status?: string;
  tau?: number;
  rule?: string;
  message?: string;
  split?: {
    train_n?: number;
    test_n?: number;
    validation_n?: number;
    train_window?: string[];
    test_window?: string[];
    rule?: string;
  };
  train?: { pool?: { n?: number; paths?: TradePath[] }; slices?: Record<string, AskedSixOosSlice> };
  test?: { pool?: { n?: number; paths?: TradePath[] }; slices?: Record<string, AskedSixOosSlice> };
  note?: string;
};

export type AskedSixPage = {
  status: string;
  product?: string;
  live_execution?: boolean;
  path_stops?: number[];
  books?: Record<string, { n?: number; identity?: string; status?: string; message?: string }>;
  pool?: {
    role?: string;
    ncaab_window_note?: string | null;
    books?: Record<string, AskedSixTauBook>;
  };
  partitions?: AskedSixSlice[];
  oos?: {
    status?: string;
    label?: string;
    in_sample_note?: string;
    books?: Record<string, AskedSixOosBook>;
  };
  disclaimers?: string[];
  message?: string;
};

export type Universe = {
  status: string;
  product?: string;
  live_execution?: boolean;
  rule?: string;
  page?: string;
  gain_cents?: number;
  loss_cents?: number;
  entry_cents?: number;
  stop_cents?: number;
  unit?: string;
  anchor_80_40?: {
    n?: number;
    S_display?: string;
    note?: string;
  };
  band_stops?: number[];
  gap?: {
    t65?: { pool?: GapSlice; slices?: GapSlice[]; note?: string };
    t60?: { pool?: GapSlice; slices?: GapSlice[]; note?: string };
  };
  clocks?: ClockSlice[];
  alignment?: { model?: string; note?: string };
  partitions: Partition[];
  pool: Partition & { note?: string };
  complement?: {
    asked_six_n?: number;
    derived_four_n?: number;
    wnba_2q_3q_n?: number;
    identity?: string;
    note?: string;
  };
  verification?: {
    status?: string;
    sources?: string[];
  };
  variables?: {
    rule?: string;
    K?: number;
    stop_cents?: number;
    stop_55_cents?: number;
    entry_cents?: number;
    entry_cap_cents?: number;
    gain_cents?: number;
    loss_cents?: number;
    n?: number;
    path_ladder_status?: string;
    path_stops?: number[];
    mid_stops?: number[];
    slices?: string[];
    locked?: boolean;
    recompute?: string;
    note?: string;
  };
  disclaimers?: string[];
  message?: string;
  code?: string;
};

export type ClockBin = {
  period: string;
  clock_bin: string;
  label: string;
  n: number;
  n_display?: string;
  pct_display?: string;
  bar_pct?: number;
};

export type ClockSlice = {
  slice: string;
  slice_label: string;
  n: number;
  n_t40?: number;
  n_t60?: number;
  bins: ClockBin[];
  mean_remaining?: { period: string; n: number; clock_display: string }[];
};

export type CountBlock = {
  k: number;
  n: number;
  display: string;
  pct_display: string;
};

export type GapSlice = {
  partition_id: string;
  n: number;
  separate_print?: CountBlock;
  same_bar_at_or_below_60?: CountBlock;
  separate_then_60?: CountBlock;
  separate_held_above_60?: CountBlock;
  same_bar_at_or_below_55?: CountBlock;
  continued_to_55?: CountBlock;
  never_printed_55?: CountBlock;
};

export type ScatterPoint = {
  ticker: string;
  slice: string;
  bought_team: string;
  t40: boolean;
  cohort: string;
  entry_margin: number;
  final_margin: number;
  t40_margin: number | null;
  alignment_confidence: string;
  plot_x_pct: number;
  plot_y_pct: number;
};

export type MarginBlock = {
  n: number;
  min: number;
  max: number;
  mean_display: string;
};

export type NbaPath = {
  status: string;
  n: number;
  n_survive: number;
  n_t40: number;
  alignment?: { model?: string; note?: string };
  clocks: ClockSlice[];
  scatter: {
    x_label: string;
    y_label: string;
    x_min: number;
    x_max: number;
    y_min: number;
    y_max: number;
    points: ScatterPoint[];
  };
  margins: {
    survive: { n: number; entry: MarginBlock; final: MarginBlock };
    t40: { n: number; entry: MarginBlock; final: MarginBlock; t40_time: MarginBlock };
  };
  message?: string;
};

export type DallasCohort = "survive" | "t40_win" | "t40_lose";

export type DallasRate = {
  n: number;
  count?: number;
  display: string;
  pct_display: string;
  bar_pct: number;
};

export type DallasTick = {
  value: number;
  label: string;
  plot_pct: number;
};

export type DallasChart = {
  x_label: string;
  y_label: string;
  x_ticks: DallasTick[];
  y_ticks: DallasTick[];
};

export type DallasGame = {
  ticker: string;
  slice: string;
  bought_team: string;
  cohort: DallasCohort;
  pregame_cents: number;
  entry_bid: number;
  lead_80: number;
  t40_lead: number | null;
  final_lead: number;
  exit_period_label: string | null;
  exit_game_clock: string | null;
  plot_x_pct: number;
  plot_y_pct: number;
  hover_lines: string[];
};

export type DallasSnapshot = {
  ticker: string;
  bought_team: string;
  cohort: DallasCohort;
  label: string;
  lead: number;
  price_cents: number;
  plot_x_pct: number;
  plot_y_pct: number;
  hover_lines: string[];
};

export type DallasCollapse = {
  ticker: string;
  bought_team: string;
  cohort: DallasCohort;
  lead_80: number;
  t40_lead: number;
  delta: number;
  exit_period_label: string | null;
  exit_game_clock: string | null;
  plot_x_pct: number;
  plot_y_pct: number;
  plot_x0_pct: number;
  plot_y0_pct: number;
  hover_lines: string[];
};

export type DallasCut = {
  key: string;
  label: string;
  n: number;
  t40: DallasRate;
  t40_win: DallasRate;
  t40_lose: DallasRate;
  survive: DallasRate;
  hover_lines: string[];
};

export type DallasCrossCell = DallasCut & {
  lead_key: string;
  lead_label: string;
  pregame_key: string;
  pregame_label: string;
};

export type DallasCross = {
  lead_labels: { key: string; label: string }[];
  pregame_labels: { key: string; label: string }[];
  cells: DallasCrossCell[];
};

export type DallasCuts = {
  lead_80: DallasCut[];
  pregame: DallasCut[];
  cross: DallasCross;
};

export type DallasSlice = {
  slice: string;
  slice_label: string;
  n: number;
  rates: {
    n: number;
    t40: DallasRate;
    t40_win: DallasRate;
    t40_lose: DallasRate;
    survive: DallasRate;
    note?: string;
  };
  games: DallasGame[];
  snapshots: DallasSnapshot[];
  collapse: DallasCollapse[];
  cuts: DallasCuts;
  game_chart: DallasChart;
  snapshot_chart: DallasChart;
  collapse_chart: DallasChart;
};

export type BookEvRow = {
  key?: string;
  label?: string;
  n: number;
  s_n?: number;
  s_display?: string;
  w_t40?: number | null;
  l_t40?: number | null;
  t40?: number | null;
  book_cents?: number;
  ev_per_trade_display?: string;
  window?: string[];
};

export type BookTape = BookEvRow & {
  tape_id: string;
  label: string;
  sport?: string;
  slices?: string[];
  phases?: string[];
  role?: string;
  window?: string[];
  slice_rows?: BookEvRow[];
  splits?: BookEvRow[];
  lead?: BookEvRow[];
  open?: BookEvRow[];
  cross_4_6_ge71?: BookEvRow;
};

export type BookHold = {
  claim: string;
  ncaab: string;
  verdict: string;
};

export type BookWatch = {
  cell: string;
  why: string;
};

export type BookRegistered = {
  status?: string;
  live_execution?: boolean;
  submits?: boolean;
  risk_approved?: boolean;
  enable_live_trading?: boolean;
  title?: string;
  sport?: string;
  slice?: string;
  season_phase?: string;
  rule?: string;
  entry_cents?: number;
  stop_cents?: number;
  contracts?: number;
  filters?: unknown[];
  baseline_tape?: string;
  clauses?: string[];
};

export type ResearchBook = {
  status: string;
  product?: string;
  book_id?: string;
  live_execution?: boolean;
  submits?: boolean;
  risk_approved?: boolean;
  enable_live_trading?: boolean;
  tape_season?: string;
  measure_season?: string;
  identity?: string;
  library_path?: string;
  writeup_path?: string;
  note_path?: string;
  registered?: BookRegistered;
  hold_reverse?: BookHold[];
  watch_do_not_filter?: BookWatch[];
  forbidden?: string[];
  measurement?: string[];
  conversion?: string[];
  baseline?: BookEvRow & { tape_id?: string; window?: string[] };
  tapes?: BookTape[];
  disclaimers?: string[];
  verification?: { status?: string; sources?: string[] };
  message?: string;
};

export type Dallas = {
  status: string;
  n: number;
  n_survive: number;
  n_t40: number;
  n_t40_win: number;
  n_t40_lose: number;
  rates: DallasSlice["rates"];
  cuts: DallasCuts;
  slices: DallasSlice[];
  note?: string;
  disclaimers?: string[];
  message?: string;
};

export type AustinCoverage = {
  n_trades?: number;
  n_q2?: number;
  n_q3?: number;
  n_path_complete?: number;
  n_path_partial?: number;
  n_path_unavailable?: number;
  n_knn_observations?: number;
  path_complete_definition?: string;
};

export type AustinNeighbor = {
  rank?: number;
  distance?: number;
  trade_id?: string;
  ticker?: string;
  game_date?: string;
  quarter?: number;
  entry_price_cents?: number;
  current_price_cents?: number;
  score_differential?: number;
  price_travel?: number;
  time_since_entry?: number;
  final_pnl_taker_8040_cents?: number;
  final_pnl_taker_7867_cents?: number;
  pnl_hold_after_t?: number;
  settlement?: string;
  csv_t40?: boolean;
  hit_40_after?: boolean;
  hit_67_after?: boolean;
};

export type AustinMatch = {
  k?: number;
  effective_neighbors?: number;
  status?: string;
  support?: string;
  distance_metric?: string;
  weighting?: string;
  mean_distance?: number;
  median_distance?: number;
  nearest_distance?: number;
  weighted_mean_PNL?: number;
  weighted_median_PNL?: number;
  weighted_mean_EV?: number;
  weighted_survival_rate?: number;
  weighted_T40_rate?: number;
  PNL_std?: number;
  PNL_p25?: number;
  PNL_p50?: number;
  PNL_p75?: number;
  PNL_min?: number;
  PNL_max?: number;
  neighbors?: AustinNeighbor[];
};

export type AustinQueryResult = {
  status: string;
  knn_status?: string;
  reason?: string;
  query_mode?: string;
  entry_source?: string;
  data_mode?: string;
  live_feed?: string;
  path_mode?: string;
  pca_vector?: number[];
  derived?: Record<string, number | null>;
  match?: AustinMatch;
  sizing?: Record<string, unknown>;
  conditional_ev?: Record<string, unknown>;
  support?: Record<string, unknown>;
  distribution?: Record<string, unknown>;
  state_change?: Record<string, unknown>;
  proximity?: { feature: string; query?: number | null; neighbor_median?: number | null; abs_delta?: number | null }[];
  feature_coverage?: number;
  missing_features?: string[];
  features?: { features?: Record<string, { value?: number | null; status?: string }> };
  availability?: Record<string, string>;
  form?: Record<string, unknown>;
  reconstructed?: Record<string, unknown>;
  message?: string;
  note?: string;
  fee_model_status?: string;
};

export type SugarlandStat = {
  sport: string;
  cohort: string;
  horizon_h?: number | string;
  eligible_n: number;
  endpoint_n: number;
  mean_dpp: number | string;
  median_dpp: number | string;
  ci95_low: number | string;
  ci95_high: number | string;
  share_rising: number | string;
  mean_return_on_ask: number | string;
  discovery_mean_dpp: number | string;
  discovery_endpoint_n: number;
  validation_mean_dpp: number | string;
  validation_endpoint_n: number;
  status: string;
};

export type SugarlandContract = {
  ticker: string;
  sport: string;
  season: string;
  game_date: string;
  partition: string;
  band: string;
  lead_bucket: string;
  in_a: boolean;
  in_b: boolean;
  already_above_80: boolean;
  endpoint: boolean;
  dpp: number | null;
  return_on_ask: number | null;
  gross_dollars: number | null;
  h48_dpp: number | null;
  h24_dpp: number | null;
  h48_around80: boolean;
  h24_around80: boolean;
  h48_above70: boolean;
  h24_above70: boolean;
  h48_return_on_ask: number | null;
  h24_return_on_ask: number | null;
  slope_pp_per_hour: number | null;
  slope_status: string;
  covered_hours: number | null;
  uncovered_hours: number | null;
  share_time_above: number | null;
  h48: number | null;
  h24: number | null;
  h12: number | null;
  h6: number | null;
  h2: number | null;
  h1: number | null;
  p30: number | null;
  exclusion: string;
};

export type SugarlandPage = {
  status: string;
  universe_id: string;
  spec_sha256: string;
  live_execution: boolean;
  submits: boolean;
  research_only: boolean;
  execution_disabled: boolean;
  question: string;
  dashboard_sports: string[];
  library_note: string;
  limitations: string[];
  coverage: Record<string, Record<string, number | string> | undefined>;
  parquet_inventory?: Record<string, { games?: number; observation_rows?: number; orderbook_data_available?: boolean } | null>;
  tables: {
    headline_first_observed_above_70: SugarlandStat[];
    around_80: SugarlandStat[];
  };
  audit?: {
    label: string;
    primary_tables_unchanged: boolean;
    blocks: Array<{
      sport: string;
      horizon_h: number;
      cohort: string;
      exclusions?: {
        eligible_n: number;
        endpoint_n: number;
        missing_n: number;
        counts: Record<string, number>;
      };
      spread_cents?: {
        complete_n: number;
        bid_appreciation_cents: { mean_cents: number | string; n: number };
        entry_spread_cents: { mean_cents: number | string; n: number };
        quote_profit_cents: { mean_cents: number | string; ci95_low: number | string; ci95_high: number | string; interval_status: string; n: number };
      };
      boundary_sensitivity?: {
        added_boundary_n: number;
        endpoint_n: number;
        eligible_n: number;
        log_odds_unavailable_n: number;
        bid_appreciation_cents: { mean_cents: number | string };
        quote_profit_cents: { mean_cents: number | string };
      };
      paired?: {
        paired_n: number;
        dropped_missing_24h: number;
        dropped_missing_endpoint: number;
        still_outside_around80_at_24h: number;
        cents_48_to_24: { mean_cents: number | string; ci95_low: number | string; ci95_high: number | string; interval_status: string };
        cents_24_to_30: { mean_cents: number | string; ci95_low: number | string; ci95_high: number | string; interval_status: string };
        cents_48_to_30: { mean_cents: number | string; ci95_low: number | string; ci95_high: number | string; interval_status: string };
      };
    }>;
  };
  contracts: SugarlandContract[];
  message?: string;
};

export type PairedRun = {
  book: string;
  configuration_id: string;
  sizing: string;
  live_size: boolean;
  per_position_risk_cents: number;
  position_cap: number | null;
  flat_loss_cents: number;
  entries_taken: number;
  contracts_taken: number;
  max_concurrent: number;
  max_deployed_cents: number;
  final_cash_cents: number;
  through_close_pnl_cents: number;
  flat_stop_pnl_cents: number;
  skips: {
    SKIP_CASH: number;
    SKIP_RISK_BUDGET: number;
    POSITION_CAP: number;
    SAME_EVENT: number;
  };
  resized_cash_n: number;
  flat_stop_stress_proxy: {
    name: string;
    meaning: string;
    min_cents: number;
    final_cents: number;
  };
  realized_pnl_path: {
    name: string;
    meaning: string;
    min_cents: number;
    final_cents: number;
  };
};

export type CapitalBook = {
  book: string;
  accepted: number;
  stopped: number;
  survivors: number;
  candidates: number;
  accepted_win_rate_display: string;
  full_book_survivor_display: string;
  contracts_taken: number;
  through_close_pnl_cents: number;
  flat_stop_pnl_cents: number;
  ending_cash_cents: number;
  return_on_initial_display: string;
  return_on_initial_pct_display: string;
  max_concurrent: number;
  max_open_entry_premium_cents: number;
  max_open_entry_premium_dollars_display: string;
  max_open_entry_premium_of_basis_pct_display: string;
  largest_single_realized_loss_cents: number;
  largest_single_realized_loss_dollars_display: string;
  worst_session_date: string;
  worst_session_realized_exit_pnl_cents: number;
  sessions_with_carried_positions: number;
  date_start: string;
  date_end: string;
  planned_flat_loss_per_full_position_cents: number;
  reasons: Record<string, number>;
  realized_capital: { name: string; meaning: string; final_cents: number };
  realized_capital_max_drawdown: {
    name: string;
    meaning: string;
    cents: number;
    dollars_display: string;
    of_peak_pct_display: string;
  };
  flat_stop_stress_proxy: { name: string; meaning: string; min_cents: number };
};

export type CapitalPolicy = {
  id: string;
  session_timezone: string;
  timestamp_convention: string;
  accepted_both: number;
  accepted_only_80_40: number;
  accepted_only_80_65: number;
  notices: {
    CANDLE_PATH_NOT_FILL: string;
    FEES_UNAVAILABLE: string;
    LIVE_EXECUTION_DISABLED: string;
    forecast: string;
  };
  books: Record<string, CapitalBook>;
};

export type PlannedBreach = {
  event_id: string;
  entry_ts: number;
  exit_ts: number;
  contracts: number;
  session_basis_cents: number;
  planned_loss_cents: number;
  through_close_cents: number;
  realized_loss_cents: number;
  excess_cents: number;
};

export type PlannedBook = CapitalBook & {
  sizing_note: string;
  realized_loss_cap: string;
  max_planned_stop_risk_of_basis_pct_display: string;
  largest_single_realized_loss_of_basis_pct_display: string;
  worst_session_dollars_display: string;
  worst_session_of_basis_pct_display: string;
  loss_breaches: PlannedBreach[];
  loss_breach_summary: {
    threshold: string;
    count: number;
    total_realized_loss_cents: number;
    largest_of_basis_pct_display: string;
  };
  decisions: PlannedAdmission[];
  occupancy: {
    max_concurrent: number;
    window: string;
    seconds_at_open_count: Record<string, number>;
    change_points: { ts: number; kind: string; event_id: string; open_count_before: number; open_count: number }[];
  };
  turnover: {
    dates_with_candidates: number;
    dates_with_accepted_entries: number;
    accepted_per_entry_date: { median: number; p95: number; maximum: number };
    holding_seconds: { median: number; p95: number; maximum: number };
    candidates_by_open_count_before: Record<string, number>;
    position_cap_skips: number;
    other_skips: number;
    busiest_entry_date: { date: string; accepted: number } | null;
    blocked_example: {
      event_id: string;
      entry_ts_display: string;
      blocking_event_ids_display: string;
      relation_to_freed_window: string;
    } | null;
    freed_example: {
      sequence_display: string;
      steps: { ts_display: string; kind: string; event_id: string; open_count_before: number; open_count: number; occupying_event_ids_display: string }[];
    } | null;
  };
  loss_severity: {
    largest_dollar_loss: { event_id: string; dollars_display: string; of_basis_pct_display: string } | null;
    largest_percent_loss: { event_id: string; dollars_display: string; of_basis_pct_display: string } | null;
    largest_dollar_and_percent_same_event: boolean;
    breach_share_display: string;
    stopped_loss_pct: { median?: string; p95?: string; maximum?: string };
    breach_excess: { median_cents?: number; p95_cents?: number; maximum_cents?: number };
  };
};

export type PlannedAdmission = {
  event_id: string;
  ticker: string;
  sport: string;
  slice: string;
  reason: string;
  accepted: boolean;
  open_count_before: number;
  open_count_after: number;
  requested_contracts: number;
  accepted_contracts: number;
  session_basis_cents: number;
};

export type PlannedDiagnostic = {
  book: string;
  max_open_positions: number;
  primary: boolean;
  label: string;
  accepted: number;
  through_close_pnl_cents: number;
  reconstructed_max_concurrent: number;
  position_cap_skips: number;
  initial_full_position_contracts: number;
};

export type PlannedRiskPolicy = {
  id: string;
  realized_loss_cap: string;
  sizing_note: string;
  session_timezone: string;
  prior_result_status: string;
  selects_a_cap: boolean;
  quantile_convention: string;
  configuration: {
    max_open_positions: number;
    premium_percent_per_position: number;
    planned_stop_risk_percent_80_40: number;
    premium_percent_portfolio: number;
    session_timezone: string;
    session_convention: string;
    reconstructed_max_concurrent_80_40: number;
    reconstructed_max_concurrent_80_65: number;
  };
  diagnostics: PlannedDiagnostic[];
  headings: { book_40: string; book_65: string; both: string };
  accepted_both: number;
  accepted_only_80_40: number;
  accepted_only_80_65: number;
  notices: CapitalPolicy["notices"];
  books: Record<string, PlannedBook>;
};

export type PairedReplay = {
  status: string;
  page: string;
  live_execution: boolean;
  submits: boolean;
  live_authorized: boolean;
  primary_research_candidate: string;
  label: string;
  n: number;
  bankroll_cents: number;
  portfolio_risk_cents: number;
  entry_cents: number;
  fees: string;
  message?: string;
  unit_book: Record<string, { through_close_book_cents: number; stops: number; survivors: number; flat_loss_cents: number }>;
  clock: { t65_stops: number; t65_stops_ledger_settlement_yes: number; those_marked_at_settlement: number };
  runs: PairedRun[];
  capital_policy: CapitalPolicy;
  planned_risk_policy: PlannedRiskPolicy;
  disclaimers: string[];
};

export type ExecutionDiagnostics = {
  events: number;
  unresolved_events: number;
  partial_fills_modeled: number;
  stop_signals_without_a_fill: number;
  settlement_benchmarks: number;
  missing_entry_candle: number;
  missing_trade_file: number;
  depth_available_entry_rows: number;
  sequence_numbers_present: number;
  entry_quote_relations: Record<string, number>;
  exit_quote_relations: Record<string, number>;
  entry_bid_minus_nominal_80: Record<string, number>;
};

export type ExecutionValidationPage = {
  page: string;
  spec_id: string;
  configuration_id: string;
  separate_configuration_id: string;
  live_execution: string;
  submits: boolean;
  reference_evidence: string;
  simulated_evidence: string;
  actual_evidence: string;
  actual_fills: number;
  execution_aware_portfolio_pnl: string;
  comparison_status: string;
  comparison_reason: string;
  fees: {
    historical_book: string;
    snapshot: { applies_to_historical_book: boolean };
  };
  coverage: {
    order_book_depth_snapshots: string;
    order_book_deltas: string;
    feed_sequence_numbers: string;
    game_time_local_receive_timestamps: string;
    exchange_trade_timestamps: string;
    actual_order_records: string;
  };
  prospective_collector: {
    status: string;
    observations_collected: number;
    spec_frozen_at: string;
    submits?: boolean;
    websocket?: string;
    feed?: string;
    simulated_fills?: string;
    return_calculation?: string;
  };
  observation_policy?: {
    trigger: string;
    live_quote_trigger: string;
    latency: string;
    hypothetical_order_intent: string;
    entry_rest: string;
    entry_cancel: string;
    exit_priority: string;
    exit_fallback: string;
    return_calculation: string;
  };
  attribution: { gap_recharged: boolean; note: string };
  specification: { missing: string[] };
  books: Record<string, { benchmark_pnl_cents: number; diagnostics: ExecutionDiagnostics }>;
};

export type AustinReplay = {
  status: string;
  trade_id?: string;
  ticker?: string;
  game_date?: string;
  settlement?: string;
  csv_t40?: boolean;
  candle_path_not_fill?: boolean;
  path?: { t?: string; t_sec?: number; price_cents?: number; home_score?: number; away_score?: number; label?: string }[];
  marks?: Record<string, string | null>;
};
