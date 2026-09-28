# W1 Observability Specification

Never silently upgrade a category.

| Kind | Use |
|------|-----|
| OBSERVED | In immutable raw (with true source semantics) |
| DERIVED | Deterministic, no lookahead (e.g. spread later) |
| INFERRED | Joins that can be wrong (not used as lake truth in W1) |
| MODELED | Simulation (fills, theta) — not W1 lake |
| UNAVAILABLE | Missing; null + reason |
| L2_HISTORICAL_UNAVAILABLE | Historical order-book depth |
| OUTCOME_LABEL | Settlement/winner — not a feature at t |

Kalshi field semantics:

- trade print → OBSERVED trade, not a quote tick
- candle bid/ask close → OBSERVED **candle**, not tick, not L2
- size on candles → UNAVAILABLE
- ingest REST book → OBSERVED at ingest; L2_HISTORICAL_UNAVAILABLE as game-time book
- mid → UNAVAILABLE (not a venue field)
