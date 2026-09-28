# W4 data model

| Concept | Type | Notes |
|---------|------|--------|
| Market point | `MarketPoint` | Venue clock + integer cents; `None` = UNAVAILABLE |
| Market path | `MarketPath` | Time-ordered t_game observations + metadata |
| Completeness | `MarketCompleteness` | Minimum honest class |
| Observation kind | `MarketObservationKind` | TRADE / CANDLE_1M / REST_PIT_SNAPSHOT / … |
| Coupled episode | `CoupledMarketEpisode` | Two YES contracts; missing side explicit |
| Identity | `IdentityMapping` → `MarketIdentityStatus` | MATCHED / AMBIGUOUS / UNMATCHED; never guessed from clocks |
| Capability card | `MarketCapabilityCard` | Survives serialization; gates W12/W13-class research |
| Starting price | `StartingPriceClass` | W1; not first print |
| Lifetime | `LifetimeCoverage` | OPEN_TO_SETTLEMENT / SETTLEMENT_DAY_ONLY / UNKNOWN |
| Candle OHLC | `CandleOhlcCents` | Preserved from raw; still CANDLE_1M; never copied to bid/ask |

`MarketState` in narrative docs means the reconstructed `MarketPath` at a
point in time. This crate does not emit a separate `SynchronizedState`.
