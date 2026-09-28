# Phase 0 — ROLLER warehouse refactor reconnaissance

Generated: **2026-09-12T20:25:00Z** primary census; linkage/quality pass **~2026-09-12T20:33Z** (Saturday afternoon PDT).

This report is **reconnaissance only**. It is not a Parquet-migration increment, not a performance project, not an ingest, and not an execution refactor.

Prior evidence only (do **not** reuse its NBA/NCAAB/MLB numbers): [`research/parquet_migration/PHASE_0_RECON.md`](../parquet_migration/PHASE_0_RECON.md) (Friday evening 2026-09-11). That report is stale on several rows (NBA `kalshi_markets.csv` was ABSENT; `first80_triggers.csv` was ABSENT; `roller/auto_roller/` was said not to exist). **Independently recounted below from today’s disk.**

Census artifact (not a warehouse file): `/tmp/warehouse_phase0_census.json`.

**Concurrent writers (not started, not killed, not duplicated by this recon):**

- `ROLLER/scripts/update_roller.py --sport NBA` (PID 38300)
- `scripts/warehouse_finish_pipeline.py` (PIDs 12398 / 12399)

NBA canonical mtimes were unchanged between 20:25Z and 20:33Z (`games.csv` `2026-09-12T07:34:05Z`). MLB orderbook CSV **grew** during the pass (live loop). Do not start a second `update_roller` or `roller.mlb.ingest`.

Every required field is a **number**, a **path**, or **`UNCLEAR` + STOP**.

---

## Status tokens used in this report

Coverage tokens (this recon + `roller.warehouse.gap_audit.STATUSES`):

`COMPLETE` | `PARTIAL` | `MISSING` | `SOURCE_UNAVAILABLE` | `NOT_APPLICABLE` | `INVALID` | (`STALE` exists in gap_audit only)

Compile tokens (`research_query.models.ResearchStatus`):

`READY` | `READY_WITH_LIMITATIONS` | `DATA_REQUIRED` | `OPERATION_REQUIRED`

These families are **not** the same. See §12. This recon does **not** normalize them.

---

## 1. Storage inventory

Canonical published research store is still **monthly CSV**:

`ROLLER/data/{sport}/{season_key}/canonical/`

On-disk sport trees: `mlb`, `nba`, `ncaab`, `tennis`, `wnba`. **`data/nhl/` absent** → `SOURCE_UNAVAILABLE`. Tennis / WNBA trees exist and were **not** program-recounted (out of scope except where identity or “do not touch” requires a mention).

Tree sizes (today):

| Tree | `du -sh` |
| --- | --- |
| `ROLLER/data/nba/2025_2026` | **12G** |
| `ROLLER/data/ncaab/2025_2026` | **931M** |
| `ROLLER/data/mlb/2025_2026` | **1.7G** |
| NBA / NCAAB / MLB `rq_index` dirs | 71M / 31M / 69M |
| `ROLLER/meta/game_identity.csv` | 1.8M / **7 254** rows |

Declared `2026_2027` NBA/NCAAB seasons in `ROLLER/roller.json`: **ABSENT** on disk → `NOT_APPLICABLE`.

### 1.1 Per-store ledger (in-scope)

