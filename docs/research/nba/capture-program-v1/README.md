# NBA 80/40 Capture Program v1

Research only. Identifier:

```text
MOMENTO_NBA_CAPTURE_PROGRAM_V1
```

Does **not** modify live FIRST01, Kalshi execution, Risk, V1, V2, V3, V4,
MLB research, `nba_80_40_execution_audit.py`,
`first80_execution_audit/`, or `frontend/research-console`.

**LIVE EXECUTION CHANGED: FALSE.**

This program does not enable live NBA trading. There is no NBA strategy
crate. Live still requires a later explicit milestone and the triple gate
(`mode=live`, `live.enabled=true`, `live.confirmation=ENABLE_LIVE_TRADING`).

---

## The two questions

### Question A — closed on 1-minute candles

The FIRST-80 close-path exists as a historical candle-path phenomenon:

```text
1,230 FIRST-80   ·   910 survivors   ·   320 close-40
73.98%           ·   EV_gross = 3p − 2 ≈ +0.2195 R
p_BE = 66.67%
```

V1–V4 found no robust production filter. Stop trying to make the
FIRST-80 entry smarter on this dataset.

See [QUESTION_A_FROZEN.md](QUESTION_A_FROZEN.md).

### Question B — open, and now the program

```text
EV_realized  =  P(F) · E[R | F]  +  P(¬F) · E[R | ¬F]
```

Can Momento capture that path with real orders, fills, stops, fees, and
capacity? **UNKNOWN.** This program measures it.

See [MISSION.md](MISSION.md) and
[QUESTION_B_EXECUTION.md](QUESTION_B_EXECUTION.md).

```text
Weekly return  ≈  N_fills  ×  EV_realized per trade
```

A 1.5–2% week is a **capacity identity**, not a forecast.

---

## Documents

| File | Role |
| --- | --- |
| [MISSION.md](MISSION.md) | Question A closed, Question B open |
| [QUESTION_A_FROZEN.md](QUESTION_A_FROZEN.md) | 1,230 / 910 / 320 freeze |
| [QUESTION_B_EXECUTION.md](QUESTION_B_EXECUTION.md) | Realized EV object |
| [ECONOMIC_MODEL.md](ECONOMIC_MODEL.md) | 3p−2, p_BE, surface regions |
| [EXECUTION_ASSUMPTIONS.md](EXECUTION_ASSUMPTIONS.md) | E0–E3, S0–S2 |
| [FEE_MODEL.md](FEE_MODEL.md) | Pluggable fees; STATUS UNRESOLVED |
| [CAPACITY_MODEL.md](CAPACITY_MODEL.md) | Signal vs executable capacity |
| [LIVE_LEDGER_SCHEMA.md](LIVE_LEDGER_SCHEMA.md) | Engine B columns + statuses |
| [PROMOTION_GATES.md](PROMOTION_GATES.md) | Six gates; none passed |
| [RISK_MODEL.md](RISK_MODEL.md) | Research sizing, governors, MC |
| [ENGINE_A_RULE.md](ENGINE_A_RULE.md) | Frozen trade definition |
| [ENGINE_B_LEDGER.md](ENGINE_B_LEDGER.md) | Event taxonomy |
| [QUESTION_B_SCOREBOARD.md](QUESTION_B_SCOREBOARD.md) | Copied candle facts |
| [WEEKLY_CAPACITY.md](WEEKLY_CAPACITY.md) | N × EV identity |
| [NON_GOALS.md](NON_GOALS.md) | Hard non-goals |
| [PROSPECTIVE_CAPTURE.md](PROSPECTIVE_CAPTURE.md) | Later WS mapping |

Code: `apps/nba-data/scripts/capture_program_v1/`

Warehouse: `.../derived/nba/momento_capture_program_v1/`

Dashboard: `nba-capture-program-v1.canvas.tsx`

```text
/tmp/momento-nba-venv/bin/python run_all.py
```

---

## Pipeline

```text
00_reproduce_baseline.py
01_build_execution_scenarios.py
02_model_entry_capture.py
03_model_stop_capture.py
04_build_fee_model.py
05_capacity_analysis.py
06_portfolio_simulation.py
07_live_episode_ledger.py
08_validation.py
09_report.py
```

All scripts are deterministic. Every artifact carries
`program_version`, `source_dataset_version`, `created_at`,
`assumptions_version`.

---

## Guardrails

Do not optimize FIRST-80 selection.
Do not search for another entry filter.
Do not alter V1–V4, live execution, Risk, or MLB waterfalls.
Do not invent L2.
Do not treat candle prints as fills or wick touches as executable exits.
Do not assume production fees.
Do not present compounded backtests as forecasts.
Do not silently convert ESTIMATED or SIMULATED into OBSERVED.
Do not claim profitability before realized execution evidence exists.
