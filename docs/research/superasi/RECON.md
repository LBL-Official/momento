# SuperASI Phase 0 — repository recon

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
LEDGER PRICE ≠ PROVEN FILL
FEE MODEL = ESTIMATED
NO SUPERASI CODE IN THIS PHASE
```

Audit only. No SuperASI package, API, or frontend was added in this phase.

## 1. What SuperASI is consuming

ROLLER is a measurement terminal (`frontend/roller-terminal` on :5179, API `ROLLER/scripts/terminal_api.py` on :8791).

Two execute paths:

| Path | Function | Full trades in HTTP body? |
|---|---|---|
| Frozen FIRST80 | `execute_research_object` | **No.** `population.count` is full; `population.rows` capped at 200 |
| Generic query | `execute_question` | **Yes.** `population.trades` is the full list; `rows` still preview-capped at 200 |

There is **no last-execute memory store** on the terminal API. Optional generic result cache (`ROLLER_QUERY_RESULT_CACHE`) is off by default and must not be treated as SuperASI authority.

Client Results snapshots are **provenance only**. SuperASI import must re-obtain the population server-side.

## 2. Isolation check (do not touch)

| Path | Status |
|---|---|
| `ROLLER/roller/research/first80.py` | Exists. Frozen FIRST80 loader. **Do not modify.** |
| `ROLLER/roller/research_query/` | Generic compiler/execute/indexes. **Do not modify.** |
| `ROLLER/roller/timeutil.py` | Exists. **Do not modify.** |
| `POPULATION_ROWS_SERIALIZE_CAP = 200` | `ROLLER/roller/dashboard_adapter/bindings.py`. **Do not lift for Results.** |
| FIRST01 / Risk / Execution / W9 / `crates/research-engine` | Out of SuperASI scope. |
| `apps/terminal-efficiency/` | Separate XIB/MCD pipeline. **Do not modify.** |
| `research/lebronner/` | FIRST75 −0.37¢ archive. Additive pointers only. |

Allowed SuperASI home: `ROLLER/roller/superasi/` (new), `ROLLER/scripts/terminal_api.py` (add routes only), `frontend/roller-terminal/src/superasi/` (new), `ResultsAnswer.tsx` (button only).

## 3. Frozen FIRST80_Q3

`ROLLER/tests/test_research_executor_phase4.py` locks **N = 290** and `rows_truncated is True`.

Frozen row fields (warehouse join), not a SuperASI trade yet:

- `ticker`, `event_ticker`, `game_date`, `team`, `first_80_timestamp`, `entry_price_e4`
- `expiration_result_yes`, `dataset_split`, `entry_quarter_bucket`
- `T40`, `W`, `barrier_join`, `alignment_confidence`

Missing vs SuperASI minimum: `entry_ask`, `entry_spread`, `entry_tradable`, `mae_cents`, `mfe_cents`, `holding_seconds`, `exit_ts` as generic names, `path_true`/`win_exit`/`loss_exit` (T40/W are the frozen equivalents).

**Decision:** map frozen fields on import; mark unmapped execution-quality fields `UNAVAILABLE`. Do not invent ask/spread.

## 4. Generic query rows

`ROLLER/roller/research_query/execute.py` already emits `entry_close`, `exit_close`, `path_true`, `win_exit`, `loss_exit`, `terminal_yes`, `mae_cents`, `mfe_cents`, `holding_seconds`, `price_basis`. Ask/spread are not guaranteed.

**Decision:** SuperASI import copies these; missing ask/spread = `UNAVAILABLE`. Do not edit `execute.py` to add fields.

## 5. How import can get N=290 without uncapping Results

| FILE | EXPECTED | ACTUAL | IMPACT | DECISION |
|---|---|---|---|---|
| `research_executor.py` HTTP return | SuperASI can read 290 rows from the last Results payload | `population.rows` length 200; no server-side last-result cache | Client snapshot cannot be N | SuperASI importer **re-executes read-only** via existing `execute_research_object` / `execute_question`, then reads the **in-memory population before serialize**, or reloads the same warehouse bindings from SuperASI code. **Do not change `POPULATION_ROWS_SERIALIZE_CAP`.** |
| `result_cache.py` | Persistent last execute | Cache disabled by default; frozen path never cached | Cannot rely on cache | Re-execute or bind warehouse in `ROLLER/roller/superasi/` |

Preferred: SuperASI-side loader that calls public `execute_*` internals / dashboard_adapter warehouse paths. If a tiny read-only helper is required on `research_executor.py` (not `first80.py`, not `research_query/`), it must only expose the already-built full list and must not change Results serialization.

## 6. Asked-six locked objects

Existing reconstruct (do not rescan):

- `apps/nba-data/scripts/superasi.py` — integers 1182 / 883 / 108 / 0 / 191
- `research/first80_asked_six_chatgpt_export/first80_asked_six.csv` — 1182 trades
- `research/first80_asked_six_t40_surround_candles/t40_surround_pm5.csv`
- `research/first80_asked_six_80_40_stop_loss/stop_loss.csv`

Four-cell: **883 / 108 / 0 / 191**. Terminal winners = **991**. S = **883/1182**. Do not use 990.

EV locks: ledger **5700/1182**, T40-close **4058/1182**, planning L **14705/299**.

## 7. Path-window row-count discrepancy

| FILE | EXPECTED (spec) | ACTUAL (locked CSV) | IMPACT | DECISION |
|---|---|---|---|---|
| `t40_surround_pm5.csv` | 299 × 11 = **3289** long rows | **3285** data rows (`summary.json` `n_candle_rows`) | Offsets +4 and +5 have **297** candles each (2 path-loss trades lack those minutes) | **Do not fabricate 4 candles.** Long-format package may have UNAVAILABLE rows for missing minutes **or** omit those minutes with status UNAVAILABLE. Offset-0 sum **10318**, offset−1 sum **14663**, pre-T40 38–40 closes **1** remain the regression locks. Fail closed if those sums do not match. |

## 8. Fees

`apps/nba-data/scripts/capture_program_v1/fee_models.py` — `PublishedScheduleEstimate`, maker 0.0175, taker 0.07, settlement 0, status ESTIMATED.

Scenarios from `docs/research/FIRST80_REALISTIC_EXIT_FEE_AUDIT_V1.md`:

| Scenario | Entry @80 | Exit | Hedge (not SuperASI live) |
|---|---|---|---|
| CURRENT | $0 | taker 0.07 | $0 |
| MODERATE | maker 0.0175 | taker 0.07 | maker 0.0175 |
| CONSERVATIVE | taker 0.07 | taker 0.07 | maker 0.0175 |

Do not invent another schedule. Production `KalshiFeeModel` is UNRESOLVED / unused.

## 9. Terminal UI (visual contract)

- Routes: `frontend/roller-terminal/src/v2/navigation.ts`
- Results button bar: `ResultsAnswer.tsx` (Save results / Download / Print)
- Scenario cards: `ScenarioPanel.tsx` + `scenarioPresets.ts`
- Drawer: `v2/components/DetailDrawer.tsx`
- Styles: `src/styles.css` — Geist / graphite
- Header wordmark: `AppHeader.tsx` (“ROLLER / Research Terminal”)
- ROLLER library: **localStorage** (`roller.v2.research_library.v1`) — SuperASI must **not** use this

No SuperASI routes or “Move to SuperASI” exist yet.

## 10. ROLLER economics (do not overwrite)

`ROLLER/roller/results_math/ev_contract.py` defines three objects: observed path EV, book-price EV, settlement EV. SuperASI copies them as GROSS / PRE-SUPERASI.

Generic `price_basis` can be last-trade. SuperASI must then set stop-path and fees to `DATA_REQUIRED`.

## 11. Existing SuperASI research docs

`research/superasi/` and `docs/research/superasi/` already hold the integer reconstruct (README, EV_DECOMPOSITION, REPORT, summary.json). Status was SPEC_ONLY. V1 dashboard/API will extend these docs; it must not change the locked integers.

`apps/nba-data/scripts/superasi.py` is a reconstruct script, not the ROLLER package. Keep it. New code lives under `ROLLER/roller/superasi/`.

## 12. Tests / scripts to preserve

- `ROLLER/tests/test_research_executor_phase4.py` (N=290, truncated preview)
- `ROLLER/tests/test_research_query_engine.py` and harden/increment2
- `ROLLER/scripts/validate_roller.py`
- `ROLLER/scripts/leakage_audit.py`

Phase 1 records their baseline. SuperASI tests are new files under `ROLLER/tests/test_superasi_*.py`.

## 13. Phase 0 conclusions

1. SuperASI is a new isolated consumer. One Vite app. Disk library.
2. Import cannot trust the UI 200-row preview. Re-execute or reload warehouse from SuperASI code.
3. Asked-six seed is reconstruct-from-CSV/integers, not a tape rescan.
4. Window long-count is **3285 observed**, not 3289. Missing +4/+5 minutes stay UNAVAILABLE.
5. No forbidden files need to change for V1 if SuperASI owns the full-population export.
6. Ready for Phase 1 baseline, then package schema.

**LIVE EXECUTION = FALSE. FIRST01 UNCHANGED. FIRST80 UNCHANGED. W9 NOT STARTED.**

## 14. Phase 1 baseline (2026-09-10)

| Command | Result |
|---|---|
| `scripts/validate_roller.py` | PASS (integrity, v4b, v4c) |
| `scripts/leakage_audit.py` | PASS, n_errors=0 |
| `pytest -q` (full ROLLER) | **467 passed, 1 failed, 1 skipped** in 412s |
| Locked subset (query engine/harden/increment2 + executor phase4 + population phase6) | recorded separately |

### Pre-existing failure (do not silently fix)

| FILE | EXPECTED | ACTUAL | IMPACT | DECISION |
|---|---|---|---|---|
| `ROLLER/tests/test_research_query_indexes.py::test_indexed_execute_matches_scan` | pass | FAIL at Phase 1 baseline, before SuperASI code | Upstream index/scan mismatch | **Preserve.** SuperASI does not modify `research_query/`. Do not treat this as a SuperASI bug. Re-check at Phase 16 that SuperASI did not change this file. |

SuperASI V1 proceeds. Phase 16 must not require this upstream test to turn green unless it was already green.
