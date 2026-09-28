//! W7 SQL schema.

pub const MIGRATION_001_SQL: &str = r#"
CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS path_runs (
  run_id TEXT PRIMARY KEY,
  dataset_version TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  artifact_version TEXT NOT NULL,
  w5_dataset_version TEXT NOT NULL,
  w6_dataset_version TEXT NOT NULL,
  join_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS event_market_paths (
  path_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  game_id TEXT NOT NULL,
  game_pk TEXT NOT NULL,
  market_id TEXT NOT NULL,
  contract_side TEXT NOT NULL,
  observations INTEGER NOT NULL,
  synchronized INTEGER NOT NULL,
  UNIQUE (run_id, game_id, market_id, contract_side)
);

CREATE TABLE IF NOT EXISTS path_observations (
  path_observation_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  path_id TEXT NOT NULL,
  game_id TEXT NOT NULL,
  game_pk TEXT NOT NULL,
  market_id TEXT NOT NULL,
  ticker TEXT NOT NULL,
  contract_id TEXT NOT NULL,
  contract_side TEXT NOT NULL,
  observation_id TEXT NOT NULL,
  w5_synchronization_id TEXT NOT NULL,
  observation_kind TEXT NOT NULL,
  market_timestamp_utc TEXT,
  matched_state_timestamp_utc TEXT,
  event_lag_ms INTEGER,
  synchronization_status TEXT NOT NULL,
  synchronization_quality TEXT NOT NULL,
  join_status TEXT NOT NULL,
  timestamp_relation TEXT NOT NULL,
  trade_price_cents INTEGER,
  trade_size_hundredths INTEGER,
  source_observation_id TEXT,
  source_lineage TEXT NOT NULL,
  state_id TEXT,
  state_seq INTEGER,
  previous_state_id TEXT,
  previous_state_seq INTEGER,
  transition_id TEXT,
  transition_event_type TEXT,
  next_state_id TEXT,
  next_state_seq INTEGER,
  inning INTEGER,
  half TEXT,
  outs INTEGER,
  score_home INTEGER,
  score_away INTEGER,
  run_differential INTEGER,
  bases_bitmask INTEGER,
  batter_id TEXT,
  pitcher_id TEXT,
  balls INTEGER,
  strikes INTEGER,
  game_status TEXT,
  chrono_index INTEGER NOT NULL,
  previous_trade_price_cents INTEGER,
  price_change_cents INTEGER,
  cumulative_trade_count INTEGER NOT NULL,
  time_since_previous_trade_ms INTEGER,
  time_since_state_transition_ms INTEGER,
  observed_high_cents_so_far INTEGER,
  observed_low_cents_so_far INTEGER,
  distance_from_high_cents INTEGER,
  distance_from_low_cents INTEGER,
  prior_price_changes INTEGER NOT NULL,
  join_version TEXT NOT NULL,
  w5_dataset_version TEXT NOT NULL,
  w6_dataset_version TEXT NOT NULL,
  w7_version TEXT NOT NULL,
  UNIQUE (run_id, observation_id, contract_side)
);

CREATE TABLE IF NOT EXISTS state_segments (
  run_id TEXT NOT NULL,
  path_id TEXT NOT NULL,
  game_id TEXT NOT NULL,
  market_id TEXT NOT NULL,
  contract_side TEXT NOT NULL,
  state_id TEXT NOT NULL,
  state_seq INTEGER NOT NULL,
  observation_count INTEGER NOT NULL,
  first_market_timestamp_utc TEXT,
  last_market_timestamp_utc TEXT,
  PRIMARY KEY (run_id, path_id, state_id, first_market_timestamp_utc)
);

CREATE TABLE IF NOT EXISTS game_path_coverage (
  run_id TEXT NOT NULL,
  game_id TEXT NOT NULL,
  game_pk TEXT NOT NULL,
  observations INTEGER NOT NULL,
  synchronized INTEGER NOT NULL,
  before_first INTEGER NOT NULL,
  after_last INTEGER NOT NULL,
  at_event INTEGER NOT NULL,
  with_gap INTEGER NOT NULL,
  no_game_state INTEGER NOT NULL,
  coverage TEXT NOT NULL,
  PRIMARY KEY (run_id, game_id)
);

CREATE INDEX IF NOT EXISTS idx_w7_obs_game_time ON path_observations (game_id, market_timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_w7_obs_market_time ON path_observations (market_id, market_timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_w7_obs_contract ON path_observations (market_id, contract_side, market_timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_w7_obs_state ON path_observations (game_id, state_id);
CREATE INDEX IF NOT EXISTS idx_w7_obs_seq ON path_observations (game_id, state_seq);
CREATE INDEX IF NOT EXISTS idx_w7_obs_id ON path_observations (observation_id);
CREATE INDEX IF NOT EXISTS idx_w7_obs_price ON path_observations (trade_price_cents);
CREATE INDEX IF NOT EXISTS idx_w7_path_game ON event_market_paths (game_id);
"#;
