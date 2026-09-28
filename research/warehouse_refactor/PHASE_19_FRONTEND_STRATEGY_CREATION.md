# Phase 19 — Frontend capability + strategy creation

Measured: **2026-09-13**. Existing ROLLER terminal only. Confirm & Run
(`execute.py`, `compiler.py`, `admin.load_dataset`, `planner.py`,
`official_settlement.py`) was not edited.

---

## What this phase is

```text
Existing ROLLER frontend chips
        ↓
researchQuestionFromDraft  (serialization only)
        ↓
POST /warehouse-research/compile | execute
        ↓
frontend_contract → compile_research → parquet warehouse
        ↓
Capability READY | DATA_REQUIRED | OPERATION_REQUIRED | ZERO_RESULTS
        ↓
Warehouse Results (backend contract)
```

The UI is a ResearchQuestion constructor. It does not implement CROSS /
BREAK / PIT / settlement / path math. It does not become a second engine.

---

## Frontend strategy construction

Constructor: `frontend/roller-terminal/src/v2/warehouse/researchQuestionFromDraft.ts`.

Quick Start stores `sport=basketball` and `league=NBA`. The constructor
maps that chip pair onto warehouse identity `sports=("NBA",), leagues=("NBA",)`.
NCAAB-only basketball is not rewritten to NBA. Season chip `2025-26` maps
to `2025-2026` in this layer only (Phase 11 `research_compiler.py` is
untouched).

Entry families exposed through the existing chips: CROSS, TOUCH,
FIRST_TOUCH … NTH_TOUCH, BREAK, REVERSION, BOUNCE, RECOVERY, ABOVE, BELOW,
MAXIMUM_TOUCH, MINIMUM_TOUCH.

Independent WIN / LOSS exits: REACH, DROP_TO, RISE_TO, RECOVER, plus hold
chips. Terminal default when no hold chip is selected:
`HOLD_TO_SETTLEMENT`.

No `FIRST80` / `FIRST75` / `FIRST01` / `T40` / `DRE` / `Lebronner` /
`PADE` tokens in the constructor.

---

## Backend contract

Module: `ROLLER/roller/warehouse/frontend_contract.py`.

API (existing `scripts/terminal_api.py` only):

```text
POST /warehouse-research/compile
POST /warehouse-research/execute
```

Body is `{ question }` or `{ draft }`. `source = warehouse_research`.
Does not import Confirm & Run execute / compiler / admin / planner.

Confirm & Run `/research-query/*` remains the CSV legacy path.
`frozen_reference` (FIRST80 lock) stays on that path. Warehouse
`DATA_REQUIRED` / `OPERATION_REQUIRED` do not fall back to CSV.

---

## Capability behavior

| Request | Status | Meaning |
| --- | --- | --- |
| NBA candles CROSS + WIN/LOSS exits | `READY` | Backend can execute against canonical parquet |
| `historical_l2` | `DATA_REQUIRED` | No candle approximation |
| `historical_tick` | `DATA_REQUIRED` | No candle approximation |
| `PBP_MARKET_PIT_ALIGNMENT` | `OPERATION_REQUIRED` | No synthetic PBP↔candle join |
| Valid Q2 CROSS 63¢ on 2025-10-10 | `ZERO_RESULTS` | Engine ran, population = 0. Not missing data. |

UI Confirm panel (`WarehouseConfirmPanel`) shows the backend status before
Run. Run is gated on warehouse `READY`.

---

## Strategy serialization

Draft → `ResearchQuestion` → `to_dict` / `from_dict` roundtrip is identical.

Browser construction (measured 2026-09-13, NBA 2025–26, dates
2025-10-10→2025-10-10, Kalshi candles):

```text
Entry:  CROSS 65¢
WIN:    REACH 85¢
LOSS:   REACH 40¢
Terminal: HOLD_TO_SETTLEMENT
Observation: TRADABLE_YES_BID · 1_MINUTE_CANDLE · PIT available_at
Capability: READY
```

Displayed Confirm plan prefix: `85740c8e04c98837`.

---

## Result rendering

`WarehouseResults` consumes `results_contract` from the backend execute.
Browser run of the CROSS 65¢ / REACH 85 / REACH 40 question:

| Field | Measured |
| --- | --- |
| status | `READY` |
| population | 7 |
| W / L | 1 / 6 |
| win rate | 14.3% (1/7) |
| loss rate | 85.7% (6/7) |
| R:R | 0.80 : 1 (reward 20¢ / risk 25¢) |
| EV | −18.57¢ |
| classification | WIN=1 LOSS=6 |
| label | observed candle-path research result |
| not | live trading, fill, maker fill, slippage, PnL |

`POST /warehouse-research/execute` duration on this run: **510 ms**
(API log, not invented).

Warehouse version on Results: `2026-09-13T06:28:48Z`.
compiler / identity / catalog: `1.0.0`.

---

## Coverage behavior

| Field | Measured |
| --- | ---: |
| nominal games | 1362 |
| nominal markets | 2724 |
| executed population | 7 |
| excluded `no_event` | 3 |
| missing_data | none |
| unsupported_operations | none |

Exclusions are listed. Rows are not silently dropped.

---

## Row-level audit

Results table columns (no generic `price` field):

```text
internal_game_id
market_id
entry_timestamp
entry_value
entry_operation
entry_period
entry_clock
win_exit_timestamp
win_exit_value
win_exit_operation
loss_exit_timestamp
loss_exit_value
loss_exit_operation
classification
settlement_status
settlement_value
observation_basis
observation_resolution
pit_field
```

Reproducibility block retains `plan_hash`, `result_hash`,
`warehouse_version`, `observation_basis`, `resolution`, `pit_field`,
`compiler_version`, `catalog_version`, `execution_version`, `engine_id`.
No `current_time`.

---

## Previously unseen generic strategy (tests)

BREAK 71¢ / REACH 90 / DROP_TO 35 compiled and executed through
`frontend_contract` with no FIRST80 special case. Status was `READY` or
`ZERO_RESULTS` from the generic compiler.

---

## Test count

Measured with:

```text
ROLLER/.venv/bin/python -m pytest tests/test_warehouse_frontend_strategy.py -q
```

```text
Phase 19 pytest: 13 passed
Failures:        0
```

Additional (not in the pytest total):

```text
node --test scripts/warehouse-research-question-unit.mjs  →  4 passed
npx tsc --noEmit                                          →  clean
```

Coverage in the pytest file:

```text
strategy construction
UI basketball+NBA universe mapping
ResearchQuestion serialization
invalid strategy validation
READY / DATA_REQUIRED / OPERATION_REQUIRED / ZERO_RESULTS
backend submission + result rendering
row-level audit + coverage
previously unseen BREAK 71 strategy
no FIRST80 / no Confirm & Run imports
```

---

## Isolation

`frontend_contract` is on the Confirm & Run forbidden-import lists
(Phase 0–17 files). Phase 19 does not call `execute.py` or
`load_dataset`.

---

## Gate

```text
PHASE 19: COMPLETE
Frontend → ResearchQuestion: PASS
Capability resolution: PASS
Warehouse Results: PASS
Confirm & Run CSV path: unchanged
```