| Path | Format | Size / rows | Dates | Sport | Purpose | Producer | Consumer | Authoritative? | Migration status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `ROLLER/data/nba/2025_2026/canonical/games.csv` | CSV | 625 356 B / **1 362** | 2025-10-10…2026-06-13 | NBA | Game list + box | `update_roller` / warehouse_games | `load_dataset("games")` | **Yes** for game rows | Published CSV |
| `…/nba/…/kalshi_markets.csv` | CSV | 894 539 B / **2 704** | same season | NBA | Kalshi result | warehouse_markets `2026-09-12T07:35:19Z` | `_read_scope_tables` | **Yes** for Kalshi W | Published CSV (**new vs Friday recon**) |
| `…/nba/…/kalshi_candles/` | monthly CSV ×9 | **6 165 183** rows | 2025-10…2026-06 | NBA | 1m `yes_bid_*` | warehouse_candles_1m | Confirm & Run candles | **Yes** for TRADABLE_YES_BID | Published CSV |
| `…/nba/…/pbp/` | monthly CSV ×9 | **780 137** | 2025-10…2026-06 | NBA | Event PBP | pbp ingest | period/clock/TE snap | **Yes** for events | Published CSV |
| `…/nba/…/kalshi_trades/` | monthly CSV ×9 | **39 799 909** | 2025-10…2026-06 | NBA | Raw prints | update_roller | **Not** Confirm & Run | Source/audit | Unused by execute |
| `…/nba/…/kalshi_orderbook_snapshots/month=empty.csv` | CSV stub | **0** rows | — | NBA | Declared orderbook | placeholder | none | No | `MISSING` |
| `…/nba/…/polymarket_candles/` + `polymarket_markets.csv` | CSV | 2 539 898 / 2 514 | 2025-10…2026-06 | NBA | Other venue | Polymarket ingest | last-trade-like only | Other basis | Not Kalshi |
| `ROLLER/data/ncaab/2025_2026/canonical/games.csv` | CSV | 2 090 340 B / **5 280** | 2025-11-03…2026-04-04 | NCAAB | Game list | warehouse_games `2026-09-06` | `load_dataset` | **Yes** for games | Published CSV |
| `…/ncaab/…/kalshi_markets.csv` | — | **ABSENT** | — | NCAAB | Kalshi result | — | execute tries, FileNotFound → None | — | `MISSING` |
| `…/ncaab/…/kalshi_candles/` | monthly CSV ×7 | **2 674 280** | 2025-10…2026-04 | NCAAB | 1m yes_bid | warehouse_candles | Confirm & Run | **Yes** for TRADABLE_YES_BID | Published CSV |
| `…/ncaab/…/pbp/` | monthly CSV ×6 | **387 322** pandas rows | 2025-11…2026-04 | NCAAB | Event PBP | pbp ingest | snap | **Yes** for events | Published CSV |
| `…/ncaab/…/polymarket_*` | CSV | 367 304 / 370 | 2025-11…2026-03 | NCAAB | Other venue | Polymarket | last-trade-like | Other basis | Not Kalshi |
| `ROLLER/data/mlb/2025_2026/canonical/games.csv` | CSV | 1 590 334 B / **5 178** | 2025-03-18…2026-09-04 | MLB | Game + crosswalk stamp | `mlb.ingest` | `load_dataset` | **Yes** for MLB IDs | Published CSV |
| `…/mlb/…/kalshi_markets.csv` | CSV | 1 746 563 B / **5 607** | — | MLB | Kalshi result | ingest + landing settlement | execute | **Yes** for Kalshi W | Published CSV |
| `…/mlb/…/kalshi_last_trade/` | monthly CSV ×13 + 1 parquet sibling | **2 511 237** | see §5.3 | MLB | 1m last print | `mlb.ingest` | MLB default basis | **Yes** for LAST_TRADE_PRINT | CSV published; parquet audit sibling |
| `…/mlb/…/kalshi_candles/` | monthly CSV ×9 | **329 844** | see §5.3 | MLB | Genuine yes_bid only | landing candlesticks | selectable; quality-gated | **Yes** when present | Thin vs last-trade |
| `…/mlb/…/pbp/` | monthly CSV ×17 | **1 757 845** | 2025-03…11, 2026-02…09 | MLB | StatsAPI events | `mlb.ingest` | inning/TE snap | **Yes** for events | Published CSV |
| `…/mlb/…/kalshi_orderbook_snapshots/month=2026-09.csv` | CSV | **49 141** at 20:33Z (was 48 974 at 20:25Z) | 2026-09-11…12 | MLB | Live TOB+levels snapshot | live loop | **Not** Confirm & Run | Snapshot only | Live, growing |
| `…/mlb/…/dataset_version.json` | JSON | 1 756 B | — | MLB | Ingest notes | ingest | humans / fingerprint notes | Partial (stale `pbp_with_market: 168`) | Metadata |
| `ROLLER/meta/game_identity.csv` | CSV | 1.8M / 7 254 | — | NBA/NCAAB/WNBA | Identity table | `identity_build.py` | `load_identity`; **not** execute join | Basketball only | **No MLB rows** |
| `…/derived/research_query/indexes/rq_index_v1.0.0/{LEAGUE}/{tradable\|last_trade}/` | Parquet + `manifest.json` | see §5 | season | NBA/NCAAB/MLB | Derived **facts** | index builder | `plan_query` indexed path | Derived from CSV | Not destination architecture |
| `ROLLER/data/.cache/research_query/` | mixed | 16 files / 84 465 839 B | — | — | Query envelopes | execute cache | execute | Derived | Not warehouse |
| `ROLLER/data/.cache/research_saves/` | JSON | 9 files / 8 144 517 B | — | — | Saved envelopes | library | UI | Derived | Not warehouse |
| `ROLLER/roller/warehouse/` | Python | contract 1.0.0 | — | — | Contract/audit | overnight parquet work | Auto Roller verify; **not** Confirm & Run | Contract only | Unused by `load_dataset` |
| Suite `…/MLB/…/normalized/mlb/pbp/game_crosswalk.json` | JSON | 1 589 726 B | — | MLB | Ingest crosswalk | Foundation | `mlb.ingest` | Source for MLB IDs | Not Confirm & Run |
| Suite landing `kalshi_historical_trades` | sidecars | **8 870** files | — | MLB+ | Ingest landing | Foundation backfill | ingest | Source | Incomplete vs candles (7 336) |
| Suite landing `kalshi_historical_candles` | sidecars | **7 336** files | — | MLB+ | Ingest landing | Foundation | ingest | Source | Incomplete vs trades |
| Suite FIRST80 `candidates.json` + barrier `trades.parquet` | JSON/Parquet | 2 084 511 + 86 724 B | NBA | Frozen FIRST80 | historical warehouse | `execute_research_object` | Fixture | Not generic warehouse |
| Suite NCAAB P5 `trades.parquet` | Parquet | 61 956 B | NCAAB | Frozen P5 | historical warehouse | `execute_research_object` | Fixture | Not generic warehouse |

`game_market_crosswalk.parquet`: **ABSENT** (searched under MLB canonical and warehouse package).

### 1.2 Overlap / split-brain read paths

The same research facts exist in more than one physical store:

| Fact | Stores today |
| --- | --- |
| NBA/NCAAB/MLB 1m observations | Canonical **CSV** (authoritative for `load_dataset`) **and** compact `rq_index` `bars.parquet` (quality-filtered subset) **and** (MLB last-trade Mar only) dual-write `.parquet` sibling |
| Kalshi settlement | `kalshi_markets.csv` **and** index `settlement.parquet` **and** FIRST80 `expiration_result_yes` overlay (`official_settlement.py`) |
| Game identity | Stamped on every canonical row **and** (basketball only) `meta/game_identity.csv` **and** (MLB) Suite `game_crosswalk.json` |
| FIRST80 population | Suite derived parquet/JSON **and** ROLLER `first80_triggers.csv` (1 362 rows; **not** the frozen N=290 path) |

**Split-brain Confirm & Run reads (today):**

1. **`frozen_reference`** → `execute_research_object` → Suite FIRST80 artifacts / `first80.py` (CSV via `load_dataset` inside that object). **Does not** use `rq_index`.
2. **`generic_query` indexed** → `rq_index_v1.0.0` parquet facts → same detectors.
3. **`generic_query` full_scan** → `admin.load_dataset` monthly **CSV** → `TradableIndex.build`.
4. **`roller.warehouse` loader / dual-write parquet** → audit only. **Not** a Confirm & Run path (`loader.py` docstring).

After eventual cutover the plan requires **one** canonical Parquet read. That cutover has **not** happened. CSV remains the published source; index is derived.

---

## 2. Existing warehouse package

Inspected: `ROLLER/roller/warehouse/` (13 modules). **Not modified.**

