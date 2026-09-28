# Post-Phase-20 ROLLER productionization

Measured: **2026-09-13**. Phase 0–20 warehouse semantics remain frozen.
This is a productionization layer, not warehouse Phase 21.

SuperASI and STAX were not modified.

---

## Verdict

```text
POST-PHASE-20 ROLLER PRODUCTIONIZATION: COMPLETE
```

Independent 3-strategy gate: **3/3 exact**. Risk started only after that gate.
Candle-path results are not fills and are not live trading.

---

## Single research path

```text
FRONTEND → ResearchQuestion → Capability → ResearchContext → ResearchPlan
  → ConditionalBacktest → Results → Labs → Risk
```

Risk consumes a research result. It does not modify ConditionalBacktest.
Research Result and Risk Result are separate artifacts.

Production execute path:

```text
POST /warehouse-research/compile
POST /warehouse-research/execute
```

`GET /warehouse-research/capabilities` is NBA-only.

`App.tsx` does not call `/research-query/compile` or `/research-query/execute`.
`execute.py`, `compiler.py`, `planner.py`, `official_settlement.py`, and
`admin.py` were not edited.

---

## §1–2 Archive / isolate + production API

`GET /warehouse-research/capabilities` (measured 2026-09-13):

```text
available_sports = [NBA]
unavailable_sports = NCAAB, WNBA, MLB, TENNIS → NOT_AVAILABLE
available_observation_bases = [TRADABLE_YES_BID]
available_resolutions = [1_MINUTE_CANDLE]
available_PIT_fields = [available_at]
unsupported_capabilities = HISTORICAL_L2, HISTORICAL_TICK, PBP_MARKET_PIT_ALIGNMENT
```

Non-NBA universes fail closed in `frontend_contract.compile_frontend_research`
**before** `compile_research` as `DATA_REQUIRED` / `UNIVERSE`. They are not
rewritten to NBA and are not reported as `ZERO_RESULTS`.

Phase 19 universe map (not regressing):

```text
Quick Start
sport = basketball
league = NBA
        ↓
NBA warehouse capability
        ↓
AVAILABLE
```

`sport="NBA"` is not the frontend identifier. NCAAB-only basketball is not
rewritten to NBA.

---

## §3 Production frontend (existing terminal)

Chips → `researchQuestionFromDraft` → warehouse compile/execute.

Browser verification on the running desk (`http://127.0.0.1:5179/`, API
`127.0.0.1:8791`):

```text
Quick Start: Basketball + NBA + 2025–26 + Kalshi + candles
Dates: 2025-10-10 → 2025-10-31
Entry: Cross 65¢ Q4
WIN: REACH 85¢
LOSS: REACH 40¢
```

Measured API clocks for that run:

| Step | Clock |
|---|---|
| `POST /warehouse-research/compile` | 2099 ms |
| `POST /warehouse-research/execute` | 6418 ms |
| `POST /warehouse-research/labs` | 9 ms |
| `POST /warehouse-research/risk` (20k paths, UI) | 142 ms |

Result (candle-path, not a fill):

```text
status = READY
population = 23
WIN = 13
LOSS = 7
SAME_BAR_TIE = 3
nominal games = 1362
nominal markets = 2724
plan_hash = 8ba88ac275d1134f70a1aa4834fb17b40eee8c94059786a67736b78b38efdd11
result_hash = 9fb753bdc139c15080a7cdfdaa748844b4877da5e57038119083a8c1fafaf676
warehouse_version = 2026-09-13T06:28:48Z
```

Save Strategy persisted the complete specification to Labs (folder `NBA`).
Results expose strategy + execution hashes/versions + population +
classification + W/L / R:R / gross EV.

---

## §4 Labs

Disk:

```text
ROLLER/labs/<folder>/<lab_id>/
  Roller[Strategy Name].csv
  metadata.json
```

`created_at` is metadata only. Same spec + warehouse version + result hash
+ Mode A seed/config ⇒ same CSV bytes. Labs are not the warehouse.

This file is the SuperASI ingest contract. SuperASI code is not changed
in this pass. One header, every save:

```text
record_type=row      candle-path trades (research meaning unchanged)
record_type=risk     Mode A desk scalars + MC distribution summary
record_type=weekly   binomial table k = 0..N
```

