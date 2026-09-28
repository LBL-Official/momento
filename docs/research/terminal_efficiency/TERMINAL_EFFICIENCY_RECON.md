# Terminal Efficiency — Phase 0 Reconnaissance

**Status:** COMPLETE (2026-09-09)  
**Scope:** Isolated research subsystem. Does not modify ROLLER five-screen workflow, FIRST80, live trading, or MLB W/A/S.  
**Phase 7:** NOT AUTHORIZED.

This document records what already exists in the repository so Terminal Efficiency reuses it instead of forking a second lake.

```text
BASKETBALL DATA
      ↓
POINT-IN-TIME GAME STATES
      ↓
XIB / MCD TRAINING          (works WITHOUT candles)
      ↓
FROZEN FUNDAMENTAL PROBABILITY
      ↓
ALIGN TO KALSHI 1-MINUTE CANDLES     (downstream grid)
      ↓
COMPARE F_t WITH K_t
      ↓
RESEARCH RESIDUAL
```

Kalshi prices are never XIB/MCD features.

---

## Isolation map

| Plane | Path | Role vs this project |
|-------|------|----------------------|
| Event-centric warehouse | `Backtesting Suite/Data/{NBA,NCAAB}/{season}/warehouse/` | **Read** raw/normalized; **write only** `derived/terminal_efficiency/` |
| Warehouse CLIs | `apps/nba-data`, `apps/ncaab-data`, `crates/research-data` | Reuse for Kalshi download/normalize |
| NBA PBP ingest | `apps/nba-data/scripts/nba_pbp_overnight_ingest.py` | Reuse; 2024–25 already COMPLETE |
| NBA live wall clock | `apps/nba-data/scripts/nba_pbp_live_timeactual_ingest.py` | Optional; 2024–25 has no `pbp_live` |
| NCAAB ESPN ingest | `apps/ncaab-data/scripts/ncaab_pbp_espn_ingest.py` | Pattern to wrap; hardcoded to 2025–26 |
| ROLLER PIT / possessions | `ROLLER/roller/` | **Do not modify.** Possession grammar v2.0.0 is the methodology reference |
| ROLLER Terminal UI | `frontend/roller-terminal/` | **Do not modify** |
| FIRST80 | `ROLLER/roller/research/first80.py` | **Do not modify** |
| MLB research-engine | `crates/research-engine/` | Out of scope |
| This subsystem | `apps/terminal-efficiency/` | New isolated package |

`ROLLER/data/.../derived/game_state_features.csv` is tagged future information. Do not use it as a feature source.

ROLLER `fundamental_win_probability_empirical_v1` is a prior-only lookup table. Do not overload it. XIB is a new object.

---

## Warehouse conventions (must follow)

- Layout: `raw/` immutable → `normalized/` parquet/JSON → `derived/` versioned → `manifests/`
- Candles: `candles_1m/`, `market_data_type=CANDLESTICK_TOP_OF_BOOK`, never `orderbook.parquet`
- Prices: integer E4. Never invent L2 (`orderbook_depth_available=false`)
- Game identity: Kalshi `event_ticker` / warehouse `game_id` (hash) / NBA Stats `gameId` / ESPN `espn_game_id`
- Crosswalk statuses: `MATCHED | UNMATCHED | AMBIGUOUS` — no silent guesses
- Observability: `OBSERVED | MODELED | DERIVED | INFERRED | UNAVAILABLE`
- Do not infer tip from Kalshi market open

Default data root: `Backtesting Suite/Data` (`MOMENTO_RESEARCH_DATA_DIR` if set).

---

## NBA inventory (inspected)

### 2024–2025 (TRAIN / VAL)

| Asset | Status | Evidence |
|-------|--------|----------|
| PlayByPlayV3 | **AVAILABLE** — 1,393 COMPLETE | `warehouse/raw/nba_stats/pbp_v3/`; manifest `complete` |
| BoxScoreSummaryV3 | **AVAILABLE** — 1,393 | `raw/nba_stats/boxscore_summary/` |
| LeagueGameLog (schedule + box stats) | **AVAILABLE** | `schedule/leaguegamelog_{pre_season,regular_season,playin,playoffs}.json` (regular season 2,460 team-rows) |
| `timeActual` / `pbp_live` | **MISSING** | `wall_clock_source=UNAVAILABLE` on every 2024–25 manifest row |
| Kalshi normalized warehouse | **MISSING** | no `normalized/`, no `dataset_manifest.json` |
| Kalshi raw events/markets | **PARTIAL / UNVERIFIED** | `raw/kalshi/nba/events.jsonl.gz` has 1,451 events including **2025–26 tickers** (`KXNBAGAME-26OCT20…`); not a clean 2024–25 catalog |
| Kalshi 1m candles | **PARTIAL** | 58 ticker directories — playoff/late-April 2025 only |
| Kalshi trades | **PARTIAL** | same 58 tickers |

