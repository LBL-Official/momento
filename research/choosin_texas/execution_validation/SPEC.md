# PAIRED_EXECUTION_VALIDATION_V1

Frozen at 2026-09-25T07:06:27+00:00. Configuration `PLANNED_RISK_CAP3`.
This file is research. It does not arm a book.

## Established

- entry_signal: Existing ledger timestamp. That second is the minute-close when the candle book marks entry.
- earliest_order_submission: The entry or stop signal timestamp. No order is eligible before that close is observable.
- entry_side_and_price: Buy YES at 80 cents. Nominal price. The candle close bid may differ.
- post_only_intent: The research description is a maker entry and a maker exit.
- stop_detection: First later minute whose yes bid close is at or below 40 or 65. Detection is not an order.
- settlement: Candle survivors are marked at 100 cents in the benchmark. That mark is not an exchange fill of our order.
- taker_fallback: NOT_AUTHORIZED
- opponent_hedge: NOT_AUTHORIZED
- position_cap: Three open slots across sports and slices. A pending entry occupies a slot.

## Missing

- Latency after the candle close. No game-time local receive clock is in the historical files.
- Order lifetime and the cancellation clock.
- Queue position. A trade at our price is not a fill.
- Exit order price after the stop print: the stop level versus the observed bid.
- Repricing.
- Partial-fill priority across the two books. Accounting rules exist for a later replay. They are not applied to historical P&L.
- A fee schedule whose effective dates cover every historical entry.

Canonical net return: NOT_PUBLISHED.
Execution-aware portfolio P&L: NOT_REPORTED.
Reference label: CANDLE_PATH_NOT_FILL.
