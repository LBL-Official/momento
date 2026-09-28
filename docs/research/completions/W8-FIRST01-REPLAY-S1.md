# Waterfall Step Completion Record

STEP ID: W8-FIRST01-REPLAY-S1
TITLE: FIRST01 observational strategy replay
OBJECTIVE: Replay existing FIRST01 sequencing deterministically over the accepted W7 EventMarketPath. Answer when FIRST01 would have triggered. Do not start W9.

SCOPE: `crates/research-replay`, `apps/research-w8`, Foundation/W8 artifacts, architecture/research docs. W7 read-only accessors already existed. No production trading trees. No Kalshi network. No L2 invention. No fills. No P&L. No outcome labels. No W9.

INPUTS:
- W7 `Backtesting Suite/Foundation/W7/path.sqlite` (`W7.EVENT_MARKET_PATH.1`, run `w7-20260827T070349Z`)
- Frozen FIRST01 constants `crates/research-strategies` v1 (80/81/83/89)
- Live sequencing (read-only) `strategies/mlb/src/{quote,strategy,state}.rs`

OUTPUTS:
- `Backtesting Suite/Foundation/W8/replay_report.json`, `coverage_report.json`, `coverage/w8_counts.json`
- `examples/representative_first01_replay.json`
- `validation/w8_validation_report.json`, `manifests/w8_manifest.json`
- `schema.sql`, `replay.sqlite` (gitignored)
- `docs/research/backtesting_rebuild/W8_FIRST01_REPLAY.md`
- `docs/architecture/w8-first01-replay.md`

CODE CHANGES: FIRST01 replay machine mirroring live observe() order; append-only event ledger; opportunity records; SQLite store; batch CLI. Observability `TRADE_PRINT_NOT_YES_BID`. No Risk/Execution/Kalshi deps.

DATA CHANGES: none to Data-Real; derived W8 only

SCHEMA CHANGES: `replay_events`, `first01_opportunities`, `replay_runs` (W8.SCHEMA.1.0.0)

TESTS: `crates/research-replay/tests/w8_replay.rs` (27 tests: no future observation, no future W6 state, FIRST80 first qualifying, same-side 81, opposite-side 81 rejected, pause ≠ lock, 89 lock, lock does not liquidate, lock before/between 80–81, multiple 80 → one FIRST80, no duplicate opportunities, independent sides, missing W6 not fabricated, gap class preserved, AT_EVENT uses W7 state, determinism/idempotence, truncation gate, no risk/execution/P&L/settlement, same-timestamp observation_id order). Workspace `cargo test --workspace`: 726 passed, 1 ignored. Clippy `--workspace --all-targets -- -D warnings`: pass.

VALIDATION: W7 cohort **1,684** games; **3,367** sides; **2,089,269** observations (reconciles). 80¢ prints **16,020** ≠ FIRST80 **1,558**. Confirm81 **1,483**. Entry-eligible **1,306**. GAME_LOCK **1,528**. Price pause **19,384**. Ambiguous **0**. State-linked triggers **5,792**. Without W6 **83**. Sync breakdown: SYNCHRONIZED **266**, AT_EVENT **0**, SYNCHRONIZED_WITH_TIMESTAMP_GAP **5,526**. Anti-lookahead truncation: PASS. Fills = 0. P&L = 0. Sent to Risk/Execution = false. W9 started = false.

ARTIFACTS: Foundation/W8 reports + gitignored `replay.sqlite`

GOOGLE DRIVE OUTPUT: none

GOOGLE SHEETS OUTPUT: none

PERFORMANCE: release replay of 2,089,269 observations completed in ~47s including compile.

KNOWN LIMITATIONS: Historical L2 UNAVAILABLE — qualifying price is TRADE print, not YES bid. Maker `bid < ask` UNAVAILABLE and not invented. One proposed intent per opportunity (live remainder Builds after partial fill are not modeled). `PositionBuilding`/`PositionOpen` never entered (require fills). Research `EntryEngine` same-tick 81 clock is not used; live observe() clock is. W6-only games and the 8,428-market catalog were not scanned.

LOOKAHEAD / DATA LEAKAGE REVIEW: Observations sorted by `market_timestamp_utc, observation_id`. Truncation test: full path vs path truncated at T identical through T; appending later prints cannot alter events ≤ T. `next_state_*` never read. No settlement/outcome.

REPRODUCIBILITY: `replay_event_id` / `opportunity_id` are sha256 of identity + W7 dataset version + event type; `generated_at` is manifest-only.

DEPENDENCIES CREATED: `momento-research-replay`, `momento-research-w8`

DEPENDENCIES RESOLVED: W7 PathStore::open_existing / list_game_ids / path_for_game / observation_count / run_meta

NEXT STEP: STOP. Do not start W9.

FINAL STATUS: COMPLETE (observational replay). W9 not authorized and not started.
