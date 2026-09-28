# Live episode ledger schema

Engine B. Append-only. One row (and one JSON episode) per attempted trade.

Code: `apps/nba-data/scripts/capture_program_v1/schema/`
Warehouse: `.../momento_capture_program_v1/live_ledger/`

Initially **empty**. Do not fabricate episodes.

---

## Observation status

Every value carries exactly one of:

```text
OBSERVED      exchange or system recorded it
ESTIMATED     inferred from candles or a published formula
SIMULATED     generated from an assumption
UNAVAILABLE   not currently observable
```

Promotion is forbidden:

```text
UNAVAILABLE ↛ SIMULATED ↛ ESTIMATED ↛ OBSERVED
```

Examples:

| Quantity | Status |
| --- | --- |
| Historical FIRST-80 survival | OBSERVED candle path |
| Historical maker fill at 80 | UNAVAILABLE |
| Fill-probability stress | SIMULATED |
| Future live maker fill | OBSERVED once executed |

---

## Required columns (parquet + JSON)

```text
episode_id
strategy_version
market_ticker
game_date
team
side

signal_timestamp
signal_price
signal_bid
signal_ask

entry_order_timestamp
entry_order_price
entry_order_size

entry_status
entry_fill_timestamp
entry_fill_price
entry_fill_quantity

remaining_quantity

stop_trigger_timestamp
stop_trigger_price

stop_order_timestamp
stop_order_type
stop_order_price

stop_fill_timestamp
stop_fill_price
stop_fill_quantity

settlement_price

gross_pnl
fees
slippage
net_pnl

max_favorable_price
max_adverse_price

episode_status
data_confidence
```

Each economic field also stores `*_status` in `{OBSERVED, ESTIMATED,
SIMULATED, UNAVAILABLE}`.

JSON episodes additionally append the event taxonomy in
[ENGINE_B_LEDGER.md](ENGINE_B_LEDGER.md):

```text
SIGNAL → ORDER SUBMITTED → QUEUE / REST
  → PARTIAL FILL → FULL FILL → POST-ENTRY PATH
  → STOP TRIGGER → STOP EXECUTION → SETTLEMENT → NET P&L
```

`STOP_TOUCH` ≠ `STOP_FILL`. A 1-minute wick is at most `STOP_TOUCH` with
`ESTIMATED` status.

---

## Intended future payloads (UNAVAILABLE until collected)

L2 snapshots, order acknowledgements, fill events, trade prints, best
bid/ask, order status, partial fills, cancellations, fees.

If unavailable: write `UNAVAILABLE`. Do not estimate silently.

---

## Leakage

- Do not use settlement to classify a fill.
- Do not use future candles to upgrade entry confidence.
- Same-bar 1-minute limitation: `SAME_BAR_1M_LIMITATION`.
- `live_armed` must be `false` in this milestone.
