# W4 capability matrix (downstream gates)

**Rule:** NO L2 = DO NOT INVENT L2.

**TRADES_ONLY is not a failed dataset.** It is a valid historical price-path
research universe with intentionally limited capabilities.

The historical universe is:

```text
broad price-path research universe
        +
narrower orderbook universe
        +
narrower maker-execution universe
```

Do not block W7/W8 price-path research merely because L2 is unavailable.

Ingest `MAPPED` with observed `game_pk` is **`MATCHED`**. Identity is never guessed.

| Capability | L2_COMPLETE | L2_PARTIAL | TRADES_ONLY | CANDLES_ONLY | METADATA_ONLY / UNOBSERVED |
|---|---|---|---|---|---|
| PRICE_PATH_RESEARCH | ALLOWED | ALLOWED | **ALLOWED** | CONDITIONAL | BLOCKED |
| ORDERBOOK_MICROSTRUCTURE | ALLOWED | CONDITIONAL | **BLOCKED** | BLOCKED | BLOCKED |
| MAKER_FILL_SIMULATION | ALLOWED | BLOCKED | **BLOCKED** | BLOCKED | BLOCKED |

| Identity | GAME_ID_LINKED_RESEARCH (W5+ sync) |
|---|---|
| MATCHED | ALLOWED (does not implement sync) |
| AMBIGUOUS | BLOCKED (record retained) |
| UNMATCHED | BLOCKED (record retained) |

`TRADES_ONLY` may join GameId-linked research **only when identity is MATCHED**.
Today all reconstructed TRADES_ONLY paths are UNMATCHED.

TRADES_ONLY **must not** be represented as bid, ask, spread, depth, queue,
maker fill probability, L2 liquidity, or executable price.

API: `chronological_trades`, `observations_as_of`, `request_orderbook_microstructure`
(fail-closed), `request_maker_fill_simulation` (fail-closed), `synthetic_bid_ask`
(always fail-closed).
