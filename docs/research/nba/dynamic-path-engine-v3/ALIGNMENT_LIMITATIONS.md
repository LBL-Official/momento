# Alignment limitations

Copied from V2 inspection; not invented.

- PlayByPlayV3: period + game clock; **no** structured per-play wall clock.
- Period start/end descriptions embed local times (knots).
- Intra-period wall time is **modeled** (`PERIOD_BOUNDED_LINEAR_GAME_CLOCK`).
- Timeouts smear across the period. Replay residuals validate knots.
- `gameEt` is local clock incorrectly tagged `Z`.
- Tip is `gameTimeUTC`, never Kalshi market open.
- Contract time ≠ NBA game clock.

V3 post-entry snaps use the same model at each `state_timestamp`.
Alignment confidence is a **quality** label. It is **not** a preregistered
trading feature. The V2 HIGH vs MEDIUM entry-time q gap is investigated in
`ALIGNMENT_FORENSICS.md` as data-quality research only.
