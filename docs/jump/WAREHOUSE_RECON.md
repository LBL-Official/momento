# Jump warehouse recon

**Date:** 2026-09-21
**LIVE EXECUTION = FALSE**

Jump does not own warehouse data. This document records what is on disk
before the workbench was built. Confirm & Run still reads canonical CSV.
The Jump workbench inspects the Phase 8 parquet desk only.

```text
ROLLER/data/{sport}/{season}/canonical/     Confirm & Run CSV
ROLLER/data/{sport}/{season}/derived/warehouse/   Phase 8 parquet desk
```

Those two layers are not interchangeable.

## 1. Physical storage

Season trees live under `ROLLER/data/`. No DuckDB, SQLite, or Postgres
warehouse files exist in-repo for research data.

NBA Phase 8 root (canonical for Jump workbench):

`ROLLER/data/nba/2025_2026/derived/warehouse/`

```text
games/games.parquet
markets/markets.parquet
game_market_links/links.parquet
settlements/settlements.parquet
observations/basis=tradable_yes_bid/month=YYYY-MM.parquet
pbp/month=YYYY-MM.parquet
manifest.json
README.md
```

There is no `orderbook/` parquet under Phase 8.
`derived/warehouse_v0/orderbook/capability.json` is `SOURCE_UNAVAILABLE`.

Jump's previous `nba warehouse` pointer was `ROLLER/data/nba` (the whole
sport tree). That is too coarse. The workbench targets the Phase 8 desk.

## 2. Logical storage

Logical names:

- `nba.games`
- `nba.markets`
- `nba.game_market_links`
- `nba.observations` (TRADABLE_YES_BID 1-minute candles)
- `nba.pbp` (sequence-only)
- `nba.settlements`

Physical files remain parquet. Jump aliases do not copy them.

## 3. Canonical tables (NBA manifest, 2026-09-13)

| Logical table | Rows | Notes |
|---|---:|---|
| games | 1,362 | identity |
| markets | 2,724 | Kalshi YES/NO |
| game_market_links | 2,724 | GameMarketLink |
| settlements | 2,724 | |
| observations | 6,165,183 | month-partitioned |
| pbp | 780,137 | month-partitioned |
| orderbook | 0 | SOURCE_UNAVAILABLE |
| ticks | 0 | SOURCE_UNAVAILABLE |

PIT: `available_at` on observations. `pbp_pit_aligned_to_candles` is false
(`OPERATION_REQUIRED`).

## 4. Relationship keys (declared)

From `ROLLER/roller/warehouse/layout.py` and GameMarketLink:

- `games.internal_game_id` 1:N `markets.internal_game_id`
- `games.internal_game_id` 1:N `observations.internal_game_id`
- `games.internal_game_id` 1:N `pbp.internal_game_id`
- `markets.market_id` / `ticker` 1:N `observations.market_id` / `ticker`
- `markets.market_id` 1:1 `settlements.market_id`
- `game_market_links` is the canonical mapping table

Name-similar columns elsewhere are candidates, not trusted FKs.

## 5. Ownership

- ROLLER owns measurements (parquet + CSV).
- SuperASI owns analysis packages.
- Jump owns catalog metadata, saved queries, logical views, display aliases.
- Jump must not write parquet or CSV warehouse files.

## 6. Mutable vs immutable

Canonical parquet/CSV: immutable from Jump (read-only).
Jump JSON under `research/jump/workbench/`: Jump-owned, writable.
Confirm & Run execute path: not this workbench.

## 7. Formats

Phase 8: parquet (zstd, row_group 262144), `manifest.json`.
Canonical: CSV month partitions.
rq_index: parquet facts for Confirm & Run, not the desk.

## 8. Query engine

Repo had no DuckDB warehouse. Jump workbench uses DuckDB as an in-memory
read layer over parquet (`read_parquet`). It does not persist a `.duckdb`
file and does not replace parquet.

## 9. Size (NBA)

Observations 6,165,183 rows. Workbench must paginate (default 100, max 500).
Never load the full observations table into the browser or into pandas for
browse.

## 10. Known missing metadata

- Historical L2 / ticks: `SOURCE_UNAVAILABLE` / `DATA_REQUIRED`
- PBP↔candle PIT: `OPERATION_REQUIRED`
- WNBA: canonical CSV + rq_index; no Phase 8 `derived/warehouse`
- NHL: absent
- Tennis Phase 8 lives under `ROLLER/data/atp/` and `ROLLER/data/wta/`, not
  `ROLLER/data/tennis/`
- Column prose descriptions are sparse; unknown → `Unavailable`

## Other sports (Phase 8 contract)

Desk sports with `derived/warehouse/manifest.json`: NBA, NCAAB, MLB, ATP, WTA.
WNBA workbench registration is `WAREHOUSE_UNAVAILABLE` until a Phase 8 tree
exists. Do not invent tables.
