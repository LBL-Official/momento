# ADR-0003 — PBP synchronization

# Decision

EVENT and MARKET domains are reconstructed independently, then joined with an
explicit confidence classification. Failed joins do not drop either raw stream.

# Context

No MLB PBP exists locally. Kalshi June 2026 trades/candles exist for 13 days.
PBP time is not Kalshi trade time. The north star requires synchronized state.

# Problem

Assuming play time equals trade time, or dropping a game because one side is
missing, destroys research coverage and invents precision.

# Alternatives Considered

1. Require exact timestamp equality or discard the game.
2. Force-align every trade to the nearest PBP play.
3. Independent reconstruction + versioned join with confidence.

# Decision Made

Alternative 3. Every synchronized observation retains:

```text
event_timestamp
market_timestamp
synchronization_delta
synchronization_method
synchronization_confidence
```

Confidence (never silently upgraded):

```text
EXACT | WITHIN_1S | WITHIN_3S | WITHIN_5S | WITHIN_INNING | AMBIGUOUS | UNMATCHED | UNAVAILABLE
```

If PBP is missing: `event_state = UNAVAILABLE`, market path retained.
If Kalshi is missing: `market_state = UNAVAILABLE`, event path retained.

# Rationale

Honesty about join quality is more valuable than a complete-looking table.

# Consequences

Waterfall 3 implements the join; Waterfalls 1–2 only preserve join keys.
No PBP download until source/license is authorized.

# Data/Model Implications

Features that need event state are unavailable when confidence is `UNAVAILABLE`
or `UNMATCHED`. Models must not treat unmatched as exact.

# Testing Implications

Sync tests: unmatched retained; confidence never upgraded; delta recorded;
no invented PBP timestamps.

# Future Compatibility

NBA/NHL clocks use the same confidence enum with sport-specific methods.

# Status

ACCEPTED

# Date

2026-08-26
