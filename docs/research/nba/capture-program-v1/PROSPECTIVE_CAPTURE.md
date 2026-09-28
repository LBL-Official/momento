# Prospective capture design (not a subscriber)

How MLB-style Kalshi WebSocket streams **would** map onto Engine B **if**
a later milestone authorizes NBA paper or live collection.

This document does **not** add a WebSocket client, does not subscribe,
and does not change `apps/trading-engine`.

---

## What exists today (MLB live desk, not NBA warehouse)

Production live (MLB, triple-gated) already sees in-memory:

- `orderbook_snapshot` / `orderbook_delta`
- private `fill` channel
- host `audit.jsonl`
- fill-authoritative position tracker and `crates/pnl`

Research collector maps **1-minute candles** as `CANDLESTICK_ONLY`
orderbook events. Historical L2 for NBA: **UNAVAILABLE**.
`GET /historical/.../orderbook` is not used and must not be invented.

---

## Mapping if NBA capture is later authorized

| WS / private event | Engine B `event_type` | Status if recorded |
| --- | --- | --- |
| Public ticker quote / trade | `MARKET_BEFORE_ENTRY` or `POST_ENTRY_PATH_SAMPLE` | OBSERVED |
| `orderbook_snapshot` / `delta` while resting | `BOOK_DURING_REST` | OBSERVED |
| Client send | `ORDER_SUBMITTED` | OBSERVED |
| Exchange ack/reject | `ORDER_ACKNOWLEDGED` | OBSERVED |
| Private fill | `FILL` or `STOP_FILL` | OBSERVED |
| Cancel / expire without fill | `NO_FILL` | OBSERVED |
| Bid/ask first crossing stop trigger | `STOP_TOUCH` | OBSERVED (trigger ≠ fill) |
| Settlement / determined market | `SETTLEMENT` | OBSERVED |
| Exchange fee field on fill | fee on `FILL` / `NET_REALIZED_PNL` | OBSERVED |
| No fee field | fee | UNAVAILABLE (do not invent KalshiFeeModel) |

Paper/unarmed NBA: write the same episode types with
`UNAVAILABLE` for private fills and L2. Valid.

---

## What must remain true

- Strategy proposes → Risk approves → execution submits.
- Submit ≠ fill.
- UNKNOWN order state → reconcile; do not double.
- No live NBA until an explicit milestone adds a strategy, Risk wiring,
  and the triple live gate.
