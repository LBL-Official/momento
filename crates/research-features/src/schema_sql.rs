//! B1 SQLite schema.

pub const MIGRATION_001_SQL: &str = r#"
CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feature_runs (
  run_id TEXT PRIMARY KEY,
  dataset_version TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  artifact_version TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  engine_version TEXT NOT NULL,
  feature_schema_version TEXT NOT NULL,
  w5_dataset_version TEXT,
  w6_run_id TEXT NOT NULL,
  w7_run_id TEXT NOT NULL,
  w8_run_id TEXT NOT NULL,
  observability TEXT NOT NULL,
  ordering_contract TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entry_snapshots (
  snapshot_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  game_id TEXT NOT NULL,
  market_id TEXT NOT NULL,
  contract_side TEXT NOT NULL,
  entry_timestamp TEXT NOT NULL,
  entry_trade_price_cents INTEGER NOT NULL,
  execution_status TEXT NOT NULL,
  w8_opportunity_id TEXT NOT NULL,
  w5_observation_id TEXT NOT NULL,
  official_date TEXT,
  split_group TEXT NOT NULL,
  settlement TEXT NOT NULL,
  bound_team_lead INTEGER,
  inning INTEGER,
  p_start_cents INTEGER,
  start_sentiment TEXT,
  start_to_entry_move_cents INTEGER,
  a1_entry_target TEXT,
  payload_json TEXT NOT NULL,
  UNIQUE (run_id, game_id)
);

CREATE INDEX IF NOT EXISTS idx_b1_game ON entry_snapshots (game_id);
CREATE INDEX IF NOT EXISTS idx_b1_date ON entry_snapshots (official_date);
"#;
