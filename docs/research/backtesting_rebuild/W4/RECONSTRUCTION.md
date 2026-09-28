# W4 reconstruction (price-path foundation)

**TRADES_ONLY is not a failed dataset.** It is a valid historical price-path
research universe with intentionally limited capabilities.

Treat the historical universe as three nested sets:

```text
broad price-path research universe     (TRADES_ONLY + CANDLES_ONLY + any L2)
        +
narrower orderbook universe            (L2_PARTIAL / L2_COMPLETE only)
        +
narrower maker-execution universe      (L2_COMPLETE only)
```

Missing L2 does **not** exclude a market from W7/W8 price-path work.

## What was reconstructed

Observation-bearing committed envelopes only (not the 8,190 metadata-only
tickers). Compact trade JSONL — not full `MarketPath` dumps.

| Metric | Value |
|---|---:|
| Inventoried markets | 8,428 |
| Reconstructed paths | 238 |
| Completeness | TRADES_ONLY × 238 |
| L2 paths | 0 |
| Identity of reconstructed | UNMATCHED × 238 |
| Failed | 0 |
| Excluded from price-path | 8,190 (METADATA_ONLY; identity retained) |

## Funnel (real W8–W11 denominator)

Observability of frozen FIRST01 80/81 **prints**. This is **not** strategy replay.

| Stage | Reconstructed TRADES_ONLY markets | MATCHED games (catalog) |
|---|---:|---:|
| Markets / games | 238 | 2,377 |
| Market ID | 238 | n/a (MATCHED pairs exist as metadata) |
| Matched identity | 0 | 2,377 mapped pairs have no trades |
| Valid time coverage | 238 | 0 in this reconstruct |
| Trade observations | 238 | 0 |
| 80% print observable | 137 (57.6%) | **0 / 2,377** |
| FIRST01 81 confirm observable | 133 | 0 |
| Post-trigger path | 137 | 0 |
| Outcome/settlement | 0 | 0 |
| FIRST01 replay-sufficient | 0 | 0 |

Coupled YES: 119/119 both sides present; 107/119 events have an 80% print on
either side.

**The GameId-linked 80% research denominator is currently 0** because every
MATCHED pair is still `MARKET_METADATA_ONLY`. That is an ingest observation
gap, not a reason to discard the 238 TRADES_ONLY paths.

## Provenance / chronology

- Trade `created_time` is `exchange_timestamp` / source time.
- Envelope `retrieved_at` is stored and **never** used to order or `as_of`.
- First observed trade is `observed_start`, not `market_open`.
- Settlement is not injected into earlier path states (none present on these envelopes).

## CLI

```text
cargo run --release -p momento-research-w4 -- --reconstruct-price-paths \
  --handoff "Backtesting Suite/Foundation/Ingest/runs/<run>/w1_handoff.json" \
  --pairs "Backtesting Suite/Foundation/Ingest/runs/<run>/game_market_pairs.json" \
  --out "Backtesting Suite/Foundation/W4" \
  --lake "Backtesting Suite/Data-Real"
```

Artifacts: `price_path_readiness.json`, `price_path_market_rows.json`,
`price_path_coupled.json`, `price_path_compact.jsonl` (gitignored; large).

Do not start W5 from this document.
