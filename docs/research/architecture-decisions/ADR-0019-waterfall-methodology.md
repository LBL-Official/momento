# ADR-0019 — Waterfall methodology (W/A/S)

# Decision

All historical-engine development uses `W# → A# → S#`. Agents must not silently
jump waterfalls. Each S-step is independently understandable, implementable,
testable, and verifiable. Architecture blocks are not padded to a fixed step count.

# Context

CEO approved strict waterfall governance. Prior plan listed waterfalls 0–26 and
phases 1–27. Recon completed Waterfall 0 documentation. Implementation of W1
requires explicit authorization.

# Problem

Unbounded code generation would skip truth layers, retune FIRST01, or touch
production.

# Alternatives Considered

1. Agile skip-ahead to interesting ML.
2. Force exactly 10 S-steps per A-block.
3. Strict W/A/S with variable S-count and checkpoint discipline.

# Decision Made

Alternative 3. Complete per S-step:

```text
IMPLEMENT → TEST → VALIDATE → DOCUMENT → ARTIFACT → CHECKPOINT
```

Then STOP unless the execution instruction authorizes the next S-step.

If a step reveals a later-waterfall dependency: DOCUMENT and STOP.

Checkpoint updates: master waterfall, registry, completion record, ADRs if
needed, current-state, artifacts, Drive/Sheets status, next W/A/S.

# Rationale

Controlled construction, not maximum code generation.

# Consequences

Registry is the operational source of step status. Master document must not
go stale relative to code.

# Data/Model Implications

None directly; process constraint.

# Testing Implications

A passing compiler is not completion. Each S-step lists test requirements.

# Future Compatibility

NBA/other sports do not start as implementation targets until MLB completes
the full waterfall.

# Status

ACCEPTED

# Date

2026-08-26