| Item | Fact |
| --- | --- |
| Contract version | `CONTRACT_VERSION = "1.0.0"` (`__init__.py`) |
| Schema version | `SCHEMA_VERSION = "1.0.0"` (`schema.py`) |
| Modules | `__init__`, `__main__`, `schema`, `catalog`, `manifest`, `validation`, `validate_cmd`, `hashing`, `freshness`, `gap_audit`, `dual_write`, `loader`, `partitioning` |
| Schemas | Dataset **contracts** for `kalshi_candles`, `kalshi_last_trade`, `polymarket_candles`, `pbp`, `games`, `kalshi_markets`, `kalshi_orderbook_snapshots`, `polymarket_markets`. Distinct bases. **No** `Game` / `Market` / `MarketObservation` / `PBPEvent` / `Settlement` / `GameMarketLink` types. |
| Catalog | `catalog.py` walks `roller.json` declared paths. Declared ≠ data. NHL/NFL/NCAAF = `UNAVAILABLE_SPORTS`. |
| Manifests | Partition pair manifests for dual-write; `rq_index` has its own `manifest.json` (research_query, not this package). |
| Validation | `validation.py` + `validate_cmd.py` — column/e4 checks. Unused by execute. |
| Hashing | `hashing.file_sha256` for manifests. |
| Freshness | `freshness.py`: `LIVE_EXPECTED` / `DAILY_EXPECTED` / `HISTORICAL_ONLY` / `SOURCE_UNAVAILABLE` vs `CURRENT`/`STALE`/… |
| Gap audit | `gap_audit.py` statuses include `STALE` plus the six coverage tokens. Writes `reports/warehouse/gap_audit.json` (mtime `2026-09-12T05:18:01Z` — **older than today’s NBA rewrite**). |
| Dual-write | `dual_write.py` copies a month CSV → sibling parquet + manifest. **Does not** switch `load_dataset`. On disk today: MLB last-trade `month=2026-03.parquet` only (in-scope). |
| Consumers | Auto Roller verify/status (`auto_roller/verify.py`, `ingest.py`, `status.py`); `python -m roller.warehouse`; tests. **Not** `admin.load_dataset`. **Not** `execute.py`. |
| Limitations | No entity types; no persistent link table; no `get_research_context`; loader must not become a silent second path. |

**Can it represent the planned logical types today?**

| Type | In `roller.warehouse` today |
| --- | --- |
| Game | **No** type. Rows in `games.csv`. |
| Market | **No** type. Rows in `kalshi_markets.csv`. |
| MarketObservation | **No** type. Candle/last-trade CSV + `TradableBar` in `entry_engine.py`. |
| PBPEvent | **No** type. PBP CSV dicts. |
| Settlement | **No** type. `result` / `kalshi_yes_settled` columns + index `settlement.parquet`. |
| GameMarketLink | **No.** |

Explicit answers:

| Question | Answer |
| --- | --- |
| Persistent versioned `GameMarketLink`? | **No.** |
| Canonical `ResearchContext`? | **No.** `query_context.py` absent. |
| Canonical warehouse query API? | **No.** `get_research_context` absent. Catalog/gap_audit are inventory, not query. |
| One canonical read path? | **No.** CSV full_scan + parquet index + frozen Suite artifacts. |

---

## 3. Loaders and execution paths

Traced. **Not modified.**

```text
frontend draft
  → compile_draft                         (compiler.py; no I/O)
      → question_from_draft
      → compile_question
          reference_match()?              (exact FIRST80_Q3 / NCAAB_FIRST80_P5 only)
  → execute_question / execute_compiled   (ignores client execution_path)
      OPERATION_REQUIRED / DATA_REQUIRED  → envelope, rows=None
      FROZEN_REFERENCE + reference_match  → execute_research_object
      GENERIC_QUERY                       → plan_query
          indexed      → open_scope_index (rq_index facts)
          full_scan    → _load_warehouse → _load_one_scope
          unavailable  → DATA_REQUIRED (fail closed)
      → operations.py / path_engine / results_math
  → Results envelope
```

| Question | Answer |
| --- | --- |
| Does `admin.load_dataset` read monthly CSV? | **Yes.** `load_table` → `concat_partition_csvs` (`glob("*.csv")` + `pd.read_csv` + `pd.concat`). |
| Does `_load_warehouse` exist and what does it read? | **Yes** (`execute.py`). Calls `_read_scope_tables` → `load_dataset` for candle **or** last-trade dataset, `pbp`, `kalshi_markets`, `games`. |
| Is `rq_index_v1.0.0` source or derived? | **Derived fact index.** Built from the CSV warehouse. Not answers. Not the destination architecture. |
| Does execution group by ticker? | **Yes.** `_load_one_scope` builds `by_ticker`. Detectors run per ticker sequence. |
| Does execution use stamped `internal_game_id`? | **Yes**, already on rows. PBP/games filtered by that field. It is **not** recomputed in execute. |
| Does execution query a persistent `GameMarketLink`? | **No.** |
| Does `get_research_context` exist? | **No.** |

`reference_engine.py`: full-scan oracle; never opens `rq_index`; refuses `frozen_reference`.

`plan_query`: `GENERIC_QUERY` only. Index absent → `full_scan`. Stale/corrupt (`dataset_version` mismatch or checksum) → `IndexUnavailable` → fail closed. Combined leagues: all indexed → union; any missing → `full_scan` reason `combined_league_union`.

NBA index is **stale today** (see §5.1): current `scope_fingerprint=dccf5e56…` ≠ manifest `18c80ca8…`. Indexed NBA Confirm & Run will fail closed until rebuild (**not** done here).

---

## 4. Identity recon

### 4.1 Construction

| Sport | Format (observed + code) | Builder |
| --- | --- | --- |
| NBA | `NBA_{YYYYMMDD}_{AWAY}_{HOME}` e.g. `NBA_20251010_BOS_TOR` | `identity.assign_internal_ids` ← `identity_build.py` |
| NCAAB | `NCAAB_{YYYYMMDD}_{AWAY}_{HOME}` e.g. `NCAAB_20251103_AFA_BEL` | same |
| MLB | `MLB_{YYYYMMDD}_{AWAY}_{HOME}_{game_pk}` e.g. `MLB_20250928_HOU_LAA_776135` | `mlb.ingest.internal_game_id()` |
| Rematch suffix | basketball `{base}_{i}` if same date+pair | `assign_internal_ids` |

IDs were **not** changed by this recon.

### 4.2 Source IDs

| Field | Where | NBA | NCAAB | MLB |
| --- | --- | --- | --- | --- |
| `source_game_id` | identity / games / PBP | NBA stats `00125…` when `MAPPED` | ESPN/warehouse id when `MAPPED` | StatsAPI `game_pk` |
| `warehouse_game_id` | identity / games | hash / warehouse id | hash | = `game_pk` |
| `event_ticker` | identity / games / markets | `KXNBAGAME-…` | `KXNCAAMBGAME-…` | `KXMLBGAME-…` |
| Market tickers | markets / candles | `{event}-{TEAM}` | `{event}-{TEAM}` on candles | `{event}-{TEAM}` |

`meta/game_identity.csv` mapping_status today: **MAPPED 2 811**, **UNMAPPED 4 443**, **REVIEW_REQUIRED 0**. Duplicate `internal_game_id`: **0**. **MLB rows: 0.**

