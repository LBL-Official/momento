# ADR-0004 — Event-time representation

# Decision

Event time is sport-specific and distinct from market (wall / exchange) time.
For MLB, event time is the baseball situation clock, not elapsed UTC alone.

# Context

Live `MarketEvent.game_state` is an opaque `Option<String>` and is typically
`None`. Research has no event domain. The engine must answer “where was the
game?” independently of “where was the book?”

# Problem

Using only wall clock collapses innings, outs, and base/out state into minutes.
That is insufficient for event theta, first-80 context, and loser classification.

# Alternatives Considered

1. Wall-clock-only event time.
2. Replace baseball state with a single synthetic theta number.
3. Preserve raw baseball state; derive synthetics from it.

# Decision Made

Alternative 3. MLB event time includes at minimum:

- inning, half inning
- outs, remaining outs (derived, versioned)
- base state, score state
- plate-appearance state
- pitch state where observed
- batter, pitcher
- game status

Wall-clock timestamps are stored alongside, never as a substitute.

# Rationale

Event-derived research variables require the actual sporting clock.

# Consequences

Waterfall 4 owns `GameState`. Waterfall 1 does not invent event types.
Extra innings, rain delay, and suspended games are explicit statuses.

# Data/Model Implications

Replay-at-t views must not include eventual score or winner.

# Testing Implications

State-machine tests for inning/half/outs; rain delay does not consume outs;
eventual outcome forbidden on live-available state.

# Future Compatibility

Other sports implement adapters (`NbaEventAdapter`, etc.) after MLB completes.

# Status

ACCEPTED

# Date

2026-08-26
