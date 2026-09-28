# CTO-W6 DEPENDENCIES

## Upstream

- W2 canonical GameId + event identity
- W3 ingest/replay/state machine (`CanonicalMlbEvent`, `MlbGameState::replay`)
- DATA-INGEST StatsAPI landing envelopes

## Downstream (not this grant)

- W5 already joins market observations to W3 timed events; it can later
  consume W6 `state_at_or_before` without W6 depending on W5.
- W7 market price paths attach via join keys only.

## Must not depend on

Kalshi network, risk, execution, strategy, FIRST01, research-sync.
