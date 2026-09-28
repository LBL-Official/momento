# Phase 2 — Canonical Game identity

Measured: **2026-09-13T05:47:08Z** (Saturday evening PDT, 2026-09-12).

Phase 0 recon remains the warehouse census. Phase 1 remains the logical entity types. This report is **Game identity only**. Counts were re-read from disk today. They were not copied from Phase 0 without verification.

Identity rule version: **`IDENTITY_RULE_VERSION = 1.0.0`**.

---

## 1. Current identity architecture

There is still **one** identity artifact: `ROLLER/meta/game_identity.csv`.

| Role | Fact |
| --- | --- |
| Authoritative catalog | `ROLLER/meta/game_identity.csv` |
| Producer (NBA / NCAAB / WNBA) | `ROLLER/roller/canonical/identity_build.py` via `assign_internal_ids` |
| Producer (MLB append) | `roller.warehouse.identity.extend_identity_artifact` copies IDs already on `games.csv` |
| MLB ID mint (ingest, unchanged) | `ROLLER/roller/mlb/ingest.py` `internal_game_id()` → `MLB_{YYYYMMDD}_{AWAY}_{HOME}_{game_pk}` |
| Game universe (per sport) | `ROLLER/data/{nba,ncaab,mlb}/2025_2026/canonical/games.csv` |
| Consumers | `admin.load_identity`; basketball `canonicalize_games` (stamps rows from the catalog); integrity; update registry |
| Versioning | Code constant `IDENTITY_RULE_VERSION`. Artifact rows keep `created_at` / `updated_at`. No `game_identity_v2.csv`. |
| Query-time | Execute still **consumes stamped** `internal_game_id` on CSV rows. It does **not** call `assign_internal_ids`. `load_identity` is not the execute join. **`execute.py` was not modified.** |

Before Phase 2 the catalog was basketball-only (**7 254** rows: NBA 1 362 / NCAAB 5 280 / WNBA 612; **0 MLB**). MLB identity lived only on `games.csv`. Phase 2 **extended** the existing catalog; it did not create a second store.

Construction path required by this phase:

```text
source game identity
        ↓
canonical internal_game_id
        ↓
Game
```

Not used, and not implemented:

```text
ticker / date / team names → guess → internal_game_id
```

`mapping_status` (`MAPPED` / `UNMAPPED` / `REVIEW_REQUIRED`) is a **source-crosswalk** flag on the artifact. It is **not** the Phase 2 identity vocabulary.

---

## 2. Canonical Game identity model

Same Phase 1 `Game` entity. No second Game type.

| Field | Role |
| --- | --- |
| `internal_game_id` | ROLLER canonical join key |
| `sport` / `league` / `season` / `game_date` | Required identity fields |
| `scheduled_at` | Optional. Copied from `scheduled_start` when present. **Not invented.** |
| `source_game_id` | Source-native ID. **≠** `internal_game_id` |
| `source_system` | `nba_stats` / `espn` / `mlb_statsapi` |
| `warehouse_game_id` | Warehouse/hash or MLB `game_pk` |
| `event_ticker` | Provenance only. **Not** Game identity |
| `identity_rule_version` | `1.0.0` |

Preserved ID formats (not renamed):

| Sport | Format | Example on disk today |
| --- | --- | --- |
| NBA | `NBA_{YYYYMMDD}_{AWAY}_{HOME}[_{n}]` | `NBA_20251010_BOS_TOR` |
| NCAAB | `NCAAB_{YYYYMMDD}_{AWAY}_{HOME}[_{n}]` | `NCAAB_20251103_AFA_BEL` |
| MLB | `MLB_{YYYYMMDD}_{AWAY}_{HOME}_{game_pk}` | `MLB_20250928_HOU_LAA_776135` |

Basketball rematch suffix `{base}_{n}` (`n≥2`) remains the existing `assign_internal_ids` rule (sort by `scheduled_start`, then `event_ticker`, then `warehouse_game_id`). **Zero rematch suffixes** exist on today’s NBA / NCAAB / MLB game rows.

