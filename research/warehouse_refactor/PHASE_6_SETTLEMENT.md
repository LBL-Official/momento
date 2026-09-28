# Phase 6 — NBA Kalshi settlement

Measured: **2026-09-13T06:23:55Z**.

NBA only. Phase 2 identities were not renamed. Confirm & Run was not modified. Settlement is not inferred from score, PBP, candles, or last price.

---

## 1. Objective

Persist an authoritative

```text
market_id → GameMarketLink → internal_game_id
market_id → Settlement (YES | NO | MISSING | INVALID)
```

record for every NBA Kalshi market. Settlement answers what the source said the market settled to. It does not answer what the NBA score implied.

---

## 2. Source inventory

| Source | Path | Role | Measured |
| --- | --- | --- | ---: |
| Suite markets (Kalshi REST) | `Backtesting Suite/Data/NBA/2025-2026/warehouse/normalized/nba/markets/markets.parquet` | **Authoritative** | 2,724 rows; `source=kalshi_rest`; yes 1,359 / no 1,359 / scalar 6 |
| Phase 3 crosswalk | `ROLLER/meta/game_market_crosswalk.parquet` | `ticker → internal_game_id` only | 2,724 LINKED |
| Canonical `kalshi_markets.csv` | `ROLLER/data/nba/2025_2026/canonical/kalshi_markets.csv` | **Not the universe** | 2,704 MAPPED yes/no; drops 20 UNMAPPED-game tickers |
| `rq_index` `settlement.parquet` | derived index | **Not a source** | 2,704 copied yes/no |
| FIRST80 `expiration_result_yes` / `official_settlement.py` | overlay | **Not used** | unused (warehouse result present) |
| `games.csv` `home_win` | box score | **Forbidden** | 750 / 602 / 10 blank |
| PBP / 1-minute candles / last trade / price 0 or 100 | observations | **Forbidden** | not read |

Suite SHA-256: `ad8137c29d51dde84fecc1217186d899a46d8ac0b78da97c694b57aea518a5fe`.

`canonicalize_markets` copies Suite `result` and does not infer from score. Phase 6 reads Suite directly so the 6 `scalar` markets are classified `INVALID` instead of being dropped.

---

## 3. Schema

Persisted columns (`ROLLER/roller/warehouse/settlement.py` `SETTLEMENT_COLUMNS`):

```text
market_id, ticker, internal_game_id, game_link_status
source, source_market_id, source_result, source_identifier
settlement_status, settlement_value_e4
source_settled_at, result_available_at, settlement_time
close_time, expiration_time
provenance, sport, season
```

`settlement_status` is the canonical enum (`YES` / `NO` / `MISSING` / `INVALID`).  
`source_result` preserves Kalshi-native `yes` / `no` / `scalar`.  
`source_settled_at` = Suite `settlement_time`.  
`Market` still has no `result` field.

---

## 4. Provenance / linkage

```text
Suite markets.parquet (kalshi_rest)
        ↓
kalshi_result_to_settlement(result)
        ↓
YES | NO | MISSING | INVALID
        ↓
ticker → GameMarketLink → internal_game_id
```

Duplicate Suite rows with the same classification: keep one, count the extra.  
Duplicate Suite rows with different classifications: **HARD STOP** (none on disk).  
Ticker in Suite but not in the crosswalk: settlement kept, `game_link_status=UNLINKED`, gid blank (none on disk).  
Ticker in the crosswalk but not in Suite: `MISSING` (none on disk).

Provenance string: `suite:markets.parquet:{hash16}:kalshi_rest`.

---

## 5. Measured coverage

| Metric | Value |
| --- | ---: |
| NBA markets (Suite ∩ crosswalk universe) | **2,724** |
| LINKED markets | **2,724** |
| UNLINKED / AMBIGUOUS | **0** |
| YES | **1,359** |
| NO | **1,359** |
| MISSING | **0** |
| INVALID (`scalar`) | **6** |
| Duplicate source rows | **0** |
| Conflicting settlements | **0** |
| Settlement date range | 2025-10-10T19:13:56.8125Z … 2026-06-14T03:32:25.229203Z |
| Games with settlement | **1,362** |
| Games without settlement | **0** |
| Games with market + observation + settlement | **1,352** |
| Games with market + observation and no settlement | **0** |
| Games with settlement and no Phase 4 candles | **10** |
| Linked markets without candles | **20** |

MISSING is not reported as NO.

INVALID tickers (source `scalar`, values preserved):

| ticker | internal_game_id | settlement_value_e4 |
| --- | --- | ---: |
| `KXNBAGAME-26JAN08MIACHI-CHI` | `NBA_20260108_MIA_CHI` | 3100 |
| `KXNBAGAME-26JAN08MIACHI-MIA` | `NBA_20260108_MIA_CHI` | 6900 |
| `KXNBAGAME-26JAN25DALMIL-DAL` | `NBA_20260125_DAL_MIL` | 4400 |
| `KXNBAGAME-26JAN25DALMIL-MIL` | `NBA_20260125_DAL_MIL` | 5600 |
| `KXNBAGAME-26JAN25DENMEM-DEN` | `NBA_20260125_DEN_MEM` | 3800 |
| `KXNBAGAME-26JAN25DENMEM-MEM` | `NBA_20260125_DEN_MEM` | 6200 |

Those 6 sit on 3 of the 10 identity-UNMAPPED games. The other 7 UNMAPPED games have binary YES/NO settlements and still have no Phase 4 candles.

Artifact: `ROLLER/data/nba/2025_2026/derived/warehouse_v0/settlements.parquet` (359,810 bytes) + `settlements.manifest.json`. SHA-256 `3838e5aa3ca67a5c02670d7994eeecb4b5d8b7ea108ccd42784192f4957185ce`.

---

## 6. Unresolved / duplicates / conflicts

None. Every crosswalk ticker has exactly one Suite settlement row. No YES+NO pair for one `market_id`.

---

## 7. Data-quality findings

- Canonical `kalshi_markets.csv` is a MAPPED-only projection and is **not** the settlement universe.
- `scalar` is a legitimate Kalshi source state. It is `INVALID` as a binary YES/NO, not rewritten to YES or NO.
- Box `home_win` and candle `yes_bid_close` were not read.

---

## 8. Tests

`tests/test_warehouse_settlement.py` (YES/NO/MISSING/INVALID, duplicate, conflict, unknown market, malformed, provenance, no score/price inference, idempotent rebuild, live invariants).

---

## 9. Limitations

- NBA only.
- Provisional `warehouse_v0` path. Phase 8 relocates the physical tree.
- Confirm & Run still reads published CSV, not this parquet.
- FIRST80 overlay is unused and must stay unused for this artifact.

---

## 10. Status

**PHASE 6: COMPLETE**
