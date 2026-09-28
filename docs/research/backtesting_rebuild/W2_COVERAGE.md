# W2 Coverage

**2025 PBP does not exist locally. Do not claim it.**

## Historical data actually available

| Asset | Status |
|-------|--------|
| Official MLB StatsAPI PBP | **174 Final games** 2026-06-18..30 under `Foundation/W2/raw/statsapi/` (not Data-Real) |
| Kalshi MLB Data-Real | 13 COMPLETE PT days 2026-06-18..30. Market path only. |
| Kalshi ↔ MLB identity | 168 unique MAPPED; 4 UNMATCHED; 2 AMBIGUOUS (CHC–NYM DH) |
| Kalshi 2025 probes | Empty. Not 2025 history. |
| 2025 MLB PBP | **MISSING_HISTORICAL_SOURCE** |
| Pitch-level Statcast | Not collected (Savant is secondary, not substituted) |
| Event Theta values | UNAVAILABLE (estimator W9). Inputs present on reconstructed games. |

Machine-readable: `historical_reconstruction.json`, `statsapi_collect_manifest.json`, `w2_coverage.csv`.


## Historical data actually available

| Asset | Status |
|-------|--------|
| Kalshi MLB Data-Real | 13 COMPLETE PT days 2026-06-18..30 (W1 lake). Market path only. |
| Kalshi 2025 probes | Empty (`markets_discovered=0`). Not 2025 history. |
| MLB PBP / StatsAPI / Savant / Retrosheet files | **None** |
| metadata.parquet directory | **Absent** even though some manifests list a checksum |
| Pitch-level history | **MISSING_HISTORICAL_SOURCE** |

## Report vocabulary

`AVAILABLE | MISSING | PARTIAL | INVALID | UNVERIFIED | MISSING_HISTORICAL_SOURCE`

Machine-readable: `Backtesting Suite/Foundation/W2/coverage.json` and `w2_coverage.csv`.

Kalshi event tickers, when readable from orderbook parquet, appear as **UNMAPPED** aliases (`home_team=UNAVAILABLE`, `away_team=UNAVAILABLE`). That is not official MLB identity.

## Synthetic vs historical

`src/synthetic.rs` and parser fixtures are **SYNTHETIC_TEST_FIXTURE**. They must not be published as 2025–2026 MLB reconstruction.
