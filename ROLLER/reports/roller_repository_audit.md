# ROLLER repository audit

**Date:** 2026-09-06  
**Purpose:** Phase 1 inventory before building ROLLER V1.  
**Invariant:** the existing warehouse remains read-only evidence. ROLLER will not replace it.

## Central distinction

The warehouse knows what data exists. ROLLER will know what could have been known at a particular time.

```
EXISTING MOMENTO WAREHOUSE  (evidence, read-only)
        → ROLLER ingest adapters
        → raw pointer / hash manifest
        → canonical CSV observations
        → derived D2D / team features
        → point-in-time choke point I(t)
        → future research (FIRST75 / FIRST80 / alpha)
```

ROLLER ≠ ALPHA ≠ STRATEGY ≠ EXECUTION.

## What exists

No `ROLLER/` tree existed before this work.

### Kalshi event-centric warehouse (reuse, do not replace)

| Component | Path |
|-----------|------|
| Core | `crates/research-data/src/warehouse/` |
| CLIs | `apps/nba-data`, `apps/wnba-data`, `apps/ncaab-data` |
| Lake | `Backtesting Suite/Data/{NBA,WNBA,NCAAB}/{season}/warehouse/` |
| NBA spec | `docs/research/NBA_KXNBAGAME_MARKET_DATA.md` |
| NCAAB spec | `docs/research/NCAAB_KXNCAAMBGAME_MARKET_DATA.md` |

Layout: `raw/` → `normalized/` → `derived/` + `manifests/`.

There is no standalone Python Kalshi candle downloader. Ingest is Rust (`nba-data download-all`, etc.). Kalshi HTTP is often blocked on the local network.

### NBA 2025-2026 (reference season)

| Asset | Count / note |
|-------|----------------|
| Kalshi games | 1,362 (`nba_games.json` / parquet) |
| Markets | 2,724 |
| 1-minute candles | ~6.2M rows, 2,724 parquet files, ~0.18 GB |
| Trades | ~40.5M (not a ROLLER V1 required dataset) |
| PBP crosswalk | 1,352 MATCHED, 10 UNMATCHED |
| PlayByPlayV3 | 1,352 JSON |
| pbp_live (`timeActual`) | 1,352 JSON |
| Box scores | 1,347 |

Game catalog has identity, tickers, schedule. **No scores.** Scores live on box / PBP terminal actions.

`pbp_live` action fields include `timeActual` (e.g. `2026-01-07T00:12:55.9Z`), `period`, `clock`, `scoreHome`, `scoreAway`, `actionType`, `description`, `possession`.

### NBA 2024-2025

PBP-only (~1,393 games). Kalshi not normalized. **Out of ROLLER V1 operational scope.**

### WNBA 2025-2026 warehouse

| Asset | Count / note |
|-------|----------------|
| Games | 612 (2025 and 2026 campaigns in one folder) |
| Markets / candles | 1,224 files, ~1.4M candles |
| ESPN plays | 610 MATCHED at `normalized/wnba/pbp/plays/` |
| Crosswalk | 612 rows, 610 MATCHED |

Team codes are mixed (`LA`/`LAS`, `LV`/`LVA`). Canonicalization already exists in `wnba_pbp_espn_ingest.py`.

### NCAAB 2025-2026 warehouse

| Asset | Count / note |
|-------|----------------|
| Kalshi games | 5,280 |
| Markets / candles | 10,560 files, ~13.4M candles |
| P5 PBP | 849 MATCHED plays JSON (16% of Kalshi games) |
| P5 codes | 70-code frozenset in `ncaab_pbp_espn_ingest.py` |

No conference table. P5 vs P5 is a hardcoded membership test. ESPN→Kalshi aliases exist (`OU→OKLA`, `SC→SCAR`, `TA&M→TXAM`).

### Identity systems (do not invent a fourth unmapped scheme)

| ID | Meaning |
|----|---------|
| Production `GameId` | u128 SHA256(`game\0` + event_ticker) in `crates/kalshi/src/identity.rs` |
| Warehouse `game_id` | Same hash as hex |
| `event_ticker` | e.g. `KXNBAGAME-26JUN13NYKSAS` |
| `nba_game_id` / `espn_game_id` | Provider IDs via `game_crosswalk.json` |

Crosswalk statuses: `MATCHED` / `UNMATCHED` / `AMBIGUOUS`. No silent guesses.

ROLLER `internal_game_id` (`NBA_20251219_LAL_BOS`) is a **readable alias** that must persist the source IDs above.

### PBP ingest to wrap, not rewrite

- `apps/nba-data/scripts/nba_pbp_overnight_ingest.py` — never invent `timeActual` from tip + clock
- `apps/nba-data/scripts/nba_pbp_live_timeactual_ingest.py`
- `apps/wnba-data/scripts/wnba_pbp_espn_ingest.py`
- `apps/ncaab-data/scripts/ncaab_pbp_espn_ingest.py`

Alignment rule already used in research scripts: latest play with wall time before the market timestamp. Do not import FIRST80 / DRE packages.

### Price units

Warehouse candles use integer **E4** (ten-thousandths of a dollar). `look_ahead = false` in `derive.rs`. Candles are `CANDLESTICK_TOP_OF_BOOK`, not fills, not L2.

## What is missing (ROLLER must add)

- `available_at`, `ingested_at`, availability quality labels
- Scores on the game row
- Team `*_pre` features and D2D information states
- Central as_of API with a public choke point
- CSV canonical layer
- Leakage tests that fail the pipeline
- Metadata-driven seasons and NCAAB conferences
- Daily Python orchestrator with source-revision hashes
- Row-level lineage

## What must not be ingested or rewritten

- FIRST75 / FIRST80 / DRE / Lebronner outputs
- Live trading crates and production `GameId` binding
- MLB research-engine W0–W8 (do not start W9)
- Warehouse raw files (read-only evidence)

## Normalization plan

| Existing asset | ROLLER action |
|----------------|---------------|
| `*_games.json` | Pointer + hash; canonicalize to `games.csv` with scores and timestamps |
| `game_crosswalk.json` | Drive mapping_status; never upgrade UNMATCHED silently |
| NBA `pbp_live` / `pbp_v3` | Pointer + hash; canonical monthly `pbp.csv` preferring `timeActual` |
| WNBA/NCAAB `pbp/plays/*.json` | Reuse normalized plays; do not re-parse raw ESPN |
| `candles_1m/*.parquet` | Read-only; export monthly canonical CSV with E4 integers |
| `P5_CODES` + ESPN aliases | Seed `conferences.json` / `teams.csv` |
| Warehouse derived FIRST80/DRE | Ignore |

## Recommended preserve vs replace

**Preserve:** warehouse ingest, parquet candles, crosswalks, PBP JSON, integer E4 prices, MATCHED/UNMATCHED discipline.

**Add:** ROLLER identity, availability timestamps, D2D, as_of choke point, validation, update log.

**Replace:** nothing in the warehouse or live trading path.
