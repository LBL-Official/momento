# ADR-0008 — Orderbook representation

# Decision

Orderbook fields are stored only when historically observed. Missing L2 is
`UNAVAILABLE`. Candles are not books. Point-in-time REST snapshots taken at
collection time are not game-time L2.

# Context

Kalshi does not sell archived WebSocket L2. LEGACY collector stores 1-minute
candlestick close bid/ask in a type named `OrderbookEvent`, plus a REST snapshot
at backfill time. Research execution correctly refuses maker simulation on
`CANDLESTICK_ONLY`.

# Problem

Naming candles as orderbook and mixing ingest-time snapshots into historical
paths fabricates liquidity, queue, and fill probability.

# Alternatives Considered

1. Interpolate L2 between trades or from candle OHLC.
2. Treat last trade as bid.
3. Preserve observed fields only; classify observability explicitly.

# Decision Made

Alternative 3. Where source supports it, preserve: best bid/ask, spread, sizes,
depth, trades, cancellations, replenishment, imbalance, velocity, acceleration,
liquidity changes, market-state transitions.

Where it does not: mark UNAVAILABLE. Never fabricate.

Observability / execution quality:

```text
FULL_L2 | TOP_OF_BOOK_ONLY | CANDLESTICK_ONLY | NO_EXECUTION_DATA
```

PIT REST `RestSnapshot` is OBSERVED as-of ingest, UNAVAILABLE as historical book.
Candle minute OHLC present in raw gzip but dropped in normalize v1 must be
catalogued as present-in-raw, absent-in-v1.

# Rationale

Maker-fill claims require book quality that history does not have.

# Consequences

Schema 1.0.0 is frozen (WRAP). New normalize version carries observability on
every row. Prospective WS capture is forward-only after authorization.

# Data/Model Implications

Execution models on candles are MODELED and currently unsupported for fills.
Features needing depth are unavailable historically.

# Testing Implications

no_synthetic_rows; candles not labeled `l2_snapshot`; mixing one snapshot must
not upgrade a day to FULL_L2.

# Future Compatibility

Live WS capture can populate FULL_L2 going forward without rewriting June gzip.

# Status

ACCEPTED

# Date

2026-08-26