`gross_ev` remains candle-path research EV (`ev_e4`). Risk columns are
theoretical Mode A (B=$20,000, f=0.05, N=10, r_w=+0.20, r_l=−0.40,
p=0.70, T_w=0.01, 52 weeks, 100k paths, seed 20260913). They are not
fills. `fees` / `slippage` / `fills` = `UNAVAILABLE`. `net_ev` =
`NOT_COMPUTABLE`. `correlation_status` = `CORRELATION_DATA_REQUIRED`.
`risk_not` = `candle_path_not_fill`.

`Save Strategy` / `save_lab` runs Mode A before writing the CSV. No
second click. 100k paths are not dumped; SuperASI gets the summary
percentiles, mean, median, and target probabilities.

Canonical header (132 unique columns; row-level ops use `*_row` suffixes):

```text
record_type, strategy_name, sport, league, season, date_from, date_to, universe,
observation_basis, resolution, pit_field,
entry_operation, entry_parameters, win_exit_operation, win_exit_parameters,
loss_exit_operation, loss_exit_parameters, terminal_behavior,
plan_hash, compiler_version, warehouse_version, identity_version,
catalog_version, execution_version, data_fingerprint, backtest_status,
population, wins, losses, win_rate, loss_rate, average_win, average_loss,
risk_reward, gross_ev,
internal_game_id, market_id, entry_timestamp, entry_value, entry_operation_row,
entry_period, entry_clock,
win_exit_timestamp, win_exit_value, win_exit_operation_row,
loss_exit_timestamp, loss_exit_value, loss_exit_operation_row,
classification, settlement_status, settlement_value, result_hash,
risk_mode, risk_seed, risk_result_hash, static_weekly_sizing,
initial_bankroll, trade_allocation, trades_per_week, win_return, loss_return,
risk_win_probability, target_weekly_ev, weeks_per_year, monte_carlo_paths,
capital_per_trade, win_pnl, loss_pnl, R_w, R_l, break_even_probability,
trade_ev, trade_ev_dollars, weekly_ev, weekly_ev_dollars, min_wins_for_target,
P_target_week, P_below_target, P_negative_week, weekly_volatility,
deterministic_compound_if_ev_realized,
fees, slippage, fills, net_ev, correlation_status,
mc_bankroll_{p5,p10,p25,p50,p75,p90,p95,p99,mean,median,min,max},
mc_return_{…}, mc_mdd_{…},
P_final_ge_1_5x, P_final_lt_B0, P_mdd_le_neg_5, P_mdd_le_neg_10, P_mdd_le_neg_20,
risk_not,
weekly_wins, weekly_losses, weekly_return, weekly_probability
```

New saves use `Roller[Strategy Name].csv`. Stored bytes = downloaded bytes
(tested in `tests/test_research_labs.py`, including Mode A anchors
p_BE=2/3, EV/trade=0.001, EV/week=0.01, C=1000).

Prior UI save from this session (research-only schema, before this
contract) remains on disk as historical evidence:

```text
lab_id = b6404738888b42728c5559bfa80f84c0
filename = RollerQ4 Cross 65 REACH 85 40.csv
csv_sha256 = d462cb5fe93d904b36ac355bb41edb899d88f3bd437ef220ac472483b875fbf8
```

Re-save a strategy to emit the SuperASI contract header.

Results Labs UI: sort, filter, inspect, download, folders. Not
localStorage `LibraryView`.

---

## §5 Independent 3-strategy validation — GATE PASSED

Scripts:

- Production: `ROLLER/scripts/validate_three_random_nba_strategies.py`
  → HTTP `POST /warehouse-research/execute` (optimized)
- Oracle: `ROLLER/scripts/independent_nba_evaluator.py`
  → `compile_research` + `get_research_context` + `run_plan(..., engine_id="reference")`

The evaluator does not import `frontend_contract` and does not treat
production JSON as ground truth. Not FIRST80. Not Confirm & Run
`operations.py`.

```text
validation_seed = 20260913
strategy_1_seed = 1602050
strategy_2_seed = 3184043
strategy_3_seed = 3904527
exact_3_of_3 = true
```

Raw report: `ROLLER/reports/three_random_nba_validation.json`.

Loaded context (evaluator, same window on all three):

```text
loaded_observations = 466077
loaded_pbp_events = 73907
months present in context load = 2025-10, 2025-11
```