MLB is **not** reminted by `identity_build`. `assign_internal_ids` would drop `game_pk`. `build_identity(..., sports=["MLB"])` now keeps existing MLB catalog rows.

---

## 3. Source ID mappings

| Sport | `source_system` | Source field | `source_game_id` on disk |
| --- | --- | --- | --- |
| NBA | `nba_stats` | `nba_game_id` | NBA stats id, e.g. `0012500044` |
| NCAAB | `espn` | `espn_game_id` | ESPN/warehouse id when present |
| MLB | `mlb_statsapi` | `game_pk` | StatsAPI `game_pk`, e.g. `776135` |

Kalshi tickers are **not** source game IDs. `event_ticker` / `kalshi_market_yes_*` remain catalog columns for provenance already defined on the artifact schema. They are **not** a `GameMarketLink`.

---

## 4. Identity status vocabulary

Distinct from warehouse coverage and from `mapping_status`:

`VALID` | `DUPLICATE` | `CONFLICT` | `AMBIGUOUS` | `INVALID` | `MISSING`

Fail closed. No nearest-date / nearest-team repair. No ticker inference.

`resolve_internal_game_id` accepts only `sport` + `source_game_id` and/or `internal_game_id` plus a catalog lookup. Unknown source → `MISSING`. Disagreeing source vs catalog → `CONFLICT`. A ticker string → `INVALID`.

---

## 5. Coverage (games.csv universe, measured today)

Season on disk for all three sports: **2025-2026** only. Declared `2026-2027` NBA/NCAAB trees remain absent (`NOT_APPLICABLE`).

### NBA

| Metric | Value |
| --- | --- |
| Total games | **1 362** |
| With `internal_game_id` | **1 362** |
| Without `internal_game_id` | **0** |
| Unique `internal_game_id` | **1 362** |
| Duplicate IDs | **0** |
| With `source_game_id` | **1 352** |
| Without `source_game_id` | **10** |
| Unique source IDs | **1 352** |
| Duplicate source IDs | **0** |
| One source → many internals | **0** |
| Season / league | 2025-2026 / NBA |
| Date range | 2025-10-10 … 2026-06-13 |
| `scheduled_start` present | 81 (absent 1 281; not invented) |
| Identity status | **VALID 1 362**; 0 DUPLICATE / CONFLICT / AMBIGUOUS / INVALID / MISSING |
| Catalog overlap | games∩identity **1 362**; games-only 0; identity-only 0; source mismatch 0 |

The 10 NBA games with a valid ID and no source id (still `VALID`, source provenance `MISSING` as coverage — not reminted):

| `internal_game_id` | Date |
| --- | --- |
| `NBA_20260108_MIA_CHI` | 2026-01-08 |
| `NBA_20260124_GSW_MIN` | 2026-01-24 |
| `NBA_20260125_DAL_MIL` | 2026-01-25 |
| `NBA_20260125_DEN_MEM` | 2026-01-25 |
| `NBA_20260414_MIA_CHA` | 2026-04-14 |
| `NBA_20260414_POR_PHX` | 2026-04-14 |
| `NBA_20260415_GSW_LAC` | 2026-04-15 |
| `NBA_20260415_ORL_PHI` | 2026-04-15 |
| `NBA_20260417_CHA_ORL` | 2026-04-17 |
| `NBA_20260417_GSW_PHX` | 2026-04-17 |

### NCAAB

