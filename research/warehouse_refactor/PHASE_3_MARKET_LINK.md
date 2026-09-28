# Phase 3 — NBA market identity + GameMarketLink

Measured: **2026-09-13T06:05:01Z**.

NBA only. Phase 2 identities were not renamed. Confirm & Run was not modified.

---

## 1. Objective

Persist an auditable

```text
NBA Game → GameMarketLink → Kalshi Market
```

relationship so later phases resolve `ticker → internal_game_id` from a warehouse fact, not from ticker-string guessing.

---

## 2. Source inventory

| Source | Path | Measured |
| --- | --- | ---: |
| Identity catalog | `ROLLER/meta/game_identity.csv` | 1,362 NBA games; 2,724 explicit home/away tickers |
| Canonical markets | `ROLLER/data/nba/2025_2026/canonical/kalshi_markets.csv` | 2,704 tickers / 1,352 games (MAPPED only) |
| Suite markets | `Backtesting Suite/Data/NBA/2025-2026/warehouse/normalized/nba/markets/markets.parquet` | 2,724 tickers |
| Crosswalk before this phase | `game_market_crosswalk.parquet` | **ABSENT** |

Identity ticker columns (`kalshi_market_yes_home` / `_away`) come from Suite `nba_games.json` explicit `home_market_ticker` / `away_market_ticker`. They are **not** parsed from `KXNBAGAME-…` bodies.

`mapping_status` remains a PBP/source-id flag. It is **not** `link_status`.

---

## 3. Schema

`GameMarketLink` (extended, same enum): `status`, `internal_game_id`, `ticker`, `event_ticker`, `reason`, `link_method`, `source_evidence`, `identity_rule_version`.

`Market` (extended): `ticker` = stable `market_id`; optional `source_market_id`, `source`, `market_type`, `title`, `sport`, `league`. No generic `price`.

Persisted columns: `ROLLER/roller/warehouse/market_link.py` `CROSSWALK_COLUMNS` / `MARKET_COLUMNS`.

---

## 4. Linkage methodology

```text
identity.kalshi_market_yes_home/away
        ↓
unique ticker → one internal_game_id  → LINKED
ticker → two games                    → AMBIGUOUS (none on disk)
ticker in Suite/canonical only        → UNLINKED (none on disk)
empty ticker                          → INVALID
```

`link_method = identity_explicit_ticker` for every LINKED row.

UNMAPPED games (no NBA stats `source_game_id`) are still LINKED when identity has unique explicit tickers. Those 20 tickers stay out of `kalshi_markets.csv` as before.

Rebuild does **not** call `infer_market_tickers`. One game → many markets is valid.

---

## 5. Measured row counts

| Metric | Value |
| --- | ---: |
| Crosswalk rows | **2,724** |
| LINKED | **2,724** |
| UNLINKED | **0** |
| AMBIGUOUS | **0** |
| INVALID | **0** |
| Duplicate tickers | **0** |
| One ticker → many games | **0** |
| Games with ≥1 LINKED market | **1,362** |
| Identity tickers | 2,724 |
| Suite tickers | 2,724 |
| Canonical `kalshi_markets` tickers | 2,704 |
| UNMAPPED-but-LINKED tickers | **20** (10 games × 2) |

Artifact: `ROLLER/meta/game_market_crosswalk.parquet` (82,756 bytes) + `.manifest.json`.  
Provisional markets: `ROLLER/data/nba/2025_2026/derived/warehouse_v0/markets.parquet` (202,700 bytes).

---

## 6. Coverage

Every NBA identity game has two LINKED Kalshi YES markets (home and away).  
1,352 of those games also appear in `kalshi_markets.csv`.  
10 games have LINKED tickers and no settlement catalog row.

---

## 7–9. Duplicates / unresolved / quality

No duplicate links. No conflicting ticker→game maps. No unresolved Suite tickers. No ticker was used as `internal_game_id`.

---

## 10. Tests

`tests/test_warehouse_market_link.py` (synthetic + live invariants). See Phase 3–5 test run in the gate report.

---

## 11. Limitations

- NBA only. NCAAB/MLB not written to this crosswalk.
- Layout is provisional (`warehouse_v0`). Phase 8 will relocate.
- Settlement fields on Suite/canonical markets are **not** a Phase 6 Settlement entity.
- Confirm & Run still reads stamped CSV, not this parquet.

---

## 12. Status

**PHASE 3: COMPLETE**