### 4.3 Where stamped / consumed / versioned

| Step | Fact |
| --- | --- |
| Stamped | Offline: `identity_build` writes identity CSV + basketball `games.csv` columns; `mlb.ingest` stamps MLB canonical rows from Suite `game_crosswalk.json`. |
| Consumed | Execute reads the column already on CSV/index rows. `load_identity` exists for admin/pipeline, not as a live join in `_load_one_scope`. |
| Recomputed at query time? | **No.** Execute does not call `assign_internal_ids`. |
| Materialized persistently? | **Yes, on rows** (`internal_game_id` on games, candles, last-trade, PBP, markets). Basketball also in `meta/game_identity.csv`. |
| Versioned link object? | **No.** No `GameMarketLink` table, no link version, no `game_market_crosswalk.parquet`. |

**Required conclusion (supported by disk+code):** identity is stamped/materialized on canonical rows; a persistent versioned `GameMarketLink` **does not exist**. No contradiction found.

---

## 5. Per-sport data census

**Definitions used**

| Term | Meaning |
| --- | --- |
| Games | Rows in `canonical/games.csv` with non-empty `internal_game_id` |
| Kalshi markets | Rows in `kalshi_markets.csv` |
| Unique tickers | Distinct `ticker` on the named observation file |
| Candle rows | Stored rows in `kalshi_candles/month=*.csv` (not inferred minute slots) |
| Last-trade rows | Stored rows in `kalshi_last_trade/month=*.csv` |
| PBP rows | Pandas rows (authoritative when quoted newlines inflate `wc`) |
| Settlements | Markets rows with `result` in {yes, no, scalar, blank} |
| Linked games | `games ∩ markets` on `internal_game_id` when markets file exists; else `games ∩ candle internal_game_id` |
| Unlinked games | Games not in that intersection |
| Ambiguous links | Identity `REVIEW_REQUIRED` **or** >1 event_ticker for one game without a deterministic rule. **Measured below.** |
| Invalid links | Blank `internal_game_id` on a market/observation, or non-binary settlement `scalar` |
| Games without markets | Games − market game IDs |
| Markets without games | Market rows whose `internal_game_id` is blank or not in games |
| PBP without `internal_game_id` | PBP rows with blank id |

Per-ticker 1-minute completeness (every minute of every market): **UNCLEAR + STOP** (not built).

### 5.1 NBA 2025-2026

| Metric | N / status |
| --- | --- |
| Games | **1 362** `COMPLETE` as a list |
| Kalshi markets | **2 704** rows, **2 704** tickers, **1 352** game IDs, **0** duplicate tickers, **exactly 2 markets/game** on those 1 352 |
| Unique candle tickers | **2 704** |
| Candle rows | **6 165 183** (stored observations) |
| Last-trade rows | `NOT_APPLICABLE` (dir absent) |
| PBP rows | **780 137** |
| Settlements | yes 1 352 / no 1 352 / blank 0 / other 0 |
| Linked games | **1 352** |
| Unlinked / games without markets | **10** (identity `UNMAPPED`, no `source_game_id`) |
| Ambiguous links | **0** (`REVIEW_REQUIRED=0`; 2 tickers/game is the binary pair, not ambiguous) |
| Invalid links | **0** on markets/candles/PBP |
| Markets without games | **0** |
| PBP without `internal_game_id` | **0** |
| Date coverage | games 2025-10-10 → 2026-06-13 (215 dates) |
| Missing in-span candle/PBP months | **none** (9 months 2025-10…2026-06) |
| Orderbook | `MISSING` (`month=empty.csv`, 0 rows) |
| `rq_index` tradable | **INVALID/stale**: built 2026-09-11T22:30:49Z; fingerprint mismatch; 5 777 716 bars; settlement_rows=0 |

10 unmapped IDs: `NBA_20260108_MIA_CHI`, `NBA_20260124_GSW_MIN`, `NBA_20260125_DAL_MIL`, `NBA_20260125_DEN_MEM`, `NBA_20260414_MIA_CHA`, `NBA_20260414_POR_PHX`, `NBA_20260415_GSW_LAC`, `NBA_20260415_ORL_PHI`, `NBA_20260417_CHA_ORL`, `NBA_20260417_GSW_PHX`. Cause: **UNCLEAR + STOP**.

### 5.2 NCAAB 2025-2026

| Metric | N / status |
| --- | --- |
| Games | **5 280** |
| Kalshi markets | **MISSING** (file absent) |
| Unique candle tickers | **1 698** |
| Candle rows | **2 674 280** |
| Last-trade rows | `NOT_APPLICABLE` |
| PBP rows | **387 322** pandas / **398 585** physical lines (quoted newlines in `event_description`) |
| Settlements | `MISSING` |
| Linked games (∩ candles) | **849** (identity `MAPPED` 849) |
| Unlinked / games without candle markets | **4 431** |
| Ambiguous links | **0** in identity (`REVIEW_REQUIRED=0`) |
| Invalid links | **0** blank PBP/candle ids |
| Markets without games | N/A (no markets file) |
| PBP without `internal_game_id` | **0** |
| Candle games without PBP | **2** |
| Date coverage | games 2025-11-03 → 2026-04-04 (143 dates) |
| Missing months | PBP has no `2025-10` (candles do; 2 733 rows) |
| Orderbook | `MISSING` (dir absent) |
| `rq_index` tradable | fingerprint **matches** (`84097906…`); 2 252 832 bars; settlement_rows=0 |

### 5.3 MLB 2025-2026

