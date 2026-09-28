# ADR-0006 — First-80 semantics

# Decision

First-80 is the first timestamp at which the **qualifying YES bid** is ≥ 80¢
on a given `(GameId, MarketId, Side)`. It is sticky. It is not average time
above 80, not last trade, not mid, not ask.

# Context

Live FIRST01 (`strategies/mlb`) and research FIRST01 v1 already use YES bid
only. Kalshi has no official mid. A generic threshold engine (20–95) will
exist; FIRST01 consumes first-80 as one node.

# Problem

Using candle close, last trade, or “time spent above 80” would diverge from
live and invent a different strategy.

# Alternatives Considered

1. First last-trade ≥ 80.
2. Mid ≥ 80 (invented).
3. First YES bid ≥ 80, sticky, matching live.

# Decision Made

Alternative 3. Generic engine records first-touch of YES bid at 20, 30, 40,
50, 60, 70, 80, 81, 83, 89, 90, 95. FIRST01’s first_80 is the 80 node with
live-aligned sticky bind.

If a node never occurs, record `DID_NOT_OCCUR` rather than omitting it.

Minor live vs research timing (same-quote 81 confirm in live vs later quote
in LEGACY research) is documented, not “fixed” in production.

# Rationale

Research that cannot replay live rules is not a control baseline.

# Consequences

Data layer must not hard-code 80. Threshold plugin/config supplies levels.
Candle observability may observe first_80 on candle bid; execution must not
claim maker fills on `CANDLESTICK_ONLY`.

# Data/Model Implications

Labels such as “hit 89 first” are LABEL_ONLY. Entry features at first_80 must
not include post-80 path.

# Testing Implications

Invariant: opponent cannot confirm after bind. Sticky forever per game.
No mid. Bid < ask required for maker eligibility (FIRST01 plugin).

# Future Compatibility

Hyperparameter experiments may vary thresholds only as versioned overrides;
canonical FIRST01 v1 remains the control.

# Status

ACCEPTED

# Date

2026-08-26
