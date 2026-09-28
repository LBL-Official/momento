# ROLLER V2 pre-implementation audit

**Date:** 2026-09-06  
**Purpose:** Gate 1. Inspect validated V1 before any V2 engine work.  
**Invariant (locked):** `visible(row, t)` iff `available_at < t`. Equality is hidden. `event_time` does not grant visibility.

V1 tests were re-run as part of this gate. Do not treat planned V2 architecture as implemented.

## Constitutional check

| Component | Expected | Actual | Status | V2 Dependency | Recommended Action |
|-----------|----------|--------|--------|---------------|--------------------|
| Point-in-time filter | `available_at < cutoff` | [`timeutil.apply_as_of`](../roller/timeutil.py), [`filters.public_filter`](../roller/point_in_time/filters.py) | PASS | Required — do not switch to `<=` | Keep V1 half-open. Document as constitutional. |
| Naive timestamp reject | Raises | `TimestampError` | PASS | Required | Keep |
| Public API requires `as_of` | Error without `full_history` | `AsOfRequiredError` | PASS | Required | Keep; add future-info reject |
| Two-clock visibility | Event with `event_time < t` but `available_at >= t` hidden | Alignment uses `available_at` only; no dedicated two-clock test | PARTIAL | Gate 2 | Add equality-hidden two-clock test. Do not change filter. |

## V1 inventory

| Component | Expected | Actual | Status | V2 Dependency | Recommended Action |
|-----------|----------|--------|--------|---------------|--------------------|
| Database map | Self-describing sports/seasons | `roller.json` v1.0.0 | PASS | Version bump 2.0.0 | Add `state_schema_version`; keep V1 dataset paths |
| Dataset registry | PK, time columns, status | `meta/dataset_registry.json` | PARTIAL | Future-info flag | Add `contains_future_information`; do not wipe required V1 rows |
| Feature registry | Versioned families | Absent | EXPECTED | Gate 1 | Create `meta/feature_registry.json` |
| Canonical games | Identity, scores, three timestamps | `games.csv` | PASS | Team / terminal labels | Keep |
| Canonical PBP | Event timestamps | Monthly CSV: scores, clock, type; **no `player_id`** | PARTIAL | Events, possessions, player state | Smallest extension: pass through NBA `pbp_live.personId` / `subType` / `shotResult`. Do not invent `timeActual`. |
| Kalshi candles | Integer E4, `available_at` = close | Monthly CSV, MAPPED only | PASS | Market state | Keep integers; observation ≠ fill |
| Team `*_pre` | Shift-then-roll by `result_available_at` | Implemented + leakage audit | PASS | Pre-game T_t | Keep; add in-game team state separately |
| D2D L1/L2 | I(d) snapshots | `d2d_daily.csv`, `team_game_features.csv` | PASS | Team state | Keep |
| `game_state()` | Latest PBP + candle | Ad-hoc dict; not a formal G_t | PARTIAL | Gate 3 assembler | Extend return; do not break V1 keys |
| Terminal labels | Future outcomes | `game_state_features.csv` `*_terminal`; **reachable via `dataset()`** | PARTIAL | Gate 4 | Tag `contains_future_information=true`; reject from public `dataset()` |
| `contains_future_information` | Registry + API reject | Absent | EXPECTED | Gate 1 | Add flag; reject in `public_filter` / `dataset()` |
| Possession engine | Absent in V1 | Absent | EXPECTED | Gate 2 | NBA reconstruct; other sports `NOT_SUPPORTED` |
| Player identity | Absent | Absent | EXPECTED | Gate 2 | `meta/players.csv`; no silent merge |
| Lineups | Absent | NBA warehouse has no starters | EXPECTED | Gate 3 | `INCOMPLETE`; never fabricate opening five |
| Feature versioning | Absent | Hardcoded columns | EXPECTED | Gate 1–3 | Registry, not scattered literals |
| Observation assembler | Absent | Absent | EXPECTED | Gate 3 | Query-time O_t; no giant CSV |
| Deterministic `observation_id` | Absent | Absent | EXPECTED | Gate 3/4 | Hash(game, cutoff, schema version) |
| Label API | Absent | Terminal CSV via dataset | EXPECTED | Gate 4 | `db.labels()` only |
| WNBA/NCAAB operational V1 | Games/PBP/candles/features | Implemented; NCAAB features P5-only | PASS | Capability matrix | Do not copy NBA player/possession assumptions |

## Warehouse capability (do not invent)

| Source | What exists | What does not |
|--------|-------------|---------------|
| NBA `pbp_live` | `personId`, `subType`, `shotResult`, `teamId`, `possession` (team id, not segment), `timeActual`, substitutions | Opening five / starter flag |
| NBA boxscore summary | Scores, `personId` on box players, inactives | Starter / on-court lineup |
| WNBA/NCAAB normalized plays | `wallclock`, scores, `type_text`, substitution **text** | `player_id`, team, possession |
| WNBA/NCAAB raw ESPN | participants, starters | Not in V1 canonical; V2 does not scrape new sources. Reading raw later is a recorded extension, not Gate 2. |

## Discrepancies V2 must record, not “fix” by invention

1. V1 PBP column is `event_timestamp`, not `event_time`. Keep V1 column; V2 events may alias `event_time = event_timestamp`.
2. V1 `game_state()` does not read `game_state_features.csv`. Keep that; terminal rows are future information.
3. `game_state_features` is in `roller.json` for NBA only; pipeline writes the file for all sports. Record; do not silently add WNBA/NCAAB map entries unless tests require it.
4. NCAAB `scheduled_start` is empty in the warehouse. V1 conservative proxy stays.
5. Draft V2 text that said `as_of == available_at` is visible is **rejected**. Equality stays hidden.

## Recommended Gate 1 actions

1. Keep V1 tests green.
2. Lock the half-open invariant in `docs/POINT_IN_TIME.md`.
3. Add metadata only: version, registries, `contains_future_information`, PIT reject for future datasets.
4. Do not start events/possessions until Gate 1 tests pass.
