//! SQL sketch for W3 derived tables. Not a production database.

pub const W3_SCHEMA_SQL: &str = r#"
-- Research-only. W3 derived. Never Data-Real.
-- Reuses W1 provenance pointers; does not fork LakeCatalogV1.

CREATE TABLE mlb_games (
  canonical_game_id TEXT PRIMARY KEY,
  game_pk TEXT,
  official_date TEXT,
  lifecycle TEXT NOT NULL,
  identity_status TEXT NOT NULL,
  source_artifact TEXT,
  source_sha256 TEXT,
  reconstruction TEXT NOT NULL,
  fixture_kind TEXT NOT NULL
);

CREATE TABLE pbp_events (
  event_id TEXT PRIMARY KEY,
  canonical_game_id TEXT NOT NULL,
  sequence INTEGER NOT NULL,
  source_event_id TEXT,
  source_timestamp TEXT,
  reconstruction_status TEXT NOT NULL
);

CREATE TABLE game_states (
  canonical_game_id TEXT NOT NULL,
  state_seq INTEGER NOT NULL,
  inning INTEGER,
  half TEXT,
  outs INTEGER,
  PRIMARY KEY (canonical_game_id, state_seq)
);

CREATE TABLE reconstruction_runs (
  run_id TEXT PRIMARY KEY,
  generated_at TEXT NOT NULL,
  committed_count INTEGER NOT NULL,
  valid_count INTEGER NOT NULL,
  failed_count INTEGER NOT NULL
);

CREATE TABLE reconstruction_anomalies (
  run_id TEXT NOT NULL,
  game_pk TEXT,
  code TEXT NOT NULL,
  message TEXT NOT NULL
);
"#;
