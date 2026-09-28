# Terminal Efficiency — Phase 1 Data Inventory

**Status:** COMPLETE (2026-09-09)  
**Seasons:** TRAIN/VAL = 2024–25; TEST = 2025–26 (frozen, no fit)  
**NCAAB V1 universe:** P5-vs-P5 in-game; full D1 pregame-only when PBP is absent.

Statuses: `AVAILABLE` | `PARTIAL` | `MISSING` | `UNVERIFIED`.

---

## NBA

| Domain | 2024–25 | 2025–26 | Notes |
|--------|---------|---------|-------|
| Schedules | AVAILABLE | AVAILABLE | 2024–25: NBA Stats LeagueGameLog + boxscore `gameTimeUTC`. 2025–26: Kalshi games parquet + Stats schedule |
| Final results | AVAILABLE | AVAILABLE | Box / LeagueGameLog PTS + WL. Ties: none expected; flag if scores equal |
| Play-by-play | AVAILABLE (1,393 V3) | AVAILABLE (1,352 MATCHED) | V3 has period + game clock + scores. No silent possession invention |
| Possession reconstruction | PARTIAL | PARTIAL | Grammar v2.0.0; status vocabulary required. NCAAB-like ambiguity does not apply to NBA team fields |
| `timeActual` wall clock | MISSING | AVAILABLE | 2024–25 alignment is MODELED if candles exist |
| Advanced team stats (KenPom-like) | MISSING | MISSING | Construct ratings only from our prior box/PBP aggregates |
| Player availability / injuries | UNAVAILABLE | UNAVAILABLE | See DATA GAP |
| Kalshi 1m candles | PARTIAL (58 playoff tickers) | AVAILABLE (~6.2M) | Not a training requirement |
| Market/game matching | PARTIAL | AVAILABLE (1,352 MATCHED / 10 UNMATCHED) | 2024–25 events file is UNVERIFIED (mixed 2025–26 tickers) |

---

## NCAAB

| Domain | 2024–25 | 2025–26 | Notes |
|--------|---------|---------|-------|
| Schedules | MISSING (ingest required) | AVAILABLE (Kalshi 5,280) + ESPN scoreboard | Phase 2 ESPN D1 scoreboard |
| Final results | MISSING (ingest required) | PARTIAL | Kalshi settlement + ESPN scores where ingested |
| Play-by-play | MISSING (ingest required) | PARTIAL (849 P5-vs-P5) | V1: P5-vs-P5 only for in-game |
| Possession reconstruction | MISSING until PBP | PARTIAL | ESPN `type_text`; team often missing → AMBIGUOUS/UNRESOLVED |
| Advanced stats / KenPom | MISSING | MISSING | See DATA GAP |
| Player availability | UNAVAILABLE | UNAVAILABLE | See DATA GAP |
| Kalshi 1m candles | MISSING | AVAILABLE (~13.4M) | Training proceeds without candles |
| Market/game matching | MISSING | PARTIAL (P5 crosswalk) | `DATE_PM2_TEAM_PAIR` |

---

## DATA GAP blocks

### GAP-001 — Historical point-in-time player availability

```text
DATA GAP
Source: none verified in-repo
Required field: injury / inactive / lineup as-of timestamp
Why unavailable: no historical feed with proven availability_at < prediction_timestamp
Potential future source: official injury reports with publication timestamps (UNVERIFIED)
Impact on model: player features marked UNAVAILABLE in V1; no hindsight backfill
```

### GAP-002 — KenPom / NCAA official advanced stats

```text
DATA GAP
Source: not ingested
Required field: pregame KenPom / NCAA efficiency
Why unavailable: no warehouse table; frontend catalog marks KenPom COMING_SOON
Potential future source: licensed KenPom snapshot with as-of dates
Impact on model: use only prior-game box/PBP aggregates we compute ourselves
```

### GAP-003 — NBA 2024–25 per-play wall clock

```text
DATA GAP
Source: NBA Stats PlayByPlayV3
Required field: timeActual
Why unavailable: V3 has no timeActual; pbp_live not downloaded for 2024–25
Potential future source: nba_pbp_live_timeactual_ingest.py if CDN still serves those game IDs
Impact on model: possession training uses game-clock order; candle alignment MODELED
```

### GAP-004 — Complete 2024–25 Kalshi candle warehouse

```text
DATA GAP
Source: Kalshi KXNBAGAME / KXNCAAMBGAME
Required field: 1-minute CANDLESTICK_TOP_OF_BOOK for full 2024–25
Why unavailable: NBA has 58 playoff ticker dumps only; events.jsonl.gz mixes 2025–26 tickers; NCAAB 2024–25 tree absent
Potential future source: momento-nba-data / momento-ncaab-data --season 2024-2025
Impact on model: TRAIN WITHOUT CANDLES. Do not synthesize prices. Dataset C may be empty or playoff-only
```

### GAP-005 — NCAAB non-P5 play-by-play

```text
DATA GAP
Source: ESPN summary PBP
Required field: event-level PBP for non-P5 D1
Why unavailable: existing ingest filters P5_CODES; ESPN coverage is incomplete
Potential future source: broader ESPN ingest (still will be PARTIAL)
Impact on model: non-P5 games may appear in Dataset A (pregame) only; no fabricated possessions
```

### GAP-006 — Historical L2

```text
DATA GAP
Source: Kalshi order book
Required field: L2 depth
Why unavailable: warehouse contract — historical L2 UNAVAILABLE
Potential future source: none for backfill
Impact on model: not required for XIB/MCD V1
```

### GAP-007 — 2024–25 NCAAB warehouse

```text
DATA GAP
Source: ESPN + Kalshi
Required field: D1 schedule/finals + P5 PBP + optional candles
Why unavailable: directory does not exist on disk at recon time
Potential future source: Phase 2 ingest wrappers
Impact on model: NCAAB XIB/MCD cannot train until ESPN (at least) lands
```

---

## Training implication (binding)

```text
MODEL TRAINING WITHOUT CANDLES = REQUIRED
DATASET A (pregame) + DATASET B (possession) = sufficient to train
DATASET C (candle-aligned) = apply / coverage grid only
NEVER fill missing candles with synthetic prices
```

---

## Phase 2 ingest targets

1. Wrap `momento-nba-data` / `momento-ncaab-data` for 2024–25 Kalshi (record gap if blocked).
2. Optional NBA 2024–25 `timeActual` via existing live ingest (do not invent if CDN fails).
3. NCAAB 2024–25 ESPN D1 scoreboards + P5-vs-P5 PBP into `Data/NCAAB/2024-2025/warehouse/`.
4. Leave 2025–26 warehouses read-only.
