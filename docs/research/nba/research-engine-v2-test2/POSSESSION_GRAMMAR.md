# Possession grammar

A possession is a contiguous sequence of PBP actions during which one team
has offensive control. Sequence is **OBSERVED** (PlayByPlayV3 order).
Wall start/end attached via GPE V2 `PERIOD_BOUNDED_LINEAR_GAME_CLOCK` are
**DERIVED PROXY**, never claimed as `timeActual`.

## Start

- Period start / jump ball
- After a possession-ending event, next action with an offensive team

## End (not an offensive rebound)

- Made field goal (and-1 free throws remain on the same possession)
- Defensive rebound (rebound team ≠ shooting team; team rebounds parsed from description)
- Turnover
- Period end
- Jump ball that awards the other team

## Continue

- Missed shot + offensive rebound
- Non-shooting fouls, substitutions, timeouts, violations that do not change control
- Technical free throws (documented; not a new live-ball possession)

## Validation (must not silently drop)

- Duplicate `possession_id`
- Missing period coverage
- Impossible score jumps (>4 points without FTs documented)
- Non-monotonic official clocks within a period (except clock resets / replay)
- Unmapped `actionType`
- Unmatched Kalshi↔NBA crosswalk
