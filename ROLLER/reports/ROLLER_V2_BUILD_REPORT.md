# ROLLER V2 build report

**Date:** 2026-09-06  
**Extension of:** V1 (not a rewrite)  
**`state_schema_version`:** 2.0.0

```text
RESEARCH ONLY
OBSERVATION ≠ INFORMATION ≠ PREDICTION ≠ EDGE ≠ EXECUTION
CANDLE PATH ≠ FILL
LIVE EXECUTION = FALSE
```

## Gate results

| Gate | Status | Notes |
|------|--------|-------|
| 1 Audit + metadata | IMPLEMENTED | Pre-implementation audit; V1 tests stayed green; half-open locked; `contains_future_information`; `dataset()` reject |
| 2 Events + possessions | IMPLEMENTED | NBA pass-through fields; `players.csv` no silent merge; two-clock equality hidden; NBA possession statuses |
| 3 Backward states + Γ_t | IMPLEMENTED | Query-time `observation()`; no giant observation CSV |
| 4 Labels | IMPLEMENTED | `db.labels()` only; V3 `research()` stub |

## Capability matrix (as implemented)

| Engine | NBA | WNBA / NCAAB |
|--------|-----|----------------|
| Events | REAL | REAL (normalized plays) |
| `player_id` | REAL from `pbp_live.personId` | SCHEMA_ONLY — names not parsed from text |
| Possessions | REAL + CONFIRMED/RECONSTRUCTED/AMBIGUOUS/UNRESOLVED | NOT_SUPPORTED |
| Player in-game stats | REAL where personId + type support it | NOT_SUPPORTED |
| Lineups | INCOMPLETE (subs, no starters) | SCHEMA_ONLY |
| Information / starters | NOT_SUPPORTED | SCHEMA_ONLY |
| Market state | REAL integer E4 | REAL where MAPPED |
| Labels | REAL on synthetic + NBA variables | Only where the variable exists |

## IMPLEMENTED

- Constitutional `available_at < cutoff` unchanged in `timeutil.py`
- Two-clock tests: `event_time < t` still hidden when `available_at >= t`; equality hidden
- `observation_id` deterministic
- Section `source_availability_status` + field missingness
- Feature registry with `lookahead: false`
- Update tail writes `meta/players.csv` and NBA `derived/possessions.csv`
- Leakage audit samples one observation per sport/season and forbids labels on `O_t`

## PARTIAL

- Lineups: substitutions only
- Information state: extension point only
- State-transition `ΔS`: contract in `STATE_MODEL.md`, no engine
- V1 `game_state()` keys unchanged; formal `O_t` is `observation()`
- Production warehouse player/possession quality depends on source `personId` / action types

## NOT YET (recommend V3 only)

- `db.research` train / validation / OOS
- Combining labels into `I(t)` (forbidden)
- Greeks, fills, live P&L, W9
- FIRST75/80, DRE, Lebronner
- Injury / starter scrapers
- Unsupervised regimes
- Giant observation CSV
- Numeric possession confidence
- Effective-n adjustments

## Tests

Synthetic CI (no 4GB warehouse required): V1 suite plus two-clock, possessions, players, observation_id, label reject, trajectory, market, player state, lineups, missingness.

## Financial / temporal behavior

- No live risk or order path.
- Public visibility: `available_at < cutoff` only.
- Labels never pass `dataset()` or `observation()`.
