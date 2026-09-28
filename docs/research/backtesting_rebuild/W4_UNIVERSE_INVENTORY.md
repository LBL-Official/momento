# W4 historical universe inventory

**Kind:** DISCOVERY_PREFIX_SCAN + bounded TRADES_ONLY reconstruct  
**Source:** ingest `ingest-20260826T095038Z-2bc3d10b5833`  
**Machine artifacts:** `universe_inventory.json`, `price_path_readiness.json`  
**W4 GATE:** **COMPLETE** (price-path foundation). W5 is not started.

TRADES_ONLY is **not** a failed dataset.

## Counts

| Metric | Value |
|---|---:|
| Unique Kalshi markets (tickers) | 8,428 |
| Unique event_tickers | 4,214 |
| Coupled both-YES events (catalog) | 4,214 |
| Unique MATCHED games (`game_pk`) | 2,377 |
| Date range | 2025-04-16 .. 2026-08-25 |
| Sport / series | MLB / `KXMLBGAME` |
| 2025 / 2026 tickers | 4,428 / 4,000 |
| 2024 Kalshi | UNAVAILABLE |

## Identity (retained, not discarded)

| Class | Count |
|---|---:|
| MATCHED | 4,754 |
| UNMATCHED Kalshi | 3,674 |
| UNMATCHED PBP (no ticker) | 560 |
| AMBIGUOUS | 0 |

## Capability / completeness

| Class | Inventoried | Reconstructed paths |
|---|---:|---:|
| TRADES_ONLY | 238 | **238** (UNMATCHED) |
| MARKET_METADATA_ONLY | 8,190 | 0 (excluded from paths; identity kept) |
| CANDLES_ONLY | 0 | 0 |
| L2_COMPLETE / L2_PARTIAL | 0 | 0 |

`HISTORICAL_L2_UNAVAILABLE` on 8,428 / 8,428.

## Price-path reconstruct (not a vanity 8k dump)

| Metric | Value |
|---|---:|
| Reconstructable TRADES_ONLY paths | 238 |
| Trade prints (sum) | 2,249,244 |
| Observations/market (min / median / max) | 407 / 7,713 / 44,444 |
| Time span (sec, min / median / max) | 33,022 / 64,400 / 85,810 |
| Duplicate / conflicting / malformed trades | 0 / 0 / 0 |
| Coupled both-YES in reconstruct | 119 / 119 |
| 80% print on either coupled side | 107 / 119 |
| Settlement on envelopes | 0 |
| L2 paths | 0 |

See [W4/RECONSTRUCTION.md](W4/RECONSTRUCTION.md) for the W8–W11 funnel.
The GameId-linked 80% denominator is **0 / 2,377** until MATCHED pairs have trades.

Do not start W5. Do not invent L2. Do not discard TRADES_ONLY.
