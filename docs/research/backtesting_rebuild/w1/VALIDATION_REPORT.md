# W1 Validation Report

**Run:** `w1-d7e5d472e86268dc`  
**Lake:** `Backtesting Suite/Data-Real`  
**Job duration:** ~109s

## Integrity

| Check | Result |
|-------|--------|
| SHA-256 vs v1 manifests | **0 mismatches** |
| Gzip JSONL parse | **0 failures** |
| Parquet open/schema | **0 failures** |
| Two-sided pairing | **0 failures** |
| Findings | 25 × `TRADE_NOT_SORTED` (INFO). File order is not required to be chronological. **No raw repair.** |

## Tests executed (this W1 closeout)

```text
cargo fmt -p momento-research-data -p momento-research-collector
cargo check -p momento-research-data -p momento-research-collector --offline
cargo test  -p momento-research-data --offline
  lib envelope:     5 ok
  infrastructure:  13 ok
  w1_foundation:   15 ok (+1 ignored demo-slice writer)
cargo clippy -p momento-research-data -p momento-research-collector --offline
  4 warnings (too_many_arguments / type_complexity), 0 errors
```

FLAG-003 tests: `single_candlestick_copies_end_period_ts`, `candlestick_batch_preserves_last_end_period_ts_as_envelope_clock`, `candle_end_never_pairs_with_empty_source_timestamp`.

## Coverage snapshot (MLB)

| Year | COMPLETE_V1 days | Games | Markets | Trades | Candles/OB events |
|------|------------------|-------|---------|--------|-------------------|
| 2025 | 0 (5 empty probes) | 0 | 0 | 0 | 0 |
| 2026 | 13 (Jun 18–30); 17 empty Jun 1–17 | 172 | 344 | 3,396,041 | 312,887 |

Starting price rows: 410 (MLB+WNBA stubs) all `STARTING_PRICE_UNVERIFIED`. `market_open_price_cents` = none.

L2: `L2_HISTORICAL_UNAVAILABLE`. PBP: UNAVAILABLE.
