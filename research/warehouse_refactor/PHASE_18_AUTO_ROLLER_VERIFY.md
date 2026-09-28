# Phase 18 — Auto Roller warehouse verify

Measured: **2026-09-13**. Read-only inspection of the published NBA
Phase 8 parquet warehouse. Phase 17 ingest was **not** rewritten.
The live tree was **not** written.

Module: `ROLLER/roller/warehouse/auto_verify.py`.

Raw JSON: `research/warehouse_refactor/phase15_measurements/p18_live_verify.json`.

---

## What this phase is

```text
PUBLISHED CANONICAL PARQUET
        ↓
run_nba_warehouse_verify  (read-only)
        ↓
identity / observations / settlement / PBP
        ↓
capability matrix
        ↓
compile_research + run_conditional_backtest × 2
```

This is verification, not another ingest. `auto_ingest.run_nba_warehouse_ingest`
is unchanged. Confirm & Run (`execute.py`, `compiler.py`, `admin.load_dataset`,
`planner.py`, `official_settlement.py`) was not edited.

---

## Warehouse identity

| Field | Measured |
| --- | --- |
| warehouse version (`manifest.updated_at`) | `2026-09-13T06:28:48Z` |
| manifest SHA-256 | `b9f02c7b88bd1680729d6552ed3cafeb94fe36624c8f205ebb34ab5981d9f231` |
| source / ingest fingerprint | **ABSENT** (`ingest_run.json` is not on the live tree; this warehouse was published by Phase 8, not Phase 17 ingest) |
| ingest_record_present | `false` |
| sport / season | NBA / 2025-2026 |
| observation_basis | `TRADABLE_YES_BID` |
| resolution | `1_MINUTE_CANDLE` |
| pit_field | `available_at` |

---

## Counts (parquet, not invented)

| Dataset | Count |
| --- | ---: |
| identity / games | 1362 |
| markets | 2724 |
| GameMarketLink | 2724 linked, 0 unlinked, 0 ambiguous |
| observations | 6,165,183 |
| settlements | 2724 |
| PBP events | 780,137 |

Observation months:

```text
2025-10  541322
2025-11 1131497
2025-12  923736
2026-01 1065955
2026-02  669455
2026-03  831856
2026-04  607878
2026-05  323042
2026-06   70442
```

Settlement authority: `kalshi_rest` (Suite).

```text
YES      1359
NO       1359
INVALID     6
MISSING     0
```

INVALID remains INVALID. YES remains YES. NO remains NO. No settlement
inferred from score, PBP, or price.

---

## Observation verification

```text
observation_basis = TRADABLE_YES_BID
resolution        = 1_MINUTE_CANDLE
pit_field         = available_at
```

- `available_at` present, minute-aligned, no blank timestamps
- sorted by `internal_game_id`, `market_id`, `available_at`
- no other `observations/basis=*` partition
- no forward-fill / interpolation / fill columns
- no invented sub-minute stamps
- silent `(market_id, available_at)` duplicates: **0**
- publisher-flagged identical source collisions (`duplicate_key=1`): **6 rows / 3 pairs**

The 6 flagged rows are exact copies already marked by the Phase 8
publisher (SAS/POR 2026-04-22T21:34:00Z × 2 markets, OKC 2026-05-18T17:11:00Z).
They are reported, not rewritten. Silent (unflagged) duplicates fail
closed. Injected fixture duplicates fail closed.

---

## PBP verification

```text
pbp_pit_aligned_to_candles = false
```

Identity links resolve. Event order is deterministic
(`internal_game_id`, `event_number`). No persisted candle-join columns
(`yes_bid_*`, `candle_available_at`, …). PBP `event_timestamp` is not
used as a market observation `available_at`.

---

## Capability matrix (truthful)

| Capability | State |
| --- | --- |
| GAME | READY |
| MARKET | READY |
| GAME_MARKET_LINK | READY |
| TRADABLE_YES_BID_1M | READY |
| CANDLE_PIT | READY |
| SETTLEMENT | READY |
| PBP | READY |
| HISTORICAL_L2 | DATA_REQUIRED |
| HISTORICAL_TICK | DATA_REQUIRED |
| ORDERBOOK | DATA_REQUIRED |
| TICK | DATA_REQUIRED |
| PBP_MARKET_PIT_ALIGNMENT | OPERATION_REQUIRED |

Unavailable data is not converted to READY because a candle fallback
exists. `compile_research` / `run_conditional_backtest` on historical L2
returns `DATA_REQUIRED` with population 0. PBP↔candle PIT alignment
returns `OPERATION_REQUIRED`.

---

## Research reproducibility

Same warehouse-backed question, twice (2025-10-10, CROSS 63¢,
REACH 87 / REACH 41, HOLD_TO_SETTLEMENT):

```text
plan_hash            d8c10b912b20a45b0f9909cb759f2dee8a23298cd55df21ab94feb9e2432a35a
result_hash          3ff90cf3b331db7909790f3180d5b54e1d3df6027d8dcfe277c3928397d02382
population           7
classification       WIN=1 LOSS=6
warehouse_version    2026-09-13T06:28:48Z
observation_basis    TRADABLE_YES_BID
pit_field            available_at
compiler_version     1.0.0
status               READY
runs                 2
row identities       identical
current_time         not used
```

A third `run_conditional_backtest` in the test matched the same hashes.

---

## Verification results

| Check | Result |
| --- | --- |
| layout | PASS |
| manifest | PASS |
| identity | PASS |
| observations | PASS |
| settlements | PASS |
| pbp | PASS |
| capabilities | PASS |
| reproducibility | PASS |
| fingerprints | PASS |
| overall | **PASS** |

Live `manifest.json` mtime was unchanged after verify.

---

## Tests

`ROLLER/tests/test_warehouse_auto_verify.py` — **10 passed, 0 failed**.

| Test | Coverage |
| --- | --- |
| `test_identity_verification` | canonical IDs, GameMarketLink, no ambiguous maps |
| `test_observation_semantics` | basis / PIT / sort / silent vs flagged dups |
| `test_settlement_semantics` | Suite / kalshi_rest, INVALID ≠ NO |
| `test_pbp_semantics` | `pbp_pit_aligned_to_candles=false` |
| `test_capability_matrix` | READY / DATA_REQUIRED / OPERATION_REQUIRED lock |
| `test_duplicate_detection` | fixture ingest + injected game/obs dups fail |
| `test_manifest_fingerprint_consistency` | SHA-256 + counts match parquet |
| `test_deterministic_research_result` | plan/result hash + row identities |
| `test_fail_closed_unsupported_capability` | L2/tick DATA_REQUIRED; PIT OPERATION_REQUIRED |
| `test_verify_does_not_import_confirm_and_run_or_first80` | isolation |

Frozen Phase 0–17 files re-run with Phase 18:

```text
Phase 0–8:    85
Phase 9–11:   26
Phase 12–14:  43
Frozen 0–14: 154
Phase 15:      6
Phase 16:      5
Phase 17:     10
Frozen 0–17: 175
Phase 18:     10
TOTAL:       185 passed
Failures:      0
```

---

Phase 18 complete. Next authorized phase is **19**. Do not start it from
this report.