| Metric | N / status |
| --- | --- |
| Games | **5 178** (0 duplicate IDs) |
| Kalshi markets | **5 607** rows / **5 607** unique tickers |
| Unique last-trade tickers | **6 862** |
| Unique candle tickers | **399** |
| Last-trade rows | **2 511 237** |
| Candle rows | **329 844** |
| PBP rows | **1 757 845** |
| Settlements | yes 2 798 / no 2 805 / scalar **4** / blank 0 |
| Linked games (∩ market IDs) | **2 785** (2 784 with 2 sides + **1** with 1 side: `MLB_20260802_MIL_LAA_823996`) |
| Games without market rows | **2 393** |
| Markets without games | **38** rows with **blank** `internal_game_id` (19 event tickers: doubleheader `*2` and All-Star `ALLS`/`ALHS`/`NLHS`/`NLLS`). **INVALID** as game links. |
| Ambiguous links | **0** `REVIEW_REQUIRED`. The 38 blank-gid rows are invalid/unlinked, not a scored ambiguous pair. |
| Last-trade IDs not in games | **0** (non-blank) |
| Last-trade rows blank gid | **9 073** |
| Candle rows blank gid | **2 014** |
| PBP without `internal_game_id` | **0** |
| PBP ∩ markets | **2 744** |
| Games without PBP | **70** |
| Date coverage | games 2025-03-18 → 2026-09-04 (412 dates) |
| Last-trade months missing in span | **2025-03, 2025-12, 2026-01, 2026-02, 2026-08, 2026-09** |
| Candle months missing in span | **2025-03, 2025-05…09, 2025-12, 2026-01–02, 2026-04–05, 2026-08–09** |
| PBP months missing in span | **2025-12, 2026-01** |
| Orderbook | `PARTIAL` live Sep only; **49 141** rows at 20:33Z; **all 49 141 blank `internal_game_id`**; 110 tickers |
| `rq_index` last_trade | fingerprint **matches** `b1f7da70…`; 2 511 237 bars; settlement_rows 5 468 |
| `rq_index` tradable | same fingerprint; 7 408 bars / 26 games / 399 tickers |

Why 1 430 last-trade tickers are absent from `kalshi_markets.csv`: **UNCLEAR + STOP** (counted; not classified).

---

## 6. Market observation semantics

| Dataset | Basis | Timestamp | Price field | OHLC actually on file | Volume | `available_at` | Gaps | Derived? | Executable quote? | Historical candle? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NBA/NCAAB/MLB `kalshi_candles` | `TRADABLE_YES_BID` | `candle_timestamp` / `event_timestamp` / `available_at` | `yes_bid_close` | `yes_bid_open/high/low/close`, `yes_ask_*` | yes (source volume) | yes | Absent minutes are absent (no slot rows) | Ingested from Kalshi candlesticks | Yes, after `quality()` | Yes |
| MLB `kalshi_last_trade` | `LAST_TRADE_PRINT` | same clock columns | `last_close_e4` | `last_open/high/low/close_e4` | `volume`, `print_count` | yes | No print → no row | Aggregated from prints | **No** | 1m print OHLC, not TOB |
| MLB orderbook CSV | `ORDERBOOK_SNAPSHOT` | `captured_at` | `best_yes_bid_e4` | none (levels JSON) | dollars on levels | yes | Snapshots only | Live capture | TOB at capture, not a fill | **Not** historical L2 |
| Polymarket candles | `LAST_TRADE_PRINT`-like | candle clocks | last-price style | present | present | yes | absence | Other venue | **No** Kalshi TOB | Other venue |
| NBA `kalshi_trades` | prints | trade time | trade price | n/a | n/a | — | — | raw | Not execute input | ticks |

**LAST_TRADE_PRINT ≠ TRADABLE_YES_BID.** Separate columns, separate index leaves, separate `quality()` rules. `mlb.ingest` never writes `yes_bid` from a print.

### 6.1 `last_close_e4` and legacy `TradableBar.bid`

`entry_engine.py`:

- `tradable_sequence`: `bid = yes_bid_close`, `ask = yes_ask_close`, `basis=TRADABLE_YES_BID`, `quality()` applied.
- `last_trade_sequence`: `bid = last_close_e4`, `ask = None`, `basis=LAST_TRADE_PRINT`, **no** `quality()`.

So **yes**: on last-trade, legacy `TradableBar.bid` **is the last-trade print**, not a yes bid. `results_math/last_trade_display.py` records `tradable_bar_bid_is_not_yes_bid: True`. Do not relabel the field. Detectors read `.bid` on whichever basis the sequence was built.

---

## 7. PBP inventory

| | NBA | NCAAB | MLB |
| --- | --- | --- | --- |
| Source | NBA stats PBP (`source_dataset=pbp`, `source_game_id` like `0012500044`) | same family (`event_number`, period/clock); `source_game_id` when mapped | MLB StatsAPI (`mlb_statsapi`, `source_game_id=game_pk`) |
| Granularity | Event rows (period start, shots, …) | Event rows | Event rows (count, runners, advisory, …) |
| Source event ID | `event_number` | `event_number` | `event_number` |
| Timestamps | `event_timestamp`, `time_actual`, `available_at`, `ingested_at` | `event_timestamp`, `available_at`, `ingested_at` | `event_timestamp`, `available_at`, `ingested_at` |
| Period | `period` + ISO `clock` (`PT12M00.00S`) | `period` + `clock` (`20:00`) | `period`/`inning`/`half` (clock column often empty) |
| Game clock | basketball clock string | basketball clock string | **No 48-minute clock** |
| `internal_game_id` | 780 137 / 780 137 | 387 322 / 387 322 | 1 757 845 / 1 757 845 |
| Source game ID | present on NBA rows | present when mapped | = `game_pk` |
| Temporal alignment | `base_terminal_efficiency.pit`: `available_at < observation_ts` (equality invisible) | same basketball I(t) | `mlb.snap`: last event with `event_timestamp <=` entry ts; never snap forward; missing → `UNALIGNED` |

**Identity linkage ≠ PIT alignment.** A PBP row can carry a valid `internal_game_id` and still be `UNALIGNED` if no event is visible at the entry timestamp. `entry_engine._alignment` maps snap `UNALIGNED` / `AMBIGUOUS` / `MODELED`. Period/clock filters **fail closed** on a missing snap (`apply_period_clock`). This recon did **not** measure how many entries would snap UNALIGNED (that is execute-time). Identity coverage is §5; PIT success rate: **UNCLEAR + STOP** (not executed).

Do not interpolate PBP. Missing PBP ≠ fabricated event.

---

## 8. Settlement inventory

| Source | Market ID | Field | YES/NO | Missing | Timestamp | Coverage | Authoritative? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| NBA `kalshi_markets.csv` | `ticker` | `result`, `kalshi_yes_settled`, `settlement_value_e4` | yes/no 2704 | 0 blank | `settlement_time` / `result_available_at` | 1352 games | **Yes** Kalshi result |
| NCAAB `kalshi_markets.csv` | — | — | — | file absent | — | 0 | `MISSING` |
| MLB `kalshi_markets.csv` | `ticker` | same | 2798 / 2805 | 0 blank; **4 scalar** | same | 2785 games + 38 blank-gid rows | **Yes** when `result` ∈ {yes,no}; scalar `INVALID` as binary |
| `rq_index` settlement.parquet | ticker | copied result | NBA index **0** rows (stale); NCAAB 0; MLB last-trade 5468 | missing stays missing | — | derived | Derived from CSV |
| FIRST80 `expiration_result_yes` | ticker | overlay | yes/no | no fill from score | — | frozen candidates | Official Kalshi W **overlay** only when warehouse `result` missing (`official_settlement.merge_official_settlement`) |

