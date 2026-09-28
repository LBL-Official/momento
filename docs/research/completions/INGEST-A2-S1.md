STEP ID: INGEST-A2-S1
WATERFALL: DATA-INGEST
TITLE: Continuous MLB waterstream (historical partition + forward + Kalshi discovery)
STATUS: CODE READY / BACKFILL_PARTIAL / IMPLEMENTED_NOT_DEPLOYED
DATE: 2026-08-26

SCOPE: Ingest plane only. No Data-Real writes. No W4 MarketState. No production.

CODE: crates/research-ingest INGEST.2.0.0, apps/research-ingest
DOCS: docs/research/backtesting_rebuild/ingest/WATERSTREAM_REPORT.md

TESTS: cargo test -p momento-research-ingest --offline (31 passed)
CLIPPY: cargo clippy -p momento-research-ingest -p momento-research-ingest-app --all-targets --no-deps --offline -- -D warnings (0)

NETWORK: StatsAPI schedule probe 2026-06-18 HTTP 200 (9 games). Live ingest --network refused. Kalshi live BLOCKED.
BACKFILL: not complete. 2024/2025 PBP UNAVAILABLE locally.
CLOUD: IMPLEMENTED_NOT_DEPLOYED

NEXT: Authorized LiveStatsApiSource window, or CTO-W4 (separate). Do not start W4 from this file.
