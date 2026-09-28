# V4C future microstructure (declared only)

This document does not authorize estimators.

The current NBA warehouse provides 1-minute OHLC candles. There is no historical L2, trade-tick tape, or second snapshot store.

V4C therefore registers:

| Object | Status | Required regime |
|--------|--------|-----------------|
| `microprice` | `NOT_CONSTRUCTIBLE` | `FULL_ORDER_BOOK` |
| `order_book_imbalance` | `NOT_CONSTRUCTIBLE` | `FULL_ORDER_BOOK` |
| `price_impact_lambda` | `NOT_CONSTRUCTIBLE` | `FULL_ORDER_BOOK` |
| `signed_flow_lambda` | `NOT_CONSTRUCTIBLE` | `TRADE_TICK` |
| `psi_resilience` | `NOT_CONSTRUCTIBLE` | `FULL_ORDER_BOOK` |
| `market_delta_1s` | `NOT_YET_IMPLEMENTED` | `SECOND_SNAPSHOT` |
| `sigma_K` | `NOT_YET_IMPLEMENTED` | `TRADE_TICK` |

Prohibited substitutes are stored on each registry row under `not`.

Gates 4–6 (new candle estimators, event/possession Greeks, second-level/book objects) are deferred. Architecture existence is not measurement authorization.
