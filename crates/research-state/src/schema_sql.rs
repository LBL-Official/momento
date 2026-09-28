//! W6 SQL schema. Follows W2 sketch style with an applied SQLite migration.

pub const MIGRATION_001_SQL: &str = r#"
CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reconstruction_runs (
  run_id TEXT PRIMARY KEY,
  dataset_version TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  artifact_version TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  reconstruction_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS games (
  run_id TEXT NOT NULL,
  game_id TEXT NOT NULL,
  game_pk TEXT NOT NULL,
  official_date TEXT,
  events INTEGER NOT NULL,
  states INTEGER NOT NULL,
  transitions INTEGER NOT NULL,
  timed_events INTEGER NOT NULL,
  extra_inning INTEGER NOT NULL,
  walk_off INTEGER NOT NULL,
  terminal INTEGER NOT NULL,
  status TEXT NOT NULL,
  error TEXT,
  PRIMARY KEY (run_id, game_id),
  UNIQUE (run_id, game_pk)
);

CREATE TABLE IF NOT EXISTS game_states (
  state_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  game_id TEXT NOT NULL,
  game_pk TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  state_seq INTEGER NOT NULL,
  event_id TEXT,
  event_sequence INTEGER NOT NULL,
  source_event_id TEXT,
  canonical_timestamp TEXT,
  source_timestamp TEXT,
  inning INTEGER NOT NULL,
  half TEXT NOT NULL,
  outs INTEGER NOT NULL,
  score_home INTEGER NOT NULL,
  score_away INTEGER NOT NULL,
  run_differential INTEGER NOT NULL,
  bases_bitmask INTEGER NOT NULL,
  batter_id TEXT,
  pitcher_id TEXT,
  balls INTEGER,
  strikes INTEGER,
  pa_seq INTEGER,
  pa_phase TEXT NOT NULL,
  event_type TEXT,
  event_kind TEXT NOT NULL,
  extra_inning INTEGER NOT NULL,
  walk_off INTEGER NOT NULL,
  game_status TEXT NOT NULL,
  source_dataset TEXT NOT NULL,
  source_version TEXT NOT NULL,
  reconstruction_version TEXT NOT NULL,
  UNIQUE (run_id, game_id, state_seq),
  UNIQUE (run_id, game_id, state_id)
);

CREATE TABLE IF NOT EXISTS state_transitions (
  transition_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  game_id TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  sequence INTEGER NOT NULL,
  event_id TEXT NOT NULL,
  source_event_id TEXT NOT NULL,
  previous_state_id TEXT NOT NULL,
  resulting_state_id TEXT NOT NULL,
  event_timestamp TEXT,
  event_type TEXT NOT NULL,
  event_kind TEXT NOT NULL,
  score_delta_home INTEGER NOT NULL,
  score_delta_away INTEGER NOT NULL,
  out_delta INTEGER NOT NULL,
  bases_before INTEGER NOT NULL,
  bases_after INTEGER NOT NULL,
  batter_changed INTEGER NOT NULL,
  pitcher_changed INTEGER NOT NULL,
  inning_changed INTEGER NOT NULL,
  half_changed INTEGER NOT NULL,
  substitution INTEGER NOT NULL,
  review INTEGER NOT NULL,
  amendment INTEGER NOT NULL,
  delay INTEGER NOT NULL,
  walk_off INTEGER NOT NULL,
  reconstruction_version TEXT NOT NULL,
  UNIQUE (run_id, game_id, sequence),
  UNIQUE (run_id, game_id, event_id),
  FOREIGN KEY (previous_state_id) REFERENCES game_states(state_id),
  FOREIGN KEY (resulting_state_id) REFERENCES game_states(state_id)
);

CREATE INDEX IF NOT EXISTS idx_w6_state_game_seq ON game_states (game_id, state_seq);
CREATE INDEX IF NOT EXISTS idx_w6_state_game_time ON game_states (game_id, canonical_timestamp);
CREATE INDEX IF NOT EXISTS idx_w6_state_game_state_id ON game_states (game_id, state_id);
CREATE INDEX IF NOT EXISTS idx_w6_state_game_event ON game_states (game_id, event_id);
CREATE INDEX IF NOT EXISTS idx_w6_tr_game_seq ON state_transitions (game_id, sequence);
CREATE INDEX IF NOT EXISTS idx_w6_tr_game_time ON state_transitions (game_id, event_timestamp);
CREATE INDEX IF NOT EXISTS idx_w6_tr_game_event ON state_transitions (game_id, event_id);
CREATE INDEX IF NOT EXISTS idx_w6_tr_ids ON state_transitions (game_id, transition_id);
"#;