PBP V3 actions include `period`, ISO clock (`PT12M00.00S`), `scoreHome`/`scoreAway`, `actionType`/`subType`, `teamTricode`, `description`. Period start/end descriptions embed local wall times (e.g. `Start of 1st Period (7:11 PM EST)`). There is **no** structured `timeActual`.

Alignment for 2024–25 NBA candles, if any, must be labeled **MODELED** (`PERIOD_BOUNDED_LINEAR_GAME_CLOCK`). Training does not require candles.

### 2025–2026 (FROZEN TEST — do not fit)

| Asset | Status |
|-------|--------|
| Kalshi games / candles / trades | **AVAILABLE** — 1,362 games, 2,724 markets, ~6.2M 1m candles |
| PBP V3 + `pbp_live` | **AVAILABLE** — 1,352 MATCHED, 10 UNMATCHED |
| Crosswalk | `normalized/nba/pbp/game_crosswalk.json` (`game_date+team_pair`) |

2025–26 is read-only. No fitting, selection, calibration, or hyperparameter use.

---

## NCAAB inventory (inspected)

### 2024–2025 (TRAIN / VAL)

| Asset | Status |
|-------|--------|
| Warehouse tree | **MISSING** — no `Data/NCAAB/2024-2025/` |
| ESPN scoreboard / PBP | **MISSING** — requires ingest |
| Kalshi | **MISSING** |

### 2025–2026 (FROZEN TEST — do not fit)

| Asset | Status |
|-------|--------|
| Kalshi | **AVAILABLE** — 5,280 games, 10,560 markets, ~13.4M candles |
| ESPN PBP | **PARTIAL** — 849 P5-vs-P5 MATCHED (~16% of Kalshi universe) |
| Non-P5 PBP | **MISSING** |

V1 universe (locked): **P5-vs-P5 for possession / in-game models**; **full D1 schedule + finals for pregame-only** where PBP is absent. Do not fabricate non-P5 possessions.

---

## Reusable code (read-only)

| Need | Reuse |
|------|--------|
| Kalshi download | `cargo run -p momento-nba-data -- download-all --season 2024-2025` (same for `momento-ncaab-data`) |
| NBA PBP | `nba_pbp_overnight_ingest.py` already supports `configure(warehouse_season, stats_season)` |
| Possession rules | `ROLLER/docs/POSSESSIONS.md` v2.0.0 — `CONFIRMED \| RECONSTRUCTED \| AMBIGUOUS \| UNRESOLVED` |
| Pregame shift-then-roll | `ROLLER/roller/features/engine.py` `priors_before` (`result_available_at < cutoff`) |
| Leakage tests | `ROLLER/roller/validation/leakage.py`; DRE `apps/nba-data/scripts/dre_v5/leakage_audit.py` |
| NBA clock alignment | `docs/research/nba/game-path-engine-v2/TIME_ALIGNMENT.md` |
| NCAAB alignment | `apps/ncaab-data/scripts/ncaab_pbp_align.py` (`HALF_BOUNDED_OBSERVED_WALLCLOCK`) |
| Candle schema | `crates/research-data/src/warehouse/types.rs` — authority is UTC `end_period_ts` (period end) |

This package **reimplements** possession construction and writes only under `derived/terminal_efficiency/`. It does not import ROLLER writers or write into `ROLLER/data/`.

---

## Explicitly unavailable (do not invent)

- Historical point-in-time injury / lineup availability
- KenPom / NCAA official advanced stats warehouse
- Historical L2 order book
- Per-play `timeActual` for NBA 2024–25
- Complete 2024–25 Kalshi 1m candle warehouse
- NCAAB non-P5 play-by-play

A missing source is a DATA GAP. Never synthesize Kalshi prices to make Dataset C symmetrical.

---

## Placement decided

```text
apps/terminal-efficiency/                 # Python package + CLIs + tests
docs/research/terminal_efficiency/        # this recon + inventory + contracts
Backtesting Suite/Data/{NBA,NCAAB}/{season}/warehouse/derived/terminal_efficiency/
```

---

## Next

Phase 1: `DATA_INVENTORY.md` with AVAILABLE / PARTIAL / MISSING / UNVERIFIED and DATA GAP blocks.
