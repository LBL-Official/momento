
CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_runs (
  run_id TEXT PRIMARY KEY,
  dataset_version TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  artifact_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS synchronized_observations (
  synchronization_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  game_id TEXT NOT NULL,
  game_pk TEXT NOT NULL,
  market_id TEXT NOT NULL,
  ticker TEXT NOT NULL,
  contract_id TEXT NOT NULL,
  contract_side TEXT NOT NULL,
  observation_id TEXT NOT NULL,
  observation_type TEXT NOT NULL,
  market_timestamp_source TEXT NOT NULL,
  source_timestamp_kind TEXT NOT NULL,
  market_timestamp_utc TEXT,
  retrieval_timestamp TEXT,
  prior_event_id TEXT,
  prior_event_timestamp_utc TEXT,
  next_event_id TEXT,
  next_event_timestamp_utc TEXT,
  timestamp_relation TEXT NOT NULL,
  event_to_market_lag_ms INTEGER,
  market_to_next_event_ms INTEGER,
  synchronization_status TEXT NOT NULL,
  synchronization_method TEXT NOT NULL,
  synchronization_quality TEXT NOT NULL,
  state_seq INTEGER,
  inning INTEGER,
  half TEXT,
  outs INTEGER,
  score_home INTEGER,
  score_away INTEGER,
  run_differential INTEGER,
  balls INTEGER,
  strikes INTEGER,
  extra_inning INTEGER,
  pre_state_seq INTEGER,
  pre_inning INTEGER,
  pre_outs INTEGER,
  pre_score_home INTEGER,
  pre_score_away INTEGER,
  prior_market_observation_id TEXT,
  next_market_observation_id TEXT,
  elapsed_from_prior_obs_ms INTEGER,
  elapsed_to_next_obs_ms INTEGER,
  last_trade_cents INTEGER,
  first_observed_price_cents INTEGER,
  source_id TEXT,
  source_lineage TEXT NOT NULL,
  dataset_version TEXT NOT NULL,
  UNIQUE (run_id, observation_id)
);

CREATE TABLE IF NOT EXISTS game_coverage (
  run_id TEXT NOT NULL,
  game_id TEXT NOT NULL,
  game_pk TEXT NOT NULL,
  timed_events INTEGER NOT NULL,
  observations INTEGER NOT NULL,
  synchronized INTEGER NOT NULL,
  at_event INTEGER NOT NULL,
  before_first INTEGER NOT NULL,
  after_last INTEGER NOT NULL,
  first_pbp_utc TEXT,
  last_pbp_utc TEXT,
  first_market_utc TEXT,
  last_market_utc TEXT,
  PRIMARY KEY (run_id, game_id)
);

CREATE INDEX IF NOT EXISTS idx_sync_game_event_time
  ON synchronized_observations (game_id, prior_event_timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_sync_market_time
  ON synchronized_observations (market_id, market_timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_sync_game_market_time
  ON synchronized_observations (game_id, market_timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_sync_contract_time
  ON synchronized_observations (contract_id, market_timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_sync_observation
  ON synchronized_observations (observation_id);
CREATE INDEX IF NOT EXISTS idx_sync_event_id
  ON synchronized_observations (game_id, prior_event_id);
CREATE INDEX IF NOT EXISTS idx_sync_sync_id
  ON synchronized_observations (synchronization_id);
