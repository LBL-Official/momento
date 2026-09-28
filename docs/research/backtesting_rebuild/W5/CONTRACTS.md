# CTO-W5 CONTRACTS

**When implemented**, W5 owns:

- Synchronization confidence enum (ADR-0003 vocabulary)
- `time_delta` / method / both clocks
- Join quality report

**Reserved downstream** (not W5 implementation now):

- Canonical `StateTransition`
- `GameMarketEpisode` container
- Threshold first-touch tables
- Denormalized full-prefix `S(t)` encoding

**Consumed:**

- W2/W3 `MlbGameState` + PBP sequence
- W4 `MarketPath` / `CoupledMarketEpisode`
- W1 `StartingPriceClass`, `ObservabilityKind`

**Forbidden:** forking GameState; suffix-match identity; treating candles as L2;
using `received_at` as exchange time; inventing PBP times from trades.