`canonical/markets.py`: “W is not box home_win.” `mlb.ingest` notes: never infer from PBP. `base_terminal_efficiency/settlement.py`: Kalshi only.

**Does any code infer settlement from score/PBP?** Inspected execute/official_settlement/mlb.ingest/warehouse schema: **no**. Overlay is FIRST80 Kalshi `expiration_result_yes` + complementary binary side. Box `home_win` on `games.csv` is **not** used as Kalshi W.

`official_settlement_health()` still hard-codes `"canonical_kalshi_markets": "ABSENT"`. That string is **stale vs today’s NBA+MLB files**. Not repaired here.

---

## 9. Orderbook inventory

| Sport | Status | Evidence |
| --- | --- | --- |
| NBA | `MISSING` | Canonical stub `month=empty.csv` 0 rows. Raw JSON 0. |
| NCAAB | `MISSING` | Directory absent. |
| MLB | `PARTIAL` | Canonical `month=2026-09.csv` **49 141** rows at 20:33Z (live). Raw JSON days 2026-09-11 and 2026-09-12, **48 977** files at 20:25Z. Fields: `captured_at`, `best_yes_bid_e4`, `best_no_bid_e4`, `yes_levels`, `no_levels`, JSON books. Note on rows: `official bids-only snapshot; not a fill; not historical L2`. **All snapshot rows have blank `internal_game_id`.** Granularity: live loop captures, not 1m history. |
| NHL / others | `SOURCE_UNAVAILABLE` | No warehouse / no live series. |

**L2 synthesis is not present and must not be introduced as a fallback.**

---

## 10. Lock / execution inventory

| Object | Expected N | Compile | Execute | Fixture path |
| --- | ---: | --- | --- | --- |
| FIRST80 frozen `FIRST80_Q3` | **290** | `frozen_reference` | `execute_research_object` | increment1 goldens |
| NCAAB `NCAAB_FIRST80_P5` | **721** | `frozen_reference` | `execute_research_object` | `bindings.py` + P5 parquet |
| Increment 2 `second_touch_80` | **1087** | `generic_query` | generic / index | increment1 goldens |
| Increment 2 `first_60_q2` | **271** | `generic_query` | generic / index | same |
| Increment 2 `sequential_40_recover_80` | **1552** | `generic_query` | generic / index | same |
| Increment 2 `layered_and` | **288** | `generic_query` | generic / index | same |
| MLB FT75 / TE lead+1 dated | **554** | `generic_query` | last-trade generic | `mlb_golden_ft75_lead1_dated.json` |
| MLB 1661 | **1661** | results-layer verify-only | not a warehouse N | `test_last_trade_results.py` |

**These are regression fixtures, not the desired research architecture.** They were **not** deleted.

### Exact frozen gate (today)

`compiler.reference_match()` returns a lock **only** for the exact FIRST80 tuple (Kalshi+candles, full season, first touch 80, reach 40, Q3/P5). Then `compile_question` sets `execution_path=FROZEN_REFERENCE`. `execute_compiled` calls `execute_research_object`.

Ordinary generic research **does not** require `frozen_reference` / a pre-existing research object **if** the draft is not that exact tuple. Increment 2 and MLB 554 already run `generic_query`.

**However:** any new question that **is** that exact FIRST80 tuple is still forced through the frozen executor. That is the remaining execution gate. Later phases must stop using it as the ordinary path. **Not removed in Phase 0.**

Warehouse FIRST80 settled-book constant `NBA_FIRST80_EXPECTED_N=1230` is a **different** binding. Do not conflate with Confirm & Run **290**.

---

## 11. Operation / semantic inventory

Authority: `operations.py` (`OPERATION_SEMANTICS_VERSION = 1.0.0`). Frontend chips are **not** evidence.

| Op | Detector exists? | Compile |
| --- | --- | --- |
| FIRST / SECOND / THIRD / NTH TOUCH | Yes (`entry_engine` ordinals + `first_cross` family) | Implemented |
| CROSS | `first_cross` | Implemented. Equality on current counts. **Cross ≠ First Touch** (touch is ordinal + seen_below; cross is directional close-cross). |
| BREAK | `first_break` | Implemented. Strictly beyond P. **Break ≠ Cross** (79→80 is Cross, not Break). |
| REVERSION | `first_reversion` | Implemented (entry). |
| BOUNCE (entry) | `first_bounce` | Implemented as **entry**. |
| RECOVERY | `first_recovery` | Implemented (entry / sequential path recover). |
| ABOVE / BELOW | `first_above` / `first_below` | Implemented |
| MAXIMUM TOUCH / MINIMUM TOUCH | `first_maximum_touch` / `first_minimum_touch` | Implemented |
| Path REACH / DROP_TO / RISE_TO / RECOVER | supported path ops | Implemented |
| Path HORIZON_WIN / HORIZON_LOSS | supported if kind+minutes | MLB/tennis **game** clock → `OPERATION_REQUIRED` |
| Path **bounce** | in `UNSUPPORTED_PATH` | **`OPERATION_REQUIRED`** (path family, not entry) |
| Path **revert** | `UNSUPPORTED_PATH` | **`OPERATION_REQUIRED`** |
| Path **maximum_move** / **minimum_move** | `UNSUPPORTED_PATH` | **`OPERATION_REQUIRED`** |
| Path **never_reach** | `UNSUPPORTED_PATH` | **`OPERATION_REQUIRED`** |

`unsupported ≠ substitute.` Compiler returns `OPERATION_REQUIRED` with no rows (not N=0). Formulas were **not** rewritten.

---

## 12. Status vocabulary

