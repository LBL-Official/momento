# Waterfall Step Completion Record

STEP ID: W6-STATE-S1
TITLE: Canonical MLB GameState / StateTransition engine
OBJECTIVE: Deterministic, fail-closed, time-addressable MLB game truth from W3 PBP. Do not start W7.

SCOPE: `crates/research-state`, `apps/research-w6`, Foundation/W6 artifacts, architecture/research docs. Strictly necessary W3 occupancy parse fix (`runners[]` is a movement log). No production trading trees. No Kalshi network. No L2 invention. No FIRST01. No W7 paths.

INPUTS: StatsAPI PBP landing envelopes under `Backtesting Suite/Foundation/Ingest/landing/mlb_statsapi`

OUTPUTS:
- `Backtesting Suite/Foundation/W6/reconstruction_report.json`
- `manifests/w6_manifest.json`, `validation/w6_validation_report.json`
- `schema.sql`, `state.sqlite` (gitignored)
- `docs/research/backtesting_rebuild/W6_STATE_ENGINE.md`
- `docs/architecture/w6-state-engine.md`

CODE CHANGES: GameState, StateTransition, fingerprints, PA tracker, `state_at_or_before(T)`, fail-closed validation, SQLite store, batch CLI. W3 `runners_from_play` last-base-per-player.

DATA CHANGES: none to Data-Real; derived W6 only

SCHEMA CHANGES: `game_states`, `state_transitions`, `games`, `reconstruction_runs` (W6.SCHEMA.1.0.0)

TESTS: `crates/research-state/tests/w6_state.rs` (30 tests). Workspace `cargo test --workspace`: 681 passed, 1 ignored. Clippy `--workspace --all-targets -- -D warnings`: pass.

VALIDATION: 3,848 envelopes discovered; 3,825 reconstructed; 23 fail-closed `FINAL_TIE`; 2,377/2,377 mapped-pair game_pks reconstructed; 293,775 events; 297,600 states; 293,775 transitions

KNOWN LIMITATIONS: Play-level PBP (no pitch rows); no handedness/lineup slot; substitutions/delays/amendments not separate source rows; 23 tied-final games fail closed; remaining time UNAVAILABLE

LOOKAHEAD / DATA LEAKAGE REVIEW: `state_at_or_before` never returns ts > T; pre-game untimed; remaining time UNAVAILABLE; tests cover market-before-event ≠ post-event state

REPRODUCIBILITY: fingerprints exclude generation/retrieval time; same source → same identities

DEPENDENCIES CREATED: `momento-research-state`, `momento-research-w6`

DEPENDENCIES RESOLVED: W2 GameId; W3 replay/ingest

NEXT STEP: STOP. Do not start W7.

FINAL STATUS: COMPLETE (engine). 23 games fail closed (`FINAL_TIE`), classified, not repaired.
