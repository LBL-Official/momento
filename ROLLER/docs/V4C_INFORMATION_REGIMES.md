# V4C information regimes

Regimes are information modalities, not a linear quality ladder.

```text
CANDLE_1M
EVENT_SEQUENCE
POSSESSION_STATE
TRADE_TICK
SECOND_SNAPSHOT
FULL_ORDER_BOOK
```

`EVENT_SEQUENCE` may contain information unavailable in `SECOND_SNAPSHOT`. `FULL_ORDER_BOOK` does not encode a complete basketball event sequence.

Resolution is a separate field:

```text
60_SECOND_CANDLE
1_SECOND
EVENT_TIMESTAMP
TRADE_TIMESTAMP
BOOK_SNAPSHOT
```

Only `CANDLE_1M` is active in V4C. Other regimes are declared so future layers cannot collapse them into "higher resolution candles."

## Clocks

These clocks stay independent. Do not collapse them to `timestamp`.

```text
state_available_at
candle_available_at
measurement_available_at
event_available_at
trade_available_at
book_snapshot_available_at
```

```text
event occurrence time
    ≠ source publication time
    ≠ database availability time
    ≠ measurement availability time
```

V4C copies known V4B clocks and leaves future-regime clocks explicitly null. It does not compute event, trade, or book availability.
