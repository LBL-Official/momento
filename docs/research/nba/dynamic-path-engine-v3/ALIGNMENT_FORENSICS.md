# ALIGNMENT FORENSICS

Data-quality research on the V2 HIGH vs MEDIUM barrier-rate gap.
This is **not** a trading filter. Alignment confidence is a quality label.

## V2 published numbers (frozen)

| Confidence | n | q |
| --- | ---: | ---: |
| HIGH | 955 | 23.14% |
| MEDIUM | 214 | 41.12% |
| LOW | 3 | 66.67% |
| UNUSABLE | 58 | 15.52% |

## Recomputed slices

| Slice | n | k | q |
| --- | ---: | ---: | ---: |
| HIGH | 955 | 221 | 23.14% |
| MEDIUM | 214 | 88 | 41.12% |
| MEDIUM_replay_residual | 190 | 81 | 42.63% |
| MEDIUM_intermission | 13 | 2 | 15.38% |
| MEDIUM_game_not_started | 11 | 5 | 45.45% |
| HIGH_replay_validated | 671 | 162 | 24.14% |
| HIGH_in_period_bounds | 284 | 59 | 20.77% |
| all_high_replay_residual_flag | 236 | 93 | 39.41% |
| all_unusual_tip | 42 | 14 | 33.33% |
| all_ot_duration_proxy | 1221 | 316 | 25.88% |
| MEDIUM_excluding_replay_residual | 24 | 7 | 29.17% |

## By alignment reason

| Reason | n | q |
| --- | ---: | ---: |
| IN_PERIOD_REPLAY_VALIDATED | 671 | 24.14% |
| IN_PERIOD_BOUNDS | 284 | 20.77% |
| IN_PERIOD_REPLAY_RESIDUAL | 190 | 42.63% |
| ENTRY_OUTSIDE_GAME_WINDOW | 51 | 11.76% |
| INTERMISSION | 13 | 15.38% |
| GAME_NOT_STARTED | 11 | 45.45% |
| UNMATCHED_CROSSWALK | 7 | 42.86% |
| MISSING_PERIOD_STAMPS | 2 | 50.00% |
| INCOMPLETE_BOUNDS | 1 | 100.00% |

## In-period replay residual buckets

| Residual | n | q |
| --- | ---: | ---: |
| <=60s | 289 | 19.72% |
| 61-180s | 569 | 25.13% |
| >180s | 226 | 39.38% |
| missing | 62 | 22.58% |

## Composition

MEDIUM n=214; IN_PERIOD_REPLAY_RESIDUAL share=88.8% (190). Remaining MEDIUM is intermission / game-not-started / other.

HIGH is almost entirely IN_PERIOD_REPLAY_VALIDATED or IN_PERIOD_BOUNDS.
The strata are therefore not comparable basketball states; they are clock-quality strata.

## Candidate explanations

- Overtime duration proxy (modeled Q1-start→last-end > 50 minutes): see slices.
- Unusual tip→Q1 lag (|lag−720s| > 300s): see slices.
- Delayed / missing knots: LOW/UNUSABLE and MISSING_PERIOD_STAMPS.
- Timestamp reconstruction: replay residual > 180s is the MEDIUM definition for in-period games.
- Specific dates: month table in JSON.

## Conclusion

**A — likely data artifact.**

MEDIUM is not a random subsample of first-80 games. It is concentrated in replay-residual, intermission, and pre-tip alignment. Those labels mean the modeled wall clock is less trustworthy. A higher barrier rate in a poorly timestamped stratum can be produced by snapping the market to the wrong game state (or to no game state). That is not evidence that 'medium alignment' is an economically interpretable basketball regime.

We do **not** promote excluding MEDIUM as a trading filter. Quality labels were not preregistered as features. The residual vs validated in-period gap remains a reconstruction issue, not a demonstrated live edge.

Generated 2026-09-01T19:09:10.836643+00:00

