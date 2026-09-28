# Execution assumptions

Every row in the scenario matrices carries an observation status.

Never upgrade `UNAVAILABLE` → `SIMULATED` → `ESTIMATED` → `OBSERVED`.

---

## Entry scenarios

### E0 — Idealized

Every valid 80 signal fills at exactly 80. Exists only to reproduce
historical path economics. Label: `SIMULATED` except the path labels
copied from the frozen ledger (`OBSERVED` candle path).

### E1 — Conservative fill probability

Evaluate P_fill ∈ {100%, 90%, 80%, 70%, 60%, 50%}.

Do not invent a “correct” fill probability. Show the break-even surface.

### E2 — Partial fills

α ∈ {25%, 50%, 75%, 100%}. Capacity and portfolio use filled quantity.

### E3 — Missed signals

```text
N_fillable  =  N_signals · P_fill
```

A signal may occur but the order does not fill before price moves away,
the market resolves, risk capacity is exhausted, or another constraint
hits. More signals do not automatically increase deployable capital.

---

## Stop scenarios

### S0 — Historical close-path

`yes_bid_close ≤ 40`. Historical label only. 320 / 1,230.

### S1 — Immediate touch

`yes_bid_low ≤ 40`. Wick-trigger proxy. Frozen audit: 381 / 1,230
(all-fills wick-stop). Not an executable fill.

### S2 — Executable stop simulation

Parameterized P_stop_fill and fill price ∈ {40, 39, 38, 35, 30}¢.

Label: `SIMULATED_EXECUTION_SCENARIO`.

Do not claim these prices are historically executable without
high-resolution data.

---

## What is still UNAVAILABLE

- Queue position at 80
- Time-to-fill
- Observed partial-fill distribution
- Stop trigger vs stop fill as distinct live events
- Actual stop fill-price distribution
- L2 depth
- Production fee schedule

Do not invent L2. Do not treat candle prints as fills.
