# ADR-0005 — MLB 54-out representation

# Decision

Regulation MLB opportunity is modeled as 54 outs (9 × 2 × 3) as a **derived,
versioned remaining-opportunity input**, not as a replacement for the actual
inning/half/outs clock. Extra innings extend beyond 54. Rain delays do not
consume outs.

# Context

Event theta needs a remaining-opportunity measure. A common baseball research
convention is 54 regulation outs. Hard-coding 54 as “the event clock” would
erase extra innings, walk-offs (home team may not bat in the 9th), and delays.

# Problem

If remaining-outs is treated as ground truth without versioning, later rule
changes or walk-off handling silently bias theta and labels.

# Alternatives Considered

1. Ignore outs; use wall clock only.
2. Hard-code 54 as the only event clock.
3. Store actual outs/inning/half; derive remaining-opportunity with a versioned
   definition that starts from the 54-out regulation model.

# Decision Made

Alternative 3.

- Actual baseball clock is always stored (OBSERVED or reconstructed from PBP).
- `remaining_outs_approx` (name TBD in W4) is DERIVED.
- Definition v1: regulation 54-out backbone, plus explicit walk-off and extra-inning
  rules documented in the transform version.
- Do not ship a closed-form theta equation in Waterfall 1.

# Rationale

Preserve inputs; do not replace the sport with a synthetic metric.

# Consequences

Walk-off and extra-inning fixtures are mandatory before any theta claim.
Formula of ΘE is deferred to Waterfall 9 and must cite this definition version.

# Data/Model Implications

Features using remaining outs must record `remaining_outs_definition_version`.

# Testing Implications

9th-inning walk-off (home leading after 8.5) must not force 54 consumed.
Extra innings increase remaining opportunity beyond 0 at end of 9.

# Future Compatibility

NBA/NHL remaining-opportunity measures get their own ADRs; they must not reuse
54-out as if it were sport-agnostic.

# Status

ACCEPTED (definition v1 to be encoded in Waterfall 4; formula deferred)

# Date

2026-08-26
