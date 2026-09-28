# Waterfall Step Completion Record

STEP ID: W7-EVENT-MARKET-PATH-S1
TITLE: Canonical Event / Market Path Engine
OBJECTIVE: Deterministic, anti-lookahead EventMarketPath joining accepted W5 TRADE observations onto W6 canonical MLB states. Do not start W8.

SCOPE: `crates/research-path`, `apps/research-w7`, Foundation/W7 artifacts, architecture/research docs. Read-only W5/W6 sqlite accessors already existed. No production trading trees. No Kalshi network. No L2 invention. No FIRST01 replay. No outcome labels. No W8.

INPUTS:
- W5 `Backtesting Suite/Foundation/W5/sync.sqlite` (`W5.COHORT.PBP_PLUS_MATCHED_TRADES.1`, run `w5-20260827T055849Z`)
- W6 `Backtesting Suite/Foundation/W6/state.sqlite` (`W6.PBP.CANONICAL_STATE.1`, run `w6-20260827T064141Z`)

OUTPUTS:
- `Backtesting Suite/Foundation/W7/path_report.json`, `coverage_report.json`
- `coverage/game_coverage.json`, `coverage/market_side_coverage.json`
- `examples/representative_event_market_paths.json`
- `validation/w7_validation_report.json`, `manifests/w7_manifest.json`
- `schema.sql`, `path.sqlite` (gitignored)
- `docs/research/backtesting_rebuild/W7_EVENT_MARKET_PATH.md`
- `docs/architecture/w7-event-market-path.md`

CODE CHANGES: EventMarketPath types, W5→W6 join (W5 AS-OF `prior_event_id` → W6 post-event state), causal descriptors, state segments, SQLite store, read-only query API including observational 80¢ prints, batch CLI.

DATA CHANGES: none to Data-Real; derived W7 only

SCHEMA CHANGES: `path_observations`, `event_market_paths`, `state_segments`, `game_path_coverage`, `path_runs` (W7.SCHEMA.1.0.0)

TESTS: `crates/research-path/tests/w7_path.rs` (18 tests: no future state, AT_EVENT post-state, between-events earlier state, causal no future extrema, next-state diagnostic only, retrieval-time ordering, idempotence, two sides, no synthesized missing side, BEFORE_FIRST/AFTER_LAST retained, TRADE-only, 80¢ observational query, real-data smoke). Workspace `cargo test --workspace`: 699 passed, 1 ignored. Clippy `--workspace --all-targets -- -D warnings`: pass.

VALIDATION: W5∩W6 overlap **1,684** games; **3,367** contract sides; **2,089,269** TRADE observations (reconciles to W5 source count). Synchronized (applicable W6 state): **1,662,032** = SYNCHRONIZED 65,987 + AT_EVENT 14 + SYNCHRONIZED_WITH_TIMESTAMP_GAP 1,596,031. BEFORE_FIRST_EVENT **369,484** and AFTER_LAST_EVENT **57,753** retained without applicable state. NO_GAME_STATE/UNJOINABLE/failures **0**. Complete W6-state coverage **0** (honest PARTIAL on all 1,684). Observational 80¢ prints **16,020** (not FIRST01). Anti-lookahead SQL: PASS. L2 invented = 0. W8 started = false.

KNOWN LIMITATIONS: Historical L2 UNAVAILABLE (TRADES_ONLY). Trade size UNAVAILABLE (not in W5 sqlite). Median event-to-market lag remains play-timed PBP vs continuous trades; gap class is not upgraded to EXACT. Pregame prints are BEFORE_FIRST. No game has a print in every W6 state (`games_with_complete_state_coverage=0`). W6-only games (2,141 OK reconstructions without W5 MATCHED trades) are not vanity-scanned. Substitutions/delays as distinct W6 events remain sparse.

LOOKAHEAD / DATA LEAKAGE REVIEW: Applicable state is W5 prior event’s W6 post-state with `matched_state_timestamp <= market_timestamp`. AFTER_LAST does not snap to last state. Causal descriptors use same-side observations `<= T` only. Next-state is diagnostic. Retrieval/generation timestamps do not order paths. Tests cover all ten anti-lookahead cases in the grant.

REPRODUCIBILITY: path_id / path_observation_id are sha256 of identity + dataset versions; `generated_at` is manifest-only.

DEPENDENCIES CREATED: `momento-research-path`, `momento-research-w7`

DEPENDENCIES RESOLVED: W5 SyncStore::open_existing / observations_for_game; W6 StateStore::open_existing / load_states / load_transitions

NEXT STEP: STOP. Do not start W8.

FINAL STATUS: COMPLETE (path layer). W8 not authorized and not started.
