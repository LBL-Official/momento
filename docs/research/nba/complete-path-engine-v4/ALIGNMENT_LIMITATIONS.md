# Alignment limitations

Same as V2/V3. Not invented.

- PlayByPlayV3: period + game clock; **no** structured per-play wall clock.
- Intra-period wall time is modeled (`PERIOD_BOUNDED_LINEAR_GAME_CLOCK`).
- Tip is `gameTimeUTC`, never Kalshi market open.
- Contract time ≠ NBA game clock.
- V2 HIGH vs MEDIUM q-gap is a **data-quality** finding (V3 forensics: likely artifact). Confidence is not a V4 trading feature.

Game-path curves are UNAVAILABLE when alignment is not HIGH or MEDIUM at first-80.
Those trades remain in the market-path analysis.
