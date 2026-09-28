# ADR-0012 — No-lookahead rules

# Decision

Any feature used for a historical decision at timestamp t must represent
information actually available at t. Future information may be used only for
labels, outcomes, and retrospective analysis.

# Context

This is a financial research system. Candle close at period end, PBP of later
innings, settlement winners, and post-80 paths are all future relative to
earlier t. LEGACY day partitions can omit pre-close-day lifetime path, which
is a coverage issue, not a license to backfill from settlement.

# Problem

Leakage produces backtests that cannot exist live.

# Alternatives Considered

1. Trust researchers not to leak.
2. Ban all future fields from the database.
3. Store future labels separately; enforce live-available views in code and tests.

# Decision Made

Alternative 3.

- Strategy plugins see a causal view of `StateTransition`.
- Eventual winner / terminal score are forbidden on replay-at-t state.
- Labels live on episode/label stores.
- Every S-step completion record includes a lookahead / leakage review.

Detect in validation: look-ahead, survivorship, future PBP/quotes, duplicate
GameIds/opportunities, timestamp collisions, missing data.

# Rationale

Prefer missing an opportunity over a fictional edge.

# Consequences

FIRST01 replay (W13) must not peek at 89 before entry. Feature engine rejects
LABEL_ONLY from the live-available set.

# Data/Model Implications

Train/val/OOS splits are temporal. Purged CV / embargo belong to W19.

# Testing Implications

No-lookahead tests are mandatory wherever features or plugins exist.
A passing compiler is not completion.

# Future Compatibility

Live host must consume the same causal schema (W25) so backtest_state ≠ live_state
cannot reappear.

# Status

ACCEPTED

# Date

2026-08-26