| # | Spec | N | W / L | Other | Production execute | Evaluator compile / context / backtest / total | plan_hash (16) | result_hash (16) | diffs |
|---|---|---:|---|---|---:|---|---|---|---:|
| 1 | Q2 ABOVE 65 — REACH 85 / DROP_TO 41, BOTH, 2025-10-10→10-31 | 25 | 11 / 14 | — | 12.026 s | 2.234 / 6.751 / 5.791 / 14.776 s | `da5ce87b99e526a1` | `d2326e487f573c54` | 0 |
| 2 | Q1 FIRST_TOUCH 63 — REACH 90 / REACH 41, NO | 35 | 11 / 24 | — | 10.464 s | 0.001 / 6.431 / 3.826 / 10.258 s | `a445b90e24f4f50f` | `9894f96d5d353a00` | 0 |
| 3 | Q4 CROSS 63 — REACH 85 / REACH 41, NO | 18 | 8 / 8 | SAME_BAR_TIE 2 | 7.876 s | 0.000 / 6.457 / 4.283 / 10.741 s | `98f6a450ecaddd84` | `435f0b5cf80fab7f` | 0 |

Equality checked: population, row identity, entry timestamp/value, WIN exit,
LOSS exit, classification, settlement, aggregates, result hash.

CSV schema/metadata/rows and Labs save under folder `validation` also PASS.

---

## §6 Risk — consumer only, after 3/3

Package: `ROLLER/roller/risk/`. Persist: `ROLLER/risk_results/` (not Labs CSV).

Baseline config (percents as decimals):

```text
B = 20000
f = 0.05
N = 10
r_w = +0.20
r_l = −0.40
p = 0.70
T_w = 0.01
weeks = 52
engine default MC paths = 100000
```

Anchors (unit tests + UI Mode A):

```text
C = $1,000
R_w = +1%
R_l = −2%
p_BE = 66.6666667%
required p = 70%
EV_t = +0.10% / $20
EV_week = +1% / $200
σ_week ≈ 4.35%
min wins for target = 7
static weekly sizing = true
```

Measured UI Mode A on the Q4 Cross 65 result (seed `20260913`, **20k** paths
at the time of the click; engine default and later UI requests are 100k):

```text
MC mean / median terminal bankroll = $33656.92 / $32149.28
P(lose money) = 6.67%
P(≥1.5×) = 58.91%
MDD p5 = −32.59%
fees / slippage / fills = UNAVAILABLE
net EV = NOT_COMPUTABLE
correlation = CORRELATION_DATA_REQUIRED
risk_result_hash = 9a92b0c55235595466b9a86ad000119672a6b00724c4d249220396d217fdb0a0
persisted = ROLLER/risk_results/6b9aa303c9c042c29f202c88fae5ccf0/risk_result.json
```

Mode B: fees/slippage/fills = `UNAVAILABLE`; net EV = `NOT_COMPUTABLE` unless
the caller sets theoretical zero-cost. No Sigma → `CORRELATION_DATA_REQUIRED`.
Mode C requires externally supplied `probabilities` or the API returns 400.

`(1+EV)^52` is recorded as a deterministic note only. It is not a Monte Carlo
substitute. Mean and median are both returned.

---

## §7 Tests (measured this session)

Productionization unit tests:

```text
tests/test_production_capabilities.py
tests/test_research_labs.py
tests/test_bankroll_risk.py
15 passed in 2.47s
```

Frozen Phase 0–20 warehouse suite (same file list as Phase 20 close):

```text
209 passed in 29.75s
0 failed
```

Frontend: `npx tsc --noEmit` passed.

Phase 0–20 reports were not rewritten as if those phases changed.

---

## Original §51 checklist

| Item | Status |
|---|---|
| Legacy Confirm & Run / CSV / FIRST80 / MLB last-trade not a production execute path | PASS |
| Capability-first NBA-only API; unsupported sports fail closed before compile | PASS |
| Existing terminal; chips → ResearchQuestion; basketball+NBA → AVAILABLE | PASS |
| Results provenance + Save full spec | PASS |
| One Labs CSV schema; stored bytes = downloaded bytes; labs ≠ warehouse | PASS |
| Labs CSV SuperASI contract: row + risk + weekly; Mode A labeled, not a fill | PASS |
| 3/3 independent exact row/hash match | PASS |
| Risk consumer-only after 3/3; Risk Result JSON remains separate; no fabricated fills/fees/Sigma | PASS |
| This report uses measured clocks/hashes only | PASS |
| Phase 20 remains frozen | PASS |
| NCAAB / WNBA / MLB / Tennis not enabled | PASS |

---

## What this is not

- Live trading
- An executable fill
- L2 or tick reconstruction
- PBP↔candle PIT alignment
- Invented fees, slippage, covariance, or Sigma
- A SuperASI or STAX change
- Warehouse Phase 21
