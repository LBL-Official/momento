# Phase 20 — Full NBA research desk

Measured: **2026-09-13**. Phases 0–19 remain semantically frozen.
Confirm & Run CSV path was not edited.

---

## Architecture validation

```text
Existing ROLLER frontend
        ↓
ResearchQuestion          (researchQuestionFromDraft / frontend_contract)
        ↓
Capability resolution     (compile_research)
        ↓
ResearchContext           (get_research_context → canonical parquet)
        ↓
ResearchPlan
        ↓
ConditionalBacktest
        ├── reference
        └── optimized
        ↓
Reference ≡ Optimized     (difference_count = 0)
        ↓
Results                   (results_contract)
```

The frontend is a constructor. The backend is the authority for
capability, PIT, entry/path/settlement, classification, and hashes.

---

## Frontend → ResearchQuestion

Acceptance strategy (constructed through the existing Quick Start chips,
then replayed via the same draft contract):

```text
NBA 2025–2026
sport chip: basketball → mapped to sports=("NBA",)
league: NBA
dates: 2025-10-10 → 2025-10-10
market data: candles
observation: TRADABLE_YES_BID
resolution: 1_MINUTE_CANDLE
PIT: available_at

Entry:  CROSS 65¢
WIN:    REACH 85¢
LOSS:   REACH 40¢
Terminal: HOLD_TO_SETTLEMENT
```

Not FIRST80 / FIRST75 / FIRST01. Not a frozen lock primitive.

Browser Confirm showed warehouse `READY` and
`TRADABLE_YES_BID · 1_MINUTE_CANDLE · PIT available_at` before Run.

---

## Capability resolution

| Request | Status |
| --- | --- |
| Acceptance CROSS 65 / REACH 85 / REACH 40 | `READY` |
| Historical L2 | `DATA_REQUIRED` |
| Historical tick | `DATA_REQUIRED` |
| PBP↔candle PIT alignment | `OPERATION_REQUIRED` |
| Valid Q2 CROSS 63¢ on 2025-10-10 | `ZERO_RESULTS` (population 0; not missing data) |

---

## ResearchContext

`get_research_context` on the acceptance question:

```text
status: READY
loaded observations on 2025-10-10 slice: 5125
basis: TRADABLE_YES_BID only
```

---

## ResearchPlan

```text
status:             READY
plan_hash:          111716244afa355ef24cb69f6d2e1b5d0ca6a9da29a0f879905fe2fdc8f26830
compiler_version:   1.0.0
warehouse_version:  2026-09-13T06:28:48Z
identity_version:   1.0.0
catalog_version:    1.0.0
observation_basis:  TRADABLE_YES_BID
resolution:         1_MINUTE_CANDLE
pit_field:          available_at
```

The live Confirm panel used generated chip ids and displayed plan prefix
`85740c8e04c98837`. Same chips, same measured population (7 / 1 / 6).
The dedicated acceptance test uses stable draft ids `e1` / `win` / `loss`.

---

## Reference execution / Optimized execution

```text
engine_id reference  result_hash 2611ff547f360c6f67c351c5019d5de98f9f0e9b6474e7b65c34db1eabe53953
engine_id optimized  result_hash 2611ff547f360c6f67c351c5019d5de98f9f0e9b6474e7b65c34db1eabe53953
execution_version   1.0.0
```

---

## Reference ≡ Optimized

```text
difference_count = 0
```

Row-level compare (identity, entry timestamp/value/operation, WIN exit,
LOSS exit, classification, settlement fields): no differences. No
tolerance. Hashes identical.

---

## Result population and statistics

Observed candle-path research result. **Not** live trading. **Not** a fill.

| Field | Measured |
| --- | ---: |
| Population N | 7 |
| Wins W | 1 |
| Losses L | 6 |
| Win rate p̂ | 1/7 = 0.142857… (UI 14.3%) |
| Loss rate | 6/7 = 0.857142… (UI 85.7%) |
| Reward | 20¢ (85 − 65) |
| Risk | 25¢ (65 − 40) |
| R:R | 0.80 : 1 |
| EV | −18.57¢ (`ev_e4` = −1857.14) |

