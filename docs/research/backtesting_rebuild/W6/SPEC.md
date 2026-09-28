# CTO-W6 SPEC

**Name:** Canonical MLB State Engine  
**Status:** IMPLEMENTED  
**PLAN alias (this grant):** canonical GameState / StateTransition substrate  
**Not:** PLAN-W13 FIRST01 replay

## Objective

Construct a canonical, replayable MLB game-state transition engine that is the
single authoritative representation of MLB game state for all downstream research.

```
raw PBP → canonical events → pre-event state → transition → post-event state
```

## Inputs

W2/W3 canonical PBP (`CanonicalMlbEvent`) from StatsAPI landing envelopes.

## Outputs

`GameState`, `StateTransition`, `state_at_or_before(T)`, fingerprints, SQLite
store, manifests, validation report.

## Explicitly out of scope

W7 price paths, FIRST01 replay, outcome/trade labeling, ML, execution
simulation, invented L2/bid-ask/open-close, market Greeks, Kalshi network.
