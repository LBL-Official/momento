# ADR-0017 — FIRST01 is a strategy plugin

# Decision

FIRST01 is the first strategy plugin and the frozen control baseline. It is not
the historical database and not the definition of the research platform.

# Context

Live MLB/WNBA desk strategy is FIRST01 (80/81/83/89/50%). LEGACY
`momento-research-backtest` replays a copy on candles. Candle maker fills are
not historically provable.

# Problem

Extending the candle runner as “the engine” would skip event/market truth and
invite threshold fishing.

# Alternatives Considered

1. Rebuild/extend `research-backtest` as the platform.
2. Encode 80/81/89 into the data layer.
3. New reconstruction engine; FIRST01 consumes state as a plugin.

# Decision Made

Alternative 3. Frozen control:

```text
one canonical opportunity per GameId
sticky first_80 → 81 confirm → maker 80–83
GAME_LOCK ≥ 89
50% entry-VWAP stop
one lifecycle consumed per game
```

Do not automatically optimize FIRST01 thresholds. Candidate changes stay
versioned until approved (ADR-0013).

LEGACY_V1 runner is preserved for rule regression, deprecated as the platform.

# Rationale

The historical state engine comes first. FIRST01 replay comes later (W13).

# Consequences

Data/state/path layers must not hard-code FIRST01 constants.
`research-strategies` remains the LEGACY copy until the plugin is re-hosted.

# Data/Model Implications

Risk caps (`max_open_positions=5`, 12.5% budget) are not FIRST01 rules.
Frequency recon must keep that distinction.

# Testing Implications

Keep LEGACY FIRST01 tests green. Do not change live strategy tests for research.

# Future Compatibility

Other strategies become additional plugins on the same engine.

# Status

ACCEPTED

# Date

2026-08-26
