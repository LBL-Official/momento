# CTO-W1 acceptance candidate (10/10)

**Filled by:** W1 implementation agent (2026-08-26)  
**Bar:** [`W1_ACCEPTANCE_CRITERIA.md`](../W1_ACCEPTANCE_CRITERIA.md)  
**CTO signature file:** [`W1_ACCEPTANCE_PACKAGE.md`](../W1_ACCEPTANCE_PACKAGE.md) — **not** signed here.

This file is the evidence pack so the CTO can treat W1 as an **acceptance candidate**. It does not self-close the waterfall.

```text
Status: 10/10 PASS (W1 agent evidence)
CTO decision: PENDING (ACCEPTED / CLOSED | REJECTED | RETURN TO W1)
```

## All acceptance criteria

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | Raw-data immutability | **PASS** | Real job `w1-d7e5d472e86268dc`: `checksum_mismatches=0`, `gzip_failures=0`, `parquet_failures=0`, `pairing_failures=0`. Outputs only under `Backtesting Suite/Foundation/W1/`. `LakeWriteGuard` + test `overwrite_guard_blocks_lake_writes`. |
| 2 | Provenance | **PASS** | `provenance_index.json`, `source_inventory.json`, envelope `ingestion_timestamp` vs `source_timestamp`+kind. Collector clock is not copied onto trade/PIT exchange fields. |
| 3 | Observability explicit | **PASS** | `observability_contract.json`; L2 = `L2_HISTORICAL_UNAVAILABLE`; candles not L2; test `observability_never_upgrades_l2_or_pbp`; orderbook layer notes say RestCandlestick ≠ L2. |
| 4 | Timestamps (FLAG-003) | **PASS** | `CandleEnd` always has `source_timestamp` (`candle_end_never_pairs_with_empty_source_timestamp`). Single and batch gzip lines copy `end_period_ts`. PIT `markets/orderbook` is `IngestOnly`. `received_at` is ingestion only. |
| 5 | Coverage honesty | **PASS** | `availability_audit.json`: 2026-06-18…30, **13** COMPLETE_V1 days, **172** games, **344** contracts. 2025: 0 complete / 5 empty probes. PBP/L2/starting-price **UNAVAILABLE**. First candle ≠ `MARKET_OPEN_PRICE`. |
| 6 | Ledger integrity | **PASS** | Implementation IDs are `W1-LEDGER-A*`. PLAN records are `docs/research/completions/PLAN-W1-*.md`. Alias table: `REGISTRY_ID_MAPPING.md`. `w1_documentation_complete` is fixture-parse, **not** `fill_ledger.all_complete()`. PLAN-W1-A8 **DEFERRED**. |
| 7 | Tests actually run | **PASS** | Commands below. 0 failures. Clippy: 4 warnings (`too_many_arguments` / `type_complexity`), 0 errors. |
| 8 | Documentation package | **PASS** | `docs/research/backtesting_rebuild/w1/` + `Backtesting Suite/Foundation/W1/` + fixtures + `PBP_SOURCE_MATRIX.md`. |
| 9 | Google reporting honesty | **PASS** | `google_publish.json` = `GOOGLE_PUBLISH_PENDING`. Local CSVs exist. Drive folder `1K3EBXFRPqteRLccRZH99Tv4Ql1CJwV0n` created; **not** claimed as published success. Sheets MCP `needsAuth`. Reporting engine is CTO-W11. |
| 10 | Production isolation | **PASS** | No edits to `strategies/mlb`, risk, execution, live config, trading transport, or Data-Real. Fence test: Cargo.toml has no `momento-risk` / `momento-execution` / `momento-strategy-mlb`. Production orders: **0**. |

## Integrity (no violations)

From `Backtesting Suite/Foundation/W1/integrity_report.json`:

```text
checksum_mismatches = 0
gzip_failures       = 0
parquet_failures    = 0
pairing_failures    = 0
```

25 × `TRADE_NOT_SORTED` at **INFO** (file order ≠ chronological). **Not repaired.** Not an integrity failure.

## Tests run (this closeout)

```text
cargo fmt -p momento-research-data -p momento-research-collector
cargo check -p momento-research-data -p momento-research-collector --offline
cargo test  -p momento-research-data --offline
  lib envelope:     5 ok
  infrastructure:  13 ok
  w1_foundation:   15 ok (+1 ignored writer)
cargo clippy -p momento-research-data -p momento-research-collector --offline
  4 warnings, 0 errors
```

W1-specific: checksum replay (real job), `no_synthetic_l2_from_candlesticks` (infrastructure), demo≠real, non-overwrite, timestamp kinds, identity hash vs live helpers, namespaced ledger IDs.

## Known limitations (honest, not FAILs)

- No historical L2; no PBP; no proven market-open prices.
- 2025 MLB = empty probes only.
- 2026 outside Jun 18–30 not in this lake (Jun 1–17 PROBE_EMPTY).
- Batch candle gzip line: envelope `source_timestamp` = **last** `end_period_ts` in that line; per-bar clocks remain in `payload.candlesticks[]`.
- `fill_ledger` still marks W1-LEDGER steps complete in one job; those IDs are **not** PLAN completeness.
- Clippy nits remain (argument count).

## Outstanding flags

| Flag | After this pack |
|------|-----------------|
| FLAG-001 | **Resolved for W1:** `W1-LEDGER-*` vs `PLAN-W1-*` |
| FLAG-002 | **Resolved for W1:** documentation completeness ≠ `all_complete()` |
| FLAG-003 | **Resolved:** CandleEnd requires `source_timestamp` |
| FLAG-004 | Remaining REVIEW: envelope observability is payload-presence OBSERVED; PIT consumers must use `IngestOnly` |
| FLAG-008 | PLAN-W1-A8 still **DEFERRED** |
| FLAG-017 | Control VALIDATING until CTO signs `W1_ACCEPTANCE_PACKAGE.md` |

## Production impact

**NONE**

## Next step (after CTO ACCEPTED / CLOSED)

Do **not** start automatically. CTO may then authorize **CTO-W3 Kalshi market reconstruction**. CTO-W2 real PBP remains BLOCKED. PLAN-W1-A8 remains DEFERRED.
