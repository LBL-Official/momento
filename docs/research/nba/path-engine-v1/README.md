# Path Engine V1 — market-only NBA 80/40 path risk

Research only. Does not change live FIRST01, Risk, or Kalshi execution.
Does not invent L2. Does not invent PBP wall-clock. Does not start W9.

```text
PATH_ENGINE_V1_MARKET_ONLY
```

## Canonical object

The engine does **not** predict the NBA game. It estimates **conditional
path-barrier failure** at the first-80 decision:

```text
Y_40 = 1  ⇔  the 40 barrier is subsequently crossed
q(Z) = P(Y_40 = 1 | Z_τ80)
P(survival | Z) = 1 − q(Z)
```

Canonical economics (gross, +1R survive / −2R barrier):

```text
EV_gross = (1 − q)(+1) + q(−2) = 1 − 3q
breakeven: q = 33.33%
```

Unconditional frozen baseline (close-path 40 after first-80):

```text
q   = 320 / 1230 = 26.02%
EV  ≈ +0.219 R
survival = 73.98%
```

A classifier that predicts “no 40 for everyone” can hit ~74% accuracy and
is economically useless.

```text
FROZEN FIRST-80 EVENT
        │
        ▼
Z(τ80) causal market information
        │
        ▼
q̂ = P(40 barrier | entry state)
        │
   ┌────┴────┐
   ▼         ▼
LOW PATH   HIGH PATH
RISK       RISK
   │         │
ACCEPT    REJECT / NO TRADE
   │
EV = 1 − 3q   and   acceptance rate
```

## Decision time

```text
ENTRY_DECISION_TIME = end of first-80 candle
entry_time_precision = 1m_candle
```

Entry-candle OHLC is observable at that modeled decision. Intraminute order
inside the minute is unknown. This is not a historically verified maker fill.

Primary label `target_close_40` begins on the first **subsequent completed
candle after ENTRY_DECISION_TIME**.

## What V1 is not

- Not NBA-winner prediction
- Not a live production filter unless OOS meets all four utility criteria
- Not a rebuild of the frozen 80/40 audit
- Not a PBP game-state model (V2)

Game-state columns exist as nullable `UNAVAILABLE` /
`quarter_source=UNAVAILABLE_NO_WALL_CLOCK_JOIN`.

## Layout

| Role | Path |
| --- | --- |
| This spec | `docs/research/nba/path-engine-v1/` |
| Dataset | `Backtesting Suite/Data/NBA/2025-2026/warehouse/derived/nba/momento_path_engine_v1/` |
| Code | `apps/nba-data/scripts/path_engine_v1/` |
| Frozen audit (read-only) | `.../derived/nba/first80_execution_audit/` |

V1 result: `REPORT.md` in the dataset folder. Dashboard:
`nba-path-engine-v1.canvas.tsx`.

## Split roles

```text
TRAIN       → BUILD
VALIDATION  → CHOOSE
OOS         → VERIFY
```

See [SPLITS.md](SPLITS.md). Features: [HYPOTHESIS_LEDGER.csv](HYPOTHESIS_LEDGER.csv).
Baseline: [FROZEN_BASELINE.md](FROZEN_BASELINE.md).
