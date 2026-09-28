# W4-D — MATCHED market trade backfill

**Status:** VALIDATING (ingest + reconstruct; numbers in
`Backtesting Suite/Foundation/W4/matched_trade_coverage.json`)

This is **DATA-INGEST / W4 market-evidence** expansion. It is **not W5**.

## MATCHED identity ≠ observed historical market data

A market can be correctly linked to a `GameId` (`game_pk` OBSERVED from
StatsAPI; ticker mapped by unique observed abbreviation suffix) while having
**no historical price observations**.

```text
MATCHED identity
    ≠
observed historical market data

MATCHED + TRADES_ONLY
    = valid GameId-linked price-path research
      (raw trades exist, reconstructed on the existing MarketPath schema)

MATCHED + METADATA_ONLY
    = retained identity, not price-path usable
```

Do not remap games to increase coverage. Do not fuzzy-match. Do not treat
timing coincidence as identity. The existing authoritative MATCHED mapping is
reused as-is.

## Sources identified

| Source | Identifier | Used? | Why |
|---|---|---|---|
| Data-Real lake COMPLETE 2026-06-18..30 | lake ticker / raw trades | **No** | Zero date overlap with MATCHED catalog (2025-04-16..2026-04-16) |
| MATCHED discovery envelopes | Kalshi ticker | **No (trades)** | Landed `--kalshi-metadata-only`; `trades_status=NOT_REQUESTED` |
| Existing 238 TRADES_ONLY paths | Kalshi ticker | **No** | All UNMATCHED June 2026; left untouched |
| Kalshi `GET /trade-api/v2/historical/trades` | **same ticker string as MATCHED pair** | **Yes** | Deterministic ticker → `MarketId`; source `created_time` |

Pacific calendar day of `official_date` is the fetch window (`day_window`).
Midnight-span games may be truncated by that contract; that is a coverage
limit, not widened here.

Retrieval time is provenance only. It is never the trade event time.

## What is ingested

For each legitimate trade:

- source `trade_id`
- market ticker
- source/exchange timestamp (`created_time`)
- retrieval timestamp
- integer-cent YES price (`yes_price_dollars`; fail-closed if finer than cents)
- size (`count_fp`) when present
- sidecar path + payload SHA-256 + ingestion run id

Not inferred: bid, ask, spread, depth, queue, maker/taker, executable price,
fill probability, L2, settlement-as-price.

Empty historical fetch is honest `MATCHED + METADATA_ONLY`.

## Reconstruction

Reuse existing W4 `MarketPath`. Sidecar trades become `RawMarketEvent`
`endpoint=matched_historical_trades`. Completeness stays `TRADES_ONLY` when
trades exist. Trades never upgrade to L2.

UNMATCHED `price_path_compact.jsonl` (238 paths) is not rewritten.

## CLI

```text
cargo run --release -p momento-research-ingest-app -- matched-trades-backfill \
  --authorize-network ENABLE_RESEARCH_INGEST_NETWORK \
  --pairs "Backtesting Suite/Foundation/Ingest/runs/<run>/game_market_pairs.json" \
  --lake "Backtesting Suite/Data-Real" \
  --out "Backtesting Suite/Foundation/Ingest"

cargo run --release -p momento-research-w4 -- --reconstruct-matched-price-paths \
  --handoff "Backtesting Suite/Foundation/Ingest/runs/<run>/w1_handoff.json" \
  --pairs "Backtesting Suite/Foundation/Ingest/runs/<run>/game_market_pairs.json" \
  --out "Backtesting Suite/Foundation/W4" \
  --lake "Backtesting Suite/Data-Real"
```

`--discover-only` identifies sources without network fetch.

## 80 / 81 / 89

Exact integer-cent **trade print** counts. Observability statistics only.
Not FIRST01 triggers. Not strategy replay.

## W5

Not started. No `SynchronizedState`, no clocks, no PBP↔market join.
