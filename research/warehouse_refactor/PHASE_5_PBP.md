# Phase 5 — NBA play-by-play warehouse

Measured: **2026-09-13T06:05:37Z**.

Projection of published NBA Stats PBP through `source_game_id → internal_game_id`. No candle join. No invented PIT timestamps.

---

## 1. Objective

```text
NBA Game → PBPEvent
```

linked by the same `internal_game_id` as Phase 3 markets. Event sequence is source order. Identity linkage ≠ market/PBP temporal alignment.

---

## 2. Source inventory

| Source | Path | Measured |
| --- | --- | ---: |
| Canonical PBP | `ROLLER/data/nba/2025_2026/canonical/pbp/month=*.csv` | **780,137** rows; 9 months |
| Identity | `ROLLER/meta/game_identity.csv` | 1,362 NBA games; 1,352 with `source_game_id` |
| Raw NBA Stats | Suite `raw/nba_stats/pbp_live/{nba_game_id}.json` | upstream of canonical CSV; not re-ingested |

Canonical columns include `internal_game_id`, `source_game_id`, `event_number`, `event_timestamp`, `time_actual`, `period`, `clock`, scores, `event_type`, `possession`, player/team fields, `timestamp_status`.

---

## 3. Schema

Provisional parquet: `internal_game_id` (from identity `source_game_id`), `source_internal_game_id` (CSV stamp), `source_game_id`, `game_link_status`, `event_number`, clocks, scores, event/team/player fields, `possession` as supplied, `source`.

Sort: `internal_game_id`, numeric `event_number` (mergesort). Timestamp is **not** the order key.

---

## 4. Linkage methodology

```text
PBP source_game_id
        ↓
identity.source_game_id
        ↓
internal_game_id
```

One source id → two games: `AMBIGUOUS` (0 on disk).  
CSV stamp ≠ identity: `CONFLICT`, gid blank (0).  
Missing/unknown source id: `UNLINKED` (0 rows; the 10 games simply have **no PBP files**).

No game-clock → wall-clock invention. No nearest-candle join. Possession copied only when the source cell is non-empty.

---

## 5. Measured row counts

| Metric | Value |
| --- | ---: |
| PBP rows | **780,137** |
| LINKED rows | **780,137** |
| UNLINKED rows | **0** |
| CONFLICT / AMBIGUOUS | **0** |
| Blank `event_timestamp` | **0** |
| Duplicate `(game, event_number)` | **0** |
| Games with PBP | **1,352** |
| Identity games without `source_game_id` / without PBP | **10** |
| Date range | 2025-10-10T12:13:59.3Z … 2026-06-14T03:29:26.5Z |

| Month | Rows |
| --- | ---: |
| 2025-10 | 73,907 |
| 2025-11 | 128,731 |
| 2025-12 | 114,538 |
| 2026-01 | 132,094 |
| 2026-02 | 94,745 |
| 2026-03 | 135,731 |
| 2026-04 | 77,891 |
| 2026-05 | 19,476 |
| 2026-06 | 3,024 |

Output: `ROLLER/data/nba/2025_2026/derived/warehouse_v0/pbp/month=YYYY-MM.parquet` (9 files, 28,782,623 bytes) + `manifest.json`.

`PBPEvent.event_timestamp` stays required: every NBA row on disk has a timestamp. No entity relaxation.

---

## 6. Coverage vs markets

| Set | Count |
| --- | ---: |
| Games with observations **and** PBP | **1,352** |
| Games with LINKED markets and no PBP | **10** (no `source_game_id`) |
| Games with PBP and no observations | **0** |

The 10 games without PBP / without observations:

`NBA_20260108_MIA_CHI`, `NBA_20260124_GSW_MIN`, `NBA_20260125_DAL_MIL`, `NBA_20260125_DEN_MEM`, `NBA_20260414_MIA_CHA`, `NBA_20260414_POR_PHX`, `NBA_20260415_GSW_LAC`, `NBA_20260415_ORL_PHI`, `NBA_20260417_CHA_ORL`, `NBA_20260417_GSW_PHX`.

Missing PBP is **not** recorded as zero events.

---

## 7–9. Duplicates / unresolved / quality

No duplicate event numbers within a game. No invented clocks. `pit_join_performed=false`. `timestamps_invented=false`. `possession_inferred=false`.

---

## 10. Tests

`tests/test_warehouse_pbp.py` (synthetic + live October sequence/link).

---

## 11. Limitations

- Provisional layout. Not Confirm & Run.
- No PIT alignment to candles (later phases).
- Possession is source text; many cells are blank and stay blank.
- The 10 games without NBA stats ids cannot receive PBP without new source evidence.

---

## 12. Status

**PHASE 5: COMPLETE**