| Vocabulary | Tokens | Where |
| --- | --- | --- |
| Warehouse coverage | COMPLETE, PARTIAL, MISSING, SOURCE_UNAVAILABLE, NOT_APPLICABLE, INVALID, **STALE** | `warehouse/gap_audit.py` |
| Freshness | LIVE_EXPECTED, DAILY_EXPECTED, HISTORICAL_ONLY, SOURCE_UNAVAILABLE × CURRENT, STALE, … | `warehouse/freshness.py` |
| Compile | READY, READY_WITH_LIMITATIONS, DATA_REQUIRED, OPERATION_REQUIRED | `ResearchStatus` |
| Execute envelope | COMPLETE, OPERATION_REQUIRED, DATA_REQUIRED, READY_WITH_LIMITATIONS | `execute.py` |
| Measurement cells | COMPLETE, ABSENT | execute measurements |
| Results math | OBSERVED, DERIVED, HYPOTHETICAL, UNAVAILABLE, INCOMPLETE, DATA_REQUIRED, NOT_APPLICABLE, INVALID_SEMANTICS, AMBIGUOUS, … | `results_math/models.py` |
| Identity mapping | MAPPED, UNMAPPED, REVIEW_REQUIRED | `identity.py` (REVIEW unused on disk: 0) |
| PBP snap alignment | aligned, unaligned, modeled, ambiguous | `entry_engine._alignment` |
| Dual-write | INGESTED, FAILED | `dual_write.py` |
| Auto Roller verify | COMPLETE, FAILED | `auto_roller/verify.py` |
| `official_settlement_health` | AVAILABLE, ABSENT, USED, UNAVAILABLE | overlay helper |

**Conflicts (not normalized):**

- `COMPLETE` means “artifact present” in gap_audit, “query finished” in execute, and “metric computed” in measurements.
- `NOT_APPLICABLE` exists in warehouse coverage **and** results math.
- `DATA_REQUIRED` is compile **and** results math.
- `INVALID` (coverage) vs `INVALID_SEMANTICS` (results).
- `STALE` is warehouse-only; this recon also used it for the NBA index fingerprint mismatch (`INVALID`/`STALE`).
- Gap_audit still labels NBA `kalshi_markets` `MISSING` in the **Friday** `DATA_COVERAGE.md` / `gap_audit.json` (05:18Z). **Today the file exists.** Competing reports vs disk.

---

## 13. Data quality / linkage recon

Measured; **not repaired.**

| Issue | NBA | NCAAB | MLB |
| --- | --- | --- | --- |
| Games with no markets | 10 | 4 431 (no markets file; no candles) | 2 393 |
| Markets with no games | 0 | N/A | **38** blank-gid rows |
| Games with multiple candidate markets | 1 352 × binary pair (expected) | 849 × binary pair on candles | 2 784 × pair; **1** singleton side; **38** orphans across 19 events |
| Ambiguous identity | 0 REVIEW | 0 REVIEW | 0 REVIEW; MLB not in identity CSV |
| Invalid identity | 10 UNMAPPED (no source id) | 4 431 UNMAPPED | 38 blank market gids; 9 073 last-trade / 2 014 candle / 49 141 orderbook blank gids |
| PBP with no `internal_game_id` | 0 | 0 | 0 |
| Observations with no `internal_game_id` | 0 candles | 0 candles | last-trade 9 073; candles 2 014 |
| Settlement with no market identity | 0 (all have ticker) | file missing | 0 blank tickers; 38 lack game id |
| Duplicate market identity | 0 dup tickers | — | 0 dup tickers |
| Duplicate observation keys (`ticker,candle_timestamp`) | 0 in `2025-10` (541 322 rows) | 0 in `2026-01` (1 051 569 rows) | 0 in last-trade `2026-06` (529 630 rows) |
| Full-warehouse duplicate scan | **UNCLEAR + STOP** (only sampled months; 6M+ rows not fully keyed) | same | same |
| Timestamp anomalies | **UNCLEAR + STOP** (not audited for DST/out-of-order) | same | same |
| Missing date ranges | none in-span for candles/PBP | PBP missing 2025-10 | last-trade/candles holes §5.3 |
| Impossible/malformed | — | PBP line/pandas gap explained (quoted newlines) | 4 `result=scalar`; 38 blank-gid markets |

---

## 14. Capability map

| Capability | NBA | NCAAB | MLB | Current source | Basis | Status | Evidence | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Kalshi candles | yes | yes | thin | canonical CSV | TRADABLE_YES_BID | NBA/NCAAB PARTIAL-complete months; MLB PARTIAL | §5 | MLB quality-gated |
| Kalshi last trade | no dir | no dir | yes | canonical CSV | LAST_TRADE_PRINT | N/A / N/A / PARTIAL | §5.3 | Default MLB basis |
| Kalshi settlement | file yes | **MISSING** | file yes | `kalshi_markets.csv` | n/a | COMPLETE / MISSING / PARTIAL | §8 | 4 MLB scalar |
| PBP | yes | yes | yes | canonical CSV | n/a | PARTIAL | §7 | Identity ≠ PIT |
| Game identity | yes | yes | on games.csv only | identity CSV / ingest | n/a | COMPLETE / PARTIAL / PARTIAL | §4 | No MLB identity rows |
| Market identity | tickers | candle tickers only | tickers | markets/candles | n/a | COMPLETE / PARTIAL / PARTIAL | §5 | |
| Game-market linkage | stamped rows | stamped on candles | stamped + 38 orphans | columns | n/a | PARTIAL | no GameMarketLink | |
| Orderbook/L2 | stub | absent | live Sep | snapshots | ORDERBOOK_SNAPSHOT | MISSING / MISSING / PARTIAL | §9 | No L2 synthesis |
| PIT availability | I(t) `<` | I(t) `<` | `event_ts <=` | pit.py / snap.py | n/a | implemented | §7 | Success rate UNCLEAR |
| Generic ResearchQuestion | yes | yes | yes | compile + execute | per draft | READY if data+ops | Increment 2, MLB 554 | Not lock-gated unless exact FIRST80 tuple |
| Frozen reference | FIRST80_Q3 | NCAAB_FIRST80_P5 | no | Suite artifacts | candles | fixture | §10 | Must not stay the architecture |
| Cross | impl | impl | impl | operations.py | bar.bid | implemented | §11 | ≠ First Touch |
| Touch | impl | impl | impl | entry_engine | bar.bid | implemented | §11 | |
| Break | impl | impl | impl | operations.py | bar.bid | implemented | ≠ Cross | |
| Reversion | impl | impl | impl | operations.py | bar.bid | implemented | entry | |
| Bounce | entry impl; **path OPERATION_REQUIRED** | same | same | operations + UNSUPPORTED_PATH | — | mixed | UI path bounce ≠ entry bounce | |
| Recovery | impl | impl | impl | operations.py | bar.bid | implemented | | |

