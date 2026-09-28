# ADR-0011 — Feature availability classifications

# Decision

Every feature (and every important field) carries an availability /
observability classification. Classifications are never silently upgraded.

# Context

Historical Kalshi data is heterogeneous: trades OBSERVED, L2 UNAVAILABLE,
candles OBSERVED-as-candles, PIT REST OBSERVED-as-of-ingest. PBP is absent.

# Problem

A model that treats all columns as equally “known at t” will leak or fabricate.

# Alternatives Considered

1. Boolean `is_valid`.
2. Nulls without reason.
3. Explicit classification vocabulary.

# Decision Made

Alternative 3. Canonical availability:

```text
OBSERVED     — present in an immutable raw record at ≤ t
DERIVED      — deterministic function of observed data at ≤ t (no lookahead)
INFERRED     — join/sync that can be wrong; must carry confidence
MODELED      — simulation (fills, fees, queue, later theta estimators)
LABEL_ONLY   — future information; training labels / retrospective only
UNAVAILABLE  — not in source; null + reason; never fabricated
```

Never promote INFERRED → OBSERVED. Never fill UNAVAILABLE with interpolated L2.
`LABEL_ONLY` is forbidden in entry, execution, and risk feature sets.

# Rationale

Accuracy over completeness.

# Consequences

Feature warehouse (later waterfall) must store classification per feature
version. Live-available subset is a documented allow-list.

# Data/Model Implications

XGBoost/MC may use LABEL_ONLY only as targets, not as inputs for a live-like
decision.

# Testing Implications

Malformed-input and no-lookahead tests per feature family. Promotion forbidden
in unit tests.

# Future Compatibility

New sources add OBSERVED fields; they do not reclassify old UNAVAILABLE rows.

# Status

ACCEPTED

# Date

2026-08-26
