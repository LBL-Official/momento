
CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS replay_runs (
  run_id TEXT PRIMARY KEY,
  dataset_version TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  artifact_version TEXT NOT NULL,
  w7_dataset_version TEXT NOT NULL,
  w7_run_id TEXT NOT NULL,
  engine_version TEXT NOT NULL,
  strategy_name TEXT NOT NULL,
  strategy_version INTEGER NOT NULL,
  observability TEXT NOT NULL,
  ordering_contract TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS replay_events (
  replay_event_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  game_id TEXT NOT NULL,
  market_id TEXT NOT NULL,
  side TEXT NOT NULL,
  observation_id TEXT NOT NULL,
  market_timestamp_utc TEXT,
  strategy_state_before TEXT NOT NULL,
  strategy_state_after TEXT NOT NULL,
  event_type TEXT NOT NULL,
  price_cents INTEGER,
  state_id TEXT,
  state_seq INTEGER,
  synchronization_class TEXT NOT NULL,
  synchronization_quality TEXT NOT NULL,
  reason TEXT NOT NULL,
  observability TEXT NOT NULL,
  strategy_version INTEGER NOT NULL,
  w7_dataset_version TEXT NOT NULL,
  w8_engine_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS first01_opportunities (
  opportunity_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  game_id TEXT NOT NULL,
  market_id TEXT NOT NULL,
  side TEXT NOT NULL,
  first80_timestamp_utc TEXT,
  first80_observation_id TEXT,
  first80_price_cents INTEGER,
  first80_state_id TEXT,
  first80_state_seq INTEGER,
  confirmation_timestamp_utc TEXT,
  confirmation_observation_id TEXT,
  confirmation_state_id TEXT,
  confirmation_state_seq INTEGER,
  entry_eligible_timestamp_utc TEXT,
  entry_observation_id TEXT,
  entry_price_cents INTEGER,
  intent_proposed INTEGER NOT NULL,
  game_lock_timestamp_utc TEXT,
  game_lock_observation_id TEXT,
  replay_terminal_state TEXT NOT NULL,
  first80_sync_class TEXT,
  confirmation_sync_class TEXT,
  observability TEXT NOT NULL,
  strategy_version INTEGER NOT NULL,
  w7_dataset_version TEXT NOT NULL,
  UNIQUE (run_id, game_id)
);

CREATE INDEX IF NOT EXISTS idx_w8_ev_game ON replay_events (game_id, market_timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_w8_ev_type ON replay_events (event_type);
CREATE INDEX IF NOT EXISTS idx_w8_opp_game ON first01_opportunities (game_id);