Frontend-recognized but unavailable (examples): tick, L2, KenPom, NCAA PBP chip, Polymarket-as-Kalshi, NHL, NCAAB Kalshi settlement, MLB game-clock horizon, path bounce/revert/never_reach. Those compile to `DATA_REQUIRED` or `OPERATION_REQUIRED`, not a substitute.

---

## 15. Current architectural state

**Current (inspected):**

```text
frontend draft
  → compile_draft → ResearchQuestion
  → compiler routing
        ↳ exact FIRST80_Q3 / NCAAB_FIRST80_P5 → frozen_reference
              → execute_research_object → Suite FIRST80 artifacts / first80.py
        ↳ else generic_query (or OPERATION_REQUIRED / DATA_REQUIRED)
              → plan_query
                    ↳ rq_index parquet (if fingerprint matches)
                    ↳ else CSV admin.load_dataset / _load_warehouse
              → ticker assembly + stamped internal_game_id
              → operations.py detectors
  → Results
```

**Target (plan only — not implemented):**

```text
frontend
  → ResearchQuestion
  → capability resolution
  → warehouse query plan
  → canonical linked warehouse
  → ResearchContext
  → exact operation execution
  → Results
```

Phase 0 does **not** implement the target.

---

## 16. Required Phase 0 conclusions

1. **Where does each sport’s authoritative available data live?**  
   Published Confirm & Run data: `ROLLER/data/{nba,ncaab,mlb}/2025_2026/canonical/` monthly **CSV** (+ MLB `kalshi_markets.csv` / `games.csv`). Ingest sources: Backtesting Suite landing/normalized. Frozen FIRST80: Suite derived parquet/JSON.

2. **What is duplicated?**  
   CSV observations vs `rq_index` bars/PBP/settlement; MLB last-trade Mar dual-write parquet; basketball identity CSV vs stamped game rows; FIRST80 Suite artifacts vs `first80_triggers.csv`; Kalshi W vs FIRST80 `expiration_result_yes` overlay.

3. **Which path does Confirm/Run actually use today?**  
   `compile_draft` → `execute_question`. Frozen tuple → `execute_research_object`. Else `plan_query` → index or CSV `_load_warehouse`. `roller.warehouse` is **not** that path.

4. **Is identity currently materialized?**  
   **Yes**, on canonical rows (and basketball `meta/game_identity.csv`).

5. **Is `GameMarketLink` persistently materialized/versioned?**  
   **No.**

6. **Is there a canonical `ResearchContext`?**  
   **No.**

7. **Can a new arbitrary valid ResearchQuestion run without a frozen object?**  
   **Yes, if** it is not the exact FIRST80 lock tuple **and** data+ops exist → `generic_query` / `READY` (or `READY, N=0`). Exact FIRST80 tuple is still forced frozen. Missing data → `DATA_REQUIRED`. Unimplemented path bounce/revert/… → `OPERATION_REQUIRED`.

8. **Which frontend-recognized capabilities are actually unavailable?**  
   NCAAB Kalshi settlement; NBA/NCAAB last-trade dirs; NBA/NCAAB orderbook; historical L2; tick; KenPom/NCAA PBP; Polymarket-as-Kalshi TOB; NHL; MLB game-clock horizon; path bounce/revert/max-min move/never_reach; complete MLB yes-bid history.

9. **Which observation bases are actually present?**  
   `TRADABLE_YES_BID` (NBA/NCAAB candles; thin MLB candles). `LAST_TRADE_PRINT` (MLB last-trade; Polymarket-like). `ORDERBOOK_SNAPSHOT` (MLB live Sep only).

10. **Which PBP datasets are identity-linked but not PIT-aligned?**  
    All three sports stamp `internal_game_id` on essentially all PBP rows. PIT is a **later** snap (`available_at < t` basketball; `event_timestamp <= t` MLB). Identity success is **not** PIT proof. PIT miss rate: **UNCLEAR + STOP**.

11. **Which settlement datasets are authoritative?**  
    Kalshi `kalshi_markets.result` (NBA, MLB). NCAAB: none. Overlay: FIRST80 `expiration_result_yes` only to fill missing warehouse results. Not box score. Not PBP.

12. **Which orderbook datasets actually exist?**  
    MLB live September snapshots only. NBA stub empty. NCAAB absent. No historical L2.

13. **What prevents the canonical linked warehouse from being the sole research source today?**  
    Confirm & Run still reads CSV or a derived index or Suite frozen artifacts; no `GameMarketLink`; no `ResearchContext`; no warehouse query API; NBA index stale; NCAAB settlement missing; MLB observation holes; lock still gates the exact FIRST80 tuple; split-brain stores.

14. **Which historical locks must be retained as regression fixtures?**  
    FIRST80 frozen **290**, NCAAB P5 **721**, Increment 2 **1087 / 271 / 1552 / 288**, MLB FT75/TE **554**, MLB **1661** verify-only. Do not delete or overwrite.

---

## Phase 0 acceptance

| Check | Status |
| --- | --- |
| `research/warehouse_refactor/PHASE_0_RECON.md` exists | yes |
| Sections 1–16 exist | yes |
| NBA/NCAAB/MLB independently recounted from today’s disk | yes (20:25Z census + 20:33Z quality pass) |
| No count copied blindly from parquet_migration recon | yes (cited as prior evidence only) |
| Paths identified or UNCLEAR+STOP | yes |
| Loaders/execution traced | yes |
| Identity path traced | yes |
| Persistent GameMarketLink nonexistence established | yes |
| PBP identity vs PIT distinguished | yes |
| Observation bases preserved | yes |
| Settlement semantics established | yes |
| Orderbook availability established | yes |
| Frozen locks inventoried, not deleted | yes |
| No architectural code changed | yes |
| No ingest started | yes |
| Running ingest/update not killed or duplicated | yes |
| No frontend changes | yes |
| No execution semantics changed | yes |
| No golden overwritten | yes |
| No tennis warehouse/index/UI work | yes |
| Cites `research/parquet_migration/PHASE_0_RECON.md` | yes |

**STOP.**

Phase 1 is not authorized. Do not add `crosswalk.py`, `coverage.py`, `query_context.py`, `GameMarketLink` parquet, compiler/execute/`load_dataset` changes, backfill, Parquet cutover, or performance work.
