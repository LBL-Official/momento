//! Storage design for later warehouse joins (W3/W4). Not a live database.

pub const SCHEMA_SQL: &str = r#"
-- W2 canonical event stream. Market tables are out of scope (W3).
-- Partition: season, official_date. Version every transform.

CREATE TABLE mlb_source_files (
  file_id            TEXT PRIMARY KEY,
  source             TEXT NOT NULL,
  path               TEXT NOT NULL,
  sha256             TEXT NOT NULL,
  retrieved_at       TIMESTAMPTZ,
  parser_version     TEXT NOT NULL,
  fixture_kind       TEXT NOT NULL,
  UNIQUE (path, sha256)
);

CREATE TABLE mlb_games (
  canonical_game_id  TEXT PRIMARY KEY,
  source             TEXT NOT NULL,
  source_game_id     TEXT NOT NULL,
  season             INT NOT NULL,
  official_date      DATE NOT NULL,
  home_team_source_id TEXT,
  away_team_source_id TEXT,
  venue_source_id    TEXT,
  game_number        INT NOT NULL DEFAULT 1,
  competition        TEXT NOT NULL,
  identity_version   TEXT NOT NULL,
  UNIQUE (source, source_game_id)
);

CREATE TABLE mlb_identity_map (
  canonical_game_id  TEXT NOT NULL REFERENCES mlb_games (canonical_game_id),
  alias_kind         TEXT NOT NULL, -- official_pk | kalshi_event_ticker | kalshi_game_id
  alias_value        TEXT NOT NULL,
  match_status       TEXT NOT NULL, -- UNMAPPED|MAPPED|UNMATCHED|COLLISION|AMBIGUOUS
  provenance_note    TEXT NOT NULL,
  PRIMARY KEY (alias_kind, alias_value)
);

CREATE TABLE mlb_raw_event_refs (
  raw_ref_id         TEXT PRIMARY KEY,
  file_id            TEXT NOT NULL REFERENCES mlb_source_files (file_id),
  source_event_id    TEXT NOT NULL,
  byte_offset        BIGINT,
  line_no            BIGINT,
  payload_sha256     TEXT NOT NULL
);

CREATE TABLE mlb_canonical_events (
  event_id           TEXT PRIMARY KEY,
  canonical_game_id  TEXT NOT NULL REFERENCES mlb_games (canonical_game_id),
  sequence           INT NOT NULL,
  source_event_id    TEXT NOT NULL,
  source_timestamp   TIMESTAMPTZ,
  source_timestamp_kind TEXT NOT NULL,
  collector_timestamp TIMESTAMPTZ,
  inning             SMALLINT,
  half_inning        TEXT,
  outs_before        SMALLINT,
  outs_after         SMALLINT,
  score_home_before  SMALLINT,
  score_away_before  SMALLINT,
  score_home_after   SMALLINT,
  score_away_after   SMALLINT,
  event_type         TEXT NOT NULL,
  runs_scored        SMALLINT,
  parser_version     TEXT NOT NULL,
  normalization_version TEXT NOT NULL,
  schema_version     TEXT NOT NULL,
  observability_json JSONB NOT NULL,
  raw_ref_id         TEXT REFERENCES mlb_raw_event_refs (raw_ref_id),
  UNIQUE (canonical_game_id, sequence),
  UNIQUE (canonical_game_id, source_event_id)
);

CREATE TABLE mlb_game_states (
  canonical_game_id  TEXT NOT NULL REFERENCES mlb_games (canonical_game_id),
  state_seq          INT NOT NULL,
  event_id           TEXT NOT NULL REFERENCES mlb_canonical_events (event_id),
  inning             SMALLINT NOT NULL,
  half_inning        TEXT NOT NULL,
  outs               SMALLINT NOT NULL,
  game_status        TEXT NOT NULL,
  score_home         SMALLINT NOT NULL,
  score_away         SMALLINT NOT NULL,
  runners_json       JSONB,
  machine_version    TEXT NOT NULL,
  PRIMARY KEY (canonical_game_id, state_seq)
);

