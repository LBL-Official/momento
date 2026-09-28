# ADR-0016 — Primary research objects

# Decision

A trade is never the unit of historical truth. `StateTransition` is the atomic
reconstructable observation. `GameMarketEpisode` is the container (one game,
both contracts, full paths, outcomes).

# Context

The reset named `GameMarketEpisode` as primary. The rebuild brief named
`StateTransition`. Neither type exists in Rust today. LEGACY artifacts are
opportunity/intent CSVs.

# Problem

Ambiguity would recreate a trade-centric backtester and skip path reconstruction.

# Alternatives Considered

1. Trade/opportunity as primary object.
2. Only episodes, no atomic transitions.
3. Dual: atomic transition inside episode container.

# Decision Made

Alternative 3. FIRST01 is a plugin that walks transitions; it does not define
the schema. The data layer must compile without FIRST01.

Do not store only the state at 80%. The preceding path is a first-class
research object.

# Rationale

Desk losses require “how did we get here?”, not only “did we take the trade?”

# Consequences

Waterfalls 5–8 build transitions and paths. Waterfall 13 is the first plugin.
LEGACY CSVs remain regression artifacts.

# Data/Model Implications

Labels attach to episodes/transitions, not to a reconstructed fill that never
occurred.

# Testing Implications

Invariant tests: episode contains both contracts; transition has before/after
and trigger; no lookahead on plugin-visible fields.

# Future Compatibility

Live state schema should match `HistoricalState` (W25).

# Status

ACCEPTED

# Date

2026-08-26
