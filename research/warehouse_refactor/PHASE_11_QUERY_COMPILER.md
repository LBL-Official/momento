# Phase 11 — Isolated NBA query compiler

Measured: **2026-09-13**. Plan only. Backtest not executed.

```text
ResearchQuestion
      ↓
Normalization
      ↓
Validation
      ↓
Phase 9 catalog.resolve
      ↓
ResearchPlan
```

Module: `ROLLER/roller/warehouse/research_compiler.py`.

Does not import or edit Confirm & Run `compiler.py` / `execute.py`.
`ResearchPlan` is a new frozen type (not `CompileResult`). Confirm & Run
`TerminalOutcome` YES/NO/BOTH is unchanged. Warehouse-local terminal is
`HOLD_TO_SETTLEMENT` | `NO_TERMINAL_RESULT`.

`ZERO_RESULTS` is not a compiler status.

---

## 1. Vocabulary (compile, do not execute)

- Universe: NBA / `2025-2026` / date range. Invalid league or inverted range
  fail closed (`DATA_REQUIRED`), not guessed.
- Observation: `TRADABLE_YES_BID` + `1_MINUTE_CANDLE` + PIT `available_at`
  → READY. `TICK` / `ORDERBOOK` / `L2` / `TRADE_TAPE` → `DATA_REQUIRED`
  (no candle remap).
- Entry: CROSS, TOUCH→`FIRST_TOUCH` unless ordinal set, BREAK, REVERSION,
  BOUNCE, RECOVERY, ABOVE, BELOW, MAXIMUM_TOUCH, MINIMUM_TOUCH. AND / order /
  price / range / period / clock preserved. No row scan.
- Exit: HOLD, REACH, DROP, RISE, RECOVER, CLOCK as independent WIN/LOSS
  predicates.

Compiler version: `1.0.0`. Same question + warehouse/catalog version → same
`to_dict` / `plan_hash`. No `current_time`.

---

## 2. Measured examples (not FIRST80)

### READY

```text
NBA 2025-2026 · TRADABLE_YES_BID · 1-minute · PIT available_at
Q2 CROSS 63¢ · WIN REACH 87¢ · LOSS REACH 41¢ · HOLD_TO_SETTLEMENT
```

```text
status              READY
observation_basis   TRADABLE_YES_BID
resolution          1_MINUTE_CANDLE
pit_requirement     available_at
entries             CROSS 6300 e4 period=Q2
exits               win REACH 8700 ; loss REACH 4100
terminal            HOLD_TO_SETTLEMENT
plan_hash           4547787d8dfdb8c40717d7321e399179e868a67f0b069cadabc3f7964f9ffa67
```

Catalog for the same candle/PIT/settlement/PBP requirements: READY.
ResearchContext for 2025-10-10: READY, canonical parquet. Backtest: not run.

### DATA_REQUIRED

```text
NBA · market_data=l2 (or tick / orderbook / trade_tape)
```

```text
status         DATA_REQUIRED
missing_data   HISTORICAL_L2 | TICK | ORDERBOOK
context        not constructed
```

### OPERATION_REQUIRED

```text
requested_dimensions = PBP_MARKET_PIT_ALIGNMENT
```

```text
status                OPERATION_REQUIRED
missing_operations    PBP_MARKET_PIT_ALIGNMENT
```

---

## 3. Isolation

No FIRST80 / W9 primitive. No fills, EV, WIN/LOSS scan, settlement inference,
CSV, or PBP↔candle join. `test_live_execute_paths_do_not_import_entities`
forbids `roller.warehouse.research_compiler`.

Phase 12 (conditional backtest) is not started.
