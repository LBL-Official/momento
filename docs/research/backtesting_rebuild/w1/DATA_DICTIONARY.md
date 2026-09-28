# W1 Data Dictionary (raw / catalog)

## v1 lake (unchanged)

| Name | Meaning |
|------|---------|
| `RawMarketEvent.received_at` | Collector ingestion clock. **Not** exchange time. |
| `RawMarketEvent.payload.created_time` | Trade exchange time when present |
| candle `end_period_ts` | End of 1-minute bucket |
| `OrderbookEvent` + `RestCandlestick` | 1m YES bid/ask **close**, not L2 |
| `OrderbookEvent` + `RestSnapshot` | Book at **ingest**, not game time |
| `DailyManifest.completeness_status` | v1 close/settled-day collection completeness |

## W1 derived

| Name | Meaning |
|------|---------|
| `lake_content_digest` | SHA-256 of sorted (path, file sha256) |
| `run_id` | `w1-` + first 16 hex of digest |
| `PartitionCoverage` | See COVERAGE.md |
| `StartingPriceClass` | STARTING_PRICE_UNVERIFIED unless market-open **price** is proven |
| `RawArtifactRef` | Pointer W2 may cite; not a PBP type |
| `IdentityStubV1.mlb_game_pk` | Always null in W1 |

Do not store invented mids, L2, or PBP in this dictionary.
