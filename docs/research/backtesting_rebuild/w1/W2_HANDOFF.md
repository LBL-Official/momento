# W1 → W2 handoff (W1-owned pointers only)

W1 does **not** define MLB GameState, PBP, or StateTransition.

W2 may **read**:

| Artifact | Path |
|----------|------|
| Canonical catalog | `Backtesting Suite/Foundation/W1/lake_catalog.json` |
| Raw file pointers + SHA-256 | `raw_artifact_refs.json` |
| Kalshi identity stubs (`mlb_game_pk` = null) | catalog `market_evidence` |
| Starting-price class | `starting_price_evidence.json` (all `STARTING_PRICE_UNVERIFIED` in this lake) |
| Coverage | `coverage_matrix.csv` |
| Integrity | `integrity_report.json` |

W2 must **not**:

- overwrite Data-Real gzip/parquet
- treat `PARTITION_COMPLETE_V1` as PBP-complete
- treat first settlement-day candle as `MARKET_OPEN_PRICE`
- invent L2 from candles

`RawArtifactRef.sport` is the **lake folder name** (`MLB` / `WNBA`), not a canonical multi-sport domain enum. See CROSS_WATERFALL_ISSUES.md.
