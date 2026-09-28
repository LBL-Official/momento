# ADR-0010 — Event theta

# Decision

Event theta is an empirical sporting-event quantity derived from event state
(remaining opportunity, information rate, state significance). It is not a
replacement for the baseball clock and not a hardcoded financial formula.

# Context

Waterfall 9 lists Event Theta, Delta, Gamma, Volatility, Alpha, Beta. Remaining
outs (see ADR-0005) is a primary input, extensible toward plate appearances,
batters faced, run expectancy, leverage-like measures.

# Problem

Treating a single theta number as the event would discard inning/score/base
state and encourage fitting a pretty curve before reconstruction exists.

# Alternatives Considered

1. Wall-clock decay as event theta.
2. Hardcoded win-expectancy table as OBSERVED truth.
3. Preserve event-state path; versioned empirical theta later.

# Decision Made

Alternative 3. `EventThetaInputs` (architecture):

```text
remaining_opportunities
information_rate_proxy
state_significance_proxy
```

Do not ship a universal theta equation in Waterfall 1. WE/leverage tables, if
used, are MODELED or DERIVED with cited version — never silently OBSERVED.

# Rationale

Synthetics are derived from the actual event, not substituted for it.

# Consequences

Waterfall 4 stores inputs. Waterfall 9 computes values. Every Greek carries
`value, timestamp, window, method, version`.

# Data/Model Implications

Event probability ↔ market relationship (αE/βE) is discovered empirically
after sync exists.

# Testing Implications

Theta missing when PBP UNAVAILABLE. No future innings in theta-at-t.

# Future Compatibility

Other sports define remaining-opportunity analogously; they do not inherit MLB
54-out theta.

# Status

ACCEPTED (estimators deferred to Waterfall 9)

# Date

2026-08-26