| Metric | Value |
| --- | --- |
| Total games | **5 280** |
| With `internal_game_id` | **5 280** |
| Without `internal_game_id` | **0** |
| Unique `internal_game_id` | **5 280** |
| Duplicate IDs | **0** |
| With `source_game_id` | **849** |
| Without `source_game_id` | **4 431** |
| Unique source IDs | **849** |
| Duplicate source IDs | **0** |
| One source → many internals | **0** |
| Season / league | 2025-2026 / NCAAB |
| Date range | 2025-11-03 … 2026-04-04 |
| `scheduled_start` present | **0** (not invented) |
| Identity status | **VALID 5 280**; all other statuses 0 |
| Catalog overlap | games∩identity **5 280**; games-only 0; identity-only 0; source mismatch 0 |

NCAAB market/candle gaps from Phase 0 are **not** identity failures. Those 4 431 games have deterministic `NCAAB_{date}_{away}_{home}` IDs and no ESPN source id. No fake market identities were added.

### MLB

| Metric | Value |
| --- | --- |
| Total games | **5 178** |
| With `internal_game_id` | **5 178** |
| Without `internal_game_id` | **0** |
| Unique `internal_game_id` | **5 178** |
| Duplicate IDs | **0** |
| With `source_game_id` (`game_pk`) | **5 178** |
| Without `source_game_id` | **0** |
| Unique `game_pk` | **5 178** |
| Duplicate `game_pk` | **0** |
| One `game_pk` → many internals | **0** |
| Season / league | 2025-2026 / MLB |
| Date range | 2025-03-18 … 2026-09-04 |
| `scheduled_start` present | **0** (not invented) |
| Identity status | **VALID 5 178**; all other statuses 0 |
| Catalog overlap **before** append | games-only **5 178**; both 0 |
| Catalog overlap **after** append | games∩identity **5 178**; games-only 0; source mismatch 0 |

Every MLB `internal_game_id` still ends with `_{game_pk}`. Existing ingest values were copied, not renamed.

---

## 6. Duplicate / conflict / ambiguous / invalid findings

On today’s NBA / NCAAB / MLB `games.csv` rows:

| Class | NBA | NCAAB | MLB |
| --- | --- | --- | --- |
| DUPLICATE | 0 | 0 | 0 |
| CONFLICT | 0 | 0 | 0 |
| AMBIGUOUS | 0 | 0 | 0 |
| INVALID | 0 | 0 | 0 |
| MISSING canonical ID | 0 | 0 | 0 |

No silent repairs. Detector tests cover each class with synthetic rows.

WNBA catalog rows (**612**) were left untouched (out of Phase 2 sport scope; preserved so the single artifact is not destroyed).

---

## 7. Artifact update

`extend_identity_artifact` appended **5 178** MLB rows copied from `games.csv`.

| Check | Result |
| --- | --- |
| NBA / NCAAB / WNBA IDs changed | **No** (7 254/7 254 both-sides match) |
| NBA / NCAAB / WNBA `source_game_id` changed | **No** |
| MLB IDs minted | **No** — copied |
| Conflicts during append | **0** |
| Artifact rows after | **12 432** (NBA 1 362 + NCAAB 5 280 + MLB 5 178 + WNBA 612) |
| `mapping_status` after | MAPPED **7 989** (= prior 2 811 + 5 178 MLB with `game_pk`); UNMAPPED **4 443** unchanged |
| File size | 2 962 790 bytes |
| `game_identity_v2.csv` / parallel store | **Not created** |
| `game_market_crosswalk.parquet` | **Absent** |

New MLB rows only: `created_at` / `updated_at` = materialize time. Existing basketball timestamps were not rewritten.

---

## 8. Query-time identity rule

**Today (unchanged):** Confirm & Run groups by ticker and filters PBP/games by the `internal_game_id` **already stamped on the row**. Identity is a warehouse/source fact. Execute does not rediscover it.

**Future requirement (not implemented):** query execution must **consume** `internal_game_id` from this catalog / stamped rows. It must not rebuild identity from ticker, team names, date, filename, row order, or cache. `execute.py` was not modified. `get_research_context` still does not exist.

---

## 9. Files changed

