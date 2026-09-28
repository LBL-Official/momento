# Waterfall Step Completion Record

STEP ID: W5-SYNC-S1
TITLE: MLB event ↔ Kalshi market time synchronization
OBJECTIVE: Deterministic anti-lookahead AS-OF join of W3 PBP timelines to MATCHED Kalshi trade observations for the 1,684-game research cohort. Do not start W6.

SCOPE: `crates/research-sync`, `apps/research-w5`, Foundation/W5 artifacts, architecture docs. No production trading trees. No Kalshi network. No L2 invention. No W6 tensors.

INPUTS: committed StatsAPI PBP landing; MATCHED trade sidecars; `game_market_pairs.json` from ingest-20260826T095038Z-2bc3d10b5833

OUTPUTS:
- `Backtesting Suite/Foundation/W5/synchronization_report.json`
- `coverage_report.json`, `timestamp_quality_report.json`, `representative_synchronized_examples.json`
- `schema.sql`, `sync.sqlite` (gitignored)
- `docs/architecture/w5-synchronization.md`
- `docs/research/backtesting_rebuild/W5_EVENT_MARKET_SYNC.md`

CODE CHANGES: AS-OF join, UTC time contract, pre/post event state refs, SQLite store, batch engine, CLI `--sync`

DATA CHANGES: none to Data-Real; derived W5 only

SCHEMA CHANGES: `synchronized_observations`, `game_coverage`, `sync_runs` (W5.SCHEMA.1.0.0)

TESTS: `crates/research-sync/tests/w5_sync.rs` (34 tests: UTC, AS-OF, AT_EVENT, leakage, identity, two sides, idempotence, TRADE-only)

VALIDATION: 1,684 games evaluated; 3,368 contract sides attempted; 2,089,269 TRADE observations classified; L2 invented = 0; clock correction = false

KNOWN LIMITATIONS: Historical L2 UNAVAILABLE (TRADES_ONLY honesty). Median event-to-market lag ~70s because PBP is play-timed and trades are continuous; lag >5s is `SYNCHRONIZED_WITH_TIMESTAMP_GAP`, not silently EXACT. Pregame prints are `BEFORE_FIRST_EVENT`. No game has 100% in-window prints (`games_successfully_synchronized=0`, all 1,684 partial). 3,367/3,368 sides had at least one successful AS-OF.

NEXT STEP: STOP. Do not start W6.
STATUS: COMPLETE (join layer). W6 not authorized.