-- W2 PBP transitions only. Canonical StateTransition / GameMarketEpisode are W5.
CREATE TABLE mlb_pbp_transitions (
  canonical_game_id  TEXT NOT NULL,
  sequence           INT NOT NULL,
  event_id           TEXT NOT NULL,
  before_state_seq   INT NOT NULL,
  after_state_seq    INT NOT NULL,
  trigger            TEXT NOT NULL,
  machine_version    TEXT NOT NULL,
  PRIMARY KEY (canonical_game_id, sequence)
);

-- Identity-only join keys. No reconstructed prices (W3).
CREATE TABLE mlb_market_refs (
  canonical_game_id  TEXT NOT NULL REFERENCES mlb_games (canonical_game_id),
  side               TEXT NOT NULL, -- TEAM_A_YES | TEAM_B_YES
  kalshi_game_id     TEXT,
  kalshi_market_id   TEXT,
  ticker             TEXT,
  event_ticker       TEXT,
  mlb_game_pk        TEXT, -- NULL while UNMAPPED
  match_status       TEXT NOT NULL,
  starting_price_class TEXT NOT NULL, -- STARTING_PRICE_UNVERIFIED in W2
  reconstruction_status TEXT NOT NULL, -- UNAVAILABLE in W2
  scope              TEXT NOT NULL, -- W2_IDENTITY_ONLY
  PRIMARY KEY (canonical_game_id, side)
);

CREATE TABLE mlb_event_time (
  canonical_game_id  TEXT NOT NULL,
  sequence           INT NOT NULL,
  outs_elapsed       INT NOT NULL,
  regulation_outs    INT NOT NULL,
  regulation_outs_remaining INT NOT NULL,
  extra_inning       BOOLEAN NOT NULL,
  definition_version TEXT NOT NULL,
  PRIMARY KEY (canonical_game_id, sequence)
);

CREATE TABLE mlb_event_sequences (
  canonical_game_id  TEXT PRIMARY KEY,
  event_ids          TEXT[] NOT NULL,
  sequence_version   TEXT NOT NULL
);

CREATE TABLE mlb_outcomes (
  canonical_game_id  TEXT PRIMARY KEY,
  final_home         SMALLINT NOT NULL,
  final_away         SMALLINT NOT NULL,
  winner             TEXT NOT NULL,
  observability      TEXT NOT NULL DEFAULT 'OUTCOME_LABEL'
);

CREATE TABLE mlb_coverage (
  canonical_game_id  TEXT,
  season             TEXT,
  official_date      DATE,
  pbp_status         TEXT NOT NULL,
  reconstruction_status TEXT NOT NULL,
  notes              TEXT
);

CREATE INDEX idx_events_game_seq ON mlb_canonical_events (canonical_game_id, sequence);
CREATE INDEX idx_states_outs_remain ON mlb_event_time (regulation_outs_remaining, extra_inning);
CREATE INDEX idx_states_sit ON mlb_game_states (inning, half_inning, outs, score_home, score_away);
-- Later W4: JOIN mlb_game_states to market_states ON sync keys, not on invented timestamps.
"#;

pub const INTENDED_QUERIES: &str = r#"
-- W4 (not implemented): states around first 80% Kalshi touch
-- SELECT s.* FROM mlb_game_states s
-- JOIN w4_sync_index x ON x.canonical_game_id = s.canonical_game_id
-- WHERE x.first_80_touch_seq IS NOT NULL
--   AND s.state_seq BETWEEN x.first_80_touch_seq - N AND x.first_80_touch_seq;

-- PBP sequence preceding a market move (W4)
-- SELECT e.* FROM mlb_canonical_events e
-- WHERE e.canonical_game_id = $1 AND e.sequence <= $2 ORDER BY e.sequence;

-- One out, runner on third, tied, bottom 9
-- SELECT * FROM mlb_game_states
-- WHERE inning = 9 AND half_inning = 'BOTTOM' AND outs = 1
--   AND score_home = score_away
--   AND runners_json->>'third' IS NOT NULL;

-- Every historical state at N regulation outs remaining
-- SELECT * FROM mlb_event_time WHERE regulation_outs_remaining = $1;
"#;
