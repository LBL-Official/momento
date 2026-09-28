# ADR-0009 — Market theta

# Decision

Market theta (and other market Greeks) are **empirical research variables**,
not hardcoded theoretical option formulas treated as truth. Definitions are
versioned. Values require method, window, timestamp, and observability.

# Context

The plan names Market Theta, Delta, Gamma, Volatility, Alpha, Beta. No
implementation exists (`crates/prediction` is a stub). Market dynamics should
be discovered from event state, liquidity, and book — not assumed from BS/Black.

# Problem

Shipping a closed-form Θ_M early would freeze a fiction into the database and
invite lookahead if computed from future path.

# Alternatives Considered

1. Import textbook option Greeks as market truth.
2. Skip Greeks entirely.
3. Preserve paths first; define versioned empirical estimators later.

# Decision Made

Alternative 3. Architecture (not formula):

```text
MarketDynamics = F(EventState, EventDynamics, MarketState)
Θ_M = f(Θ_E, State, Liquidity, OrderBook)   # empirical, versioned
```

Waterfalls 1–8 preserve the path. Waterfall 10 computes Greeks with
`value, timestamp, window, method, version`. Unavailable inputs → UNAVAILABLE
Greek, not a substituted formula.

# Rationale

Do not hard-code theoretical financial formulas as truth.

# Consequences

No theta code in Waterfall 1. Research reports must cite method version.

# Data/Model Implications

Greeks used as entry features must be causal (≤ t). Pathwise Greeks that need
the full episode are LABEL_ONLY or post-hoc research.

# Testing Implications

No-lookahead tests on Greek features; method version required; null when L2
missing rather than BS implied vol from last trade.

# Future Compatibility

New estimators are new versions, not overwrites.

# Status

ACCEPTED (estimators deferred to Waterfall 10)

# Date

2026-08-26