| Path | Change |
| --- | --- |
| `ROLLER/roller/warehouse/identity.py` | **New.** Parse / classify / resolve / audit / preserve / extend |
| `ROLLER/roller/warehouse/entities.py` | Optional `scheduled_at`, `source_system`, `identity_rule_version` on `Game` |
| `ROLLER/roller/warehouse/__init__.py` | Export `IDENTITY_RULE_VERSION` |
| `ROLLER/roller/canonical/identity_build.py` | Preserve existing IDs; do not remint or drop MLB |
| `ROLLER/meta/game_identity.csv` | Appended 5 178 MLB rows; basketball rows unchanged |
| `ROLLER/tests/test_warehouse_identity.py` | **New.** Phase 2 tests |
| `ROLLER/tests/test_warehouse_entities.py` | Execute must not import `roller.warehouse.identity` |
| `research/warehouse_refactor/PHASE_2_IDENTITY.md` | This report |

Not modified: `execute.py`, compiler, `admin.load_dataset`, Confirm & Run, frontend, Results, `first80.py`, SuperASI, STAX, goldens, ingest runners, tennis.

---

## 10. Tests run

Command:

```text
cd ROLLER && .venv/bin/python -m pytest \
  tests/test_warehouse_identity.py \
  tests/test_warehouse_entities.py \
  tests/test_identity.py \
  tests/test_warehouse_contract.py -q
```

**38 passed.** Phase 2 identity tests:

1. `test_existing_valid_id_formats_are_preserved`
2. `test_identity_construction_is_deterministic`
3. `test_unique_source_id_resolves_to_one_canonical_id`
4. `test_duplicate_canonical_id_is_detected`
5. `test_conflicting_source_ids_fail_closed`
6. `test_missing_source_and_missing_id_fail_closed`
7. `test_ambiguous_rematch_without_distinguishing_keys`
8. `test_malformed_and_impossible_identity_are_invalid`
9. `test_game_entity_keeps_source_id_distinct_from_internal_id`
10. `test_preserve_existing_ids_does_not_remint`
11. `test_ticker_is_not_an_identity_key`
12. `test_ncaab_and_mlb_identity_rules`
13. `test_extend_identity_artifact_copies_mlb_without_reminting`
14. `test_identity_build_preserves_existing_nba_id`
15. `test_live_phase2_identity_invariants`

Also re-ran existing identity / Phase 1 entity / warehouse contract tests (no golden edits).

Historical locks (Increment 2, FIRST80, MLB FT75/TE, MLB 1661 verify-only) were **not** opened or rewritten.

---

## 11. Acceptance

| Criterion | Result |
| --- | --- |
| NBA canonical identity measured and validated | **Yes** — 1 362/1 362 VALID |
| NCAAB canonical identity measured and validated | **Yes** — 5 280/5 280 VALID |
| MLB canonical identity measured and validated | **Yes** — 5 178/5 178 VALID, `game_pk` preserved |
| Existing valid `internal_game_id` values preserved | **Yes** |
| Source-native game IDs retained | **Yes** |
| Identity construction deterministic | **Yes** |
| Duplicate identities detected | **Yes** (tests; 0 on disk) |
| Conflicting identities detected | **Yes** (tests; 0 on disk) |
| Ambiguous identities fail closed | **Yes** |
| Invalid identities fail closed | **Yes** |
| No identity guessed from a Kalshi ticker | **Yes** |
| No `GameMarketLink` created | **Yes** |
| No market / PBP / settlement / orderbook / ingest work | **Yes** |
| No CSV → Parquet cutover | **Yes** |
| No compiler / execute / Confirm & Run / frontend / Results changes | **Yes** |
| No performance work / tennis / W9 | **Yes** |
| Historical locks untouched | **Yes** |
| Existing identity formats compatible | **Yes** |
| Phase 2 tests pass | **Yes — 38 passed** |
| Phase 3 started | **No** |

---

## 12. Stop

Phase 2 is complete. Phase 3 (persistent `GameMarketLink`) was **not** started.
