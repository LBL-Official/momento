# ADR-0013 — Model promotion / research–production boundary

# Decision

Research never automatically changes production trading. Model promotion is a
supervised pipeline. FIRST01 live parameters are frozen during engine work.

# Context

Production path: strategy → risk → execution → Kalshi. Research crates must
not depend on risk, execution, or `strategies/mlb`. Prediction crate is a stub.

# Problem

A promising backtest silently replacing 80/81/83/89/50% or auto-wiring a model
into Risk would be an unauthorized financial behavior change.

# Alternatives Considered

1. Auto-deploy when OOS beats baseline.
2. Researchers edit `strategies/mlb` when a candidate looks good.
3. Explicit governance statuses with CEO/CTO authorization to production.

# Decision Made

Alternative 3.

```text
RESEARCH → CANDIDATE → VALIDATED → SUPERVISED → APPROVED → PRODUCTION
```

No silent model replacement. No automatic production mutation.
Changing 80/81/83/89/50% is a **strategy** change, not an engine change.

Research may discover candidate improvements; they remain versioned and
supervised until explicitly approved.

# Rationale

Never sacrifice trading safety for research velocity.

# Consequences

Waterfall 24 is the registry. Waterfall 25 is the production bridge — later.
W1 crate graph test: new research code ↛ `momento-risk`, `momento-execution`,
`momento-strategy-mlb`.

# Data/Model Implications

Production does not rewrite the model from live outcomes automatically (W26
feeds research; promotion still supervised).

# Testing Implications

Production fence tests. Do not delete failing production tests to pass research.

# Future Compatibility

Same `HistoricalState` schema for replay and live when W25 is authorized.

# Status

ACCEPTED

# Date

2026-08-26
