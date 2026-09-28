# W6 architecture — Canonical MLB state engine

Research only. Does not modify production trading, Risk, or Kalshi execution.

`momento-research-state` wraps W3 PBP replay and emits immutable `GameState` /
`StateTransition` objects with deterministic fingerprints.

Time lookup: `state_at_or_before(T)` returns the latest timed state with
`canonical_timestamp <= T`, or `NO_STATE`. It never returns a future state.

W5 remains the market-sync owner. W6 does not import `momento-research-sync`.
W7 may join prices using `StateJoinKey` only.

See [../research/backtesting_rebuild/W6_STATE_ENGINE.md](../research/backtesting_rebuild/W6_STATE_ENGINE.md).
