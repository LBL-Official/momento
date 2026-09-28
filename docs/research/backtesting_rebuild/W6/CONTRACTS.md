# CTO-W6 CONTRACTS

Owned:

- `GameState` (immutable snapshot after event n, including explicit pre-game n=0)
- `StateTransition` (previous + event + resulting)
- `state_at_or_before(T)` / `NO_STATE`
- state and transition fingerprints
- `StateJoinKey` for W7 (no prices)

Consumed:

- W3 `CanonicalMlbEvent`, `OfficialMlbGameRef`, `replay()`
- W2 `CanonicalGameId`

Reserved downstream: `GameMarketEpisode`, price paths, FIRST01 opportunity types.