95% confidence intervals are **not** part of the approved implementation
and were not invented.

Classification on this run: WIN=1, LOSS=6. No
`MISSING_SETTLEMENT` / `INVALID_SETTLEMENT` / `SAME_BAR_TIE` in this
population (those classes are proven on fixtures).

---

## Coverage / exclusions

| Field | Measured |
| --- | ---: |
| nominal games | 1362 |
| nominal markets | 2724 |
| executed population | 7 |
| excluded `no_event` | 3 |
| missing_data | none |
| unsupported_operations | none |

---

## Row-level audit

Results expose per-row:

```text
internal_game_id, market_id, entry_timestamp, entry_value, entry_operation,
entry_period, entry_clock, win_exit_*, loss_exit_*, classification,
settlement_status, settlement_value, observation_basis,
observation_resolution, pit_field
```

No generic `price` field.

---

## Reproducibility metadata

```text
ResearchQuestion          retained on results_contract
plan_hash                 111716244afa355ef24cb69f6d2e1b5d0ca6a9da29a0f879905fe2fdc8f26830
result_hash               2611ff547f360c6f67c351c5019d5de98f9f0e9b6474e7b65c34db1eabe53953
compiler_version          1.0.0
warehouse_version         2026-09-13T06:28:48Z
identity_version          1.0.0
catalog_version           1.0.0
observation_basis         TRADABLE_YES_BID
resolution                1_MINUTE_CANDLE
pit_field                 available_at
entry                     CROSS 65¢
WIN                       REACH 85¢
LOSS                      REACH 40¢
terminal                  HOLD_TO_SETTLEMENT
execution_version         1.0.0
engine_id                 optimized
```

No `current_time`. No random seed.

---

## Adversarial capability tests

| Case | Result |
| --- | --- |
| Historical L2 | `DATA_REQUIRED` — not ZERO_RESULTS, no candle fallback |
| Historical tick | `DATA_REQUIRED` |
| PBP↔candle PIT | `OPERATION_REQUIRED` |
| Valid Q2 CROSS 63¢ 2025-10-10 | `ZERO_RESULTS`, population 0 |
| Missing settlement (fixture) | `MISSING_SETTLEMENT` |
| Invalid settlement (fixture) | `INVALID_SETTLEMENT` |
| Same-bar WIN+LOSS (fixture) | `SAME_BAR_TIE` |
| Jump-through barrier (fixture) | LOSS on candle-path observation; no fill / maker_fill |

---

## Frozen baseline

```text
Phase 0–8:    85 passed
Phase 9–11:   26 passed
Phase 12–14:  43 passed
Frozen 0–14: 154 passed

Phase 15:      6 passed
Phase 16:      5 passed
Phase 17:     10 passed
Frozen 0–17: 175 passed
```

---

## Phase 18–20 tests

Measured:

```text
ROLLER/.venv/bin/python -m pytest \
  tests/test_warehouse_contract.py \
  … (Phases 0–17 files) \
  tests/test_warehouse_auto_verify.py \
  tests/test_warehouse_frontend_strategy.py \
  tests/test_full_nba_research_desk.py -q
```

```text
Phase 18:     10 passed
Phase 19:     13 passed
Phase 20:     11 passed
TOTAL:       209 passed
FAILURES:      0
```

Additional (not in the pytest total): 4 Node constructor tests; `tsc --noEmit` clean.

---

## What this phase does not claim

- Live execution or Kalshi order submit
- Historical L2 or tick availability
- PBP↔candle PIT synchronization
- Maker/taker fills
- Production trading performance / PnL
- 95% CI (not implemented)

Confirm & Run remains CSV. The warehouse desk does not fall back to it.

---

## Gate

```text
PHASE 20: COMPLETE
Full NBA research desk: PASS
Reference = Optimized: PASS
Coverage integrity: PASS
Row-level reproducibility: PASS
```
