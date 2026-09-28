# Kalshi adapter (Milestone 4)

Official documentation inspected (2026-08-24):

- [API Keys](https://docs.kalshi.com/getting_started/api_keys)
- [Authenticated requests](https://docs.kalshi.com/getting_started/quick_start_authenticated_requests)
- [Create first order](https://docs.kalshi.com/getting_started/quick_start_create_order)
- [Create Order V2](https://docs.kalshi.com/api-reference/orders/create-order-v2)
- [Get Order](https://docs.kalshi.com/api-reference/orders/get-order)
- [Get Orders](https://docs.kalshi.com/api-reference/orders/get-orders)
- [Cancel Order V2](https://docs.kalshi.com/api-reference/orders/cancel-order-v2)
- [Get Market](https://docs.kalshi.com/api-reference/market/get-market)
- [Get Markets](https://docs.kalshi.com/api-reference/market/get-markets)
- [Fixed-point prices](https://docs.kalshi.com/getting_started/fixed_point_migration)
- [Orderbook responses](https://docs.kalshi.com/getting_started/orderbook_responses)
- [Market ticker (WebSocket)](https://docs.kalshi.com/websockets/market-ticker)
- [Fee rounding](https://docs.kalshi.com/getting_started/fee_rounding)
- [Series fee changes](https://docs.kalshi.com/api-reference/exchange/get-series-fee-changes)
- [Market settlement](https://docs.kalshi.com/getting_started/market_settlement)
- [WebSockets](https://docs.kalshi.com/getting_started/quick_start_websockets)
- [WebSocket connection](https://docs.kalshi.com/websockets/websocket-connection)
- [Orderbook updates](https://docs.kalshi.com/websockets/orderbook-updates)
- [API environments](https://docs.kalshi.com/getting_started/api_environments)

M4 implements **mapping + fail-closed adapter tests**.

M8 adds **demo/sandbox HTTP + WebSocket** against official demo hosts only.

M9 stores production credentials in AWS Secrets Manager and allows
**read-only** production authentication (`GET /exchange/status`,
`GET /portfolio/balance`, `GET /markets`). Create/cancel/amend remain locally
refused on the read-only transport and are never sent.

## M10 live arming

Live trading requires **all** of:

1. Production order submission via `ProductionTradingTransport` (post-only
   GTC entry, reduce-only IOC liquidation, cancel, and reads).
2. `config/live.toml`: `mode = "live"`, `live.enabled = true`,
   `live.confirmation = "ENABLE_LIVE_TRADING"`.
3. Point the trading engine at that config (`MOMENTO_CONFIG`). Do not infer
   live from keys, hostname, or Secrets Manager.

Immediate disable (kill switch / stop live):

1. `sudo systemctl stop momento-live.service`
2. Optional: `sudo touch /var/lib/momento/state/KILL` then the running
   process blocks new entry without flattening.
3. Presence of the Secrets Manager secret must not restart live trading.

The paper unit (`momento-paper.service`) must be stopped before the live
unit starts. They conflict and must not share a live loop.

Kalshi adapter `mid` remains `None` (Kalshi has no official mid). MLB 80/81/89
observes `yes_bid_dollars` via `MarketEvent.bid`. That is not a synthetic mid
and is not `(bid+ask)/2`. Last and ask are never the qualifying observation.

## Verified hosts

| Environment | REST | WebSocket |
|---|---|---|
| Production | `https://external-api.kalshi.com/trade-api/v2` | `wss://external-api-ws.kalshi.com/trade-api/ws/v2` |
| Demo | `https://external-api.demo.kalshi.co/trade-api/v2` | `wss://external-api-ws.demo.kalshi.co/trade-api/ws/v2` |
| Demo (also supported, M8 default) | `https://demo-api.kalshi.co/trade-api/v2` | `wss://demo-api.kalshi.co/trade-api/ws/v2` |

## Verified authentication

Every private REST request and the WebSocket handshake uses:

- `KALSHI-ACCESS-KEY` — API key ID
- `KALSHI-ACCESS-TIMESTAMP` — unix milliseconds
- `KALSHI-ACCESS-SIGNATURE` — RSA-PSS SHA256 over `timestamp + METHOD + path` with query string stripped

WebSocket sign path is exactly `/trade-api/ws/v2` with method `GET`.

M4 does **not** load keys or compute signatures. It only encodes the official payload string.

Environment-variable *names* for a later milestone (no values, no files):

- `MOMENTO_KALSHI_API_KEY_ID`
- `MOMENTO_KALSHI_PRIVATE_KEY_PATH`

Presence of those names must never arm live mode.

## Verified order API

- Create (event markets): `POST /portfolio/events/orders`
- Get: `GET /portfolio/orders/{order_id}`
- List: `GET /portfolio/orders` (`status` filter: `resting`, `canceled`, `executed`)
- Cancel: `DELETE /portfolio/events/orders/{order_id}`
- Idempotency: optional `client_order_id`; duplicate → HTTP `409`
- Create TIF: `good_till_canceled`, `immediate_or_cancel`, `fill_or_kill`
- `post_only`: boolean; never takes liquidity if set
- `reduce_only`: caps size by current position
- Book side: `bid` = buy YES, `ask` = sell YES
- Prices: fixed-point dollars (`"0.8000"`)
- Quantity: fixed-point count (`"3.00"`), venue minimum granularity **0.01 contracts**
- Create V2 response includes `order_id`, `fill_count`, `remaining_count`, `ts_ms`

GET Order `type` enum includes `limit` and `market`. Create V2 has **no** `type` field. Aggressive execution that is documented is TIF (`IOC`/`FOK`) plus optional `reduce_only`, not an invented “market order” helper.

## Verified order status

Official `OrderStatus`: `resting` | `canceled` | `executed`.

There is **no** `partially_filled` status. Partial fills are `fill_count_fp` vs `remaining_count_fp` while status remains `resting`.

Domain mapping:

| Kalshi | Domain |
|---|---|
| `resting`, filled=0 | `WORKING` |
| `resting`, filled>0, remaining>0 | `PARTIALLY_FILLED` |
| `executed`, remaining=0 | `FILLED` |
| `canceled` | `CANCELLED` |
| HTTP 400 on create | `REJECTED` |
| HTTP timeout / unknown status string | `UNKNOWN` (fail closed; never FILLED/CANCELLED/FAILED) |

HTTP 401 is authentication failure, **not** an order reject and **not** an automatic retry.

Timeout after submit is `UNKNOWN`. The adapter **must not** automatically retry. Reconcile via GET.

Create V2 HTTP 404 (including Kalshi `user_not_found`) is a venue **reject**: the order was
not created. It is not `UNKNOWN`.

Reconcile without a venue order id searches official live list filters
`status=resting|canceled|executed` with cursor pagination. Complete absence is
`NOT_FOUND`. A timeout, truncated page, or order older than
`GET /historical/cutoff` `orders_updated_ts` stays `AMBIGUOUS`.
Cutoff timestamps are unix seconds after parse; production payloads have been
observed as RFC3339 strings (`2026-06-28T00:00:00Z`), not only integers.

## Identity

- `ClientOrderId` is encoded as 128-bit hyphenated hex (UUID layout) in `client_order_id`.
- Kalshi `order_id` maps to `VenueOrderId` the same way.
- Ticker → `MarketId`/`GameId`/`PositionId` is an injected lookup.
- The adapter **never** calls `PositionId::generate()`.

## Market data

GET `/markets` and GET `/markets/{ticker}` (inspected 2026-08-24 against current
official schema and a public production `KXMLBGAME` payload) provide:

| Field | Official meaning |
|---|---|
| `yes_bid_dollars` | Highest YES **buy** offer (best bid), fixed-point dollars |
| `yes_ask_dollars` | Lowest YES **sell** offer (best ask), fixed-point dollars |
| `no_bid_dollars` / `no_ask_dollars` | Complementary NO book (YES + NO sides sum to $1.00 on the inspected MLB quote) |
| `last_price_dollars` | Last traded YES price. Not a quote. May sit outside the current bid/ask. |
| `price_ranges[].step` | Source of truth for tick size |
| `price_level_structure` | Human-readable grid label only (`linear_cent` on inspected MLB) |

**There is no official `mid` field** on REST Market, Get Markets, WebSocket
`ticker`, or the orderbook payload. Docs never establish `(bid+ask)/2` as the
authoritative market price. Adapter continues to leave `mid = None`. Do not
map last, bid, or ask into `MarketEvent.mid`.

MLB strategy spec (2026-08-24): qualifying observation is `yes_bid_dollars`
mapped to `VenueMarketSnapshot.bid` / `MarketEvent.bid`. Ask is maker-only
constraint only. Last is never the 80/81/89 input.

WebSocket channels (connection itself requires auth): `orderbook_delta`, `ticker`, `trade`, `fill`, `user_orders`, `market_positions`, `market_lifecycle_v2`, …

Production live market data (same MLB algorithm; transport only):

- Connect to production `wss://external-api-ws.kalshi.com/trade-api/ws/v2` with the
  existing Secrets Manager RSA-PSS headers.
- Subscribe `orderbook_delta` for currently open `KXMLBGAME` markets only.
- Subscribe private `fill` (no market filter; authenticated fills only).
- Maintain a local book from `orderbook_snapshot` then `orderbook_delta`.
- MLB observation is **best YES bid** from that book. Implied YES ask is
  `$1 − best NO bid` (official binary-book complementarity). Not last, not mid.
- Sequence gap → fail closed, drop the socket, reconnect, resubscribe. Do not
  flatten. New entry waits until the book is valid again.
- REST remains for discovery, bootstrap timestamps, held-position settlement,
  order reconciliation, and fill fallback.

Seq/sid duplicate suppression exists. Reconnect rebuilds the book from a fresh
snapshot rather than inventing gap-fill.

## Fees

Official:

- Series `fee_type`: `quadratic`, `quadratic_with_maker_fees`, `quadratic_with_combo_maker_fees`, `flat` plus `fee_multiplier` (`GET /series/fee_changes`).
- Event overrides exist (`GET /events/{ticker}/fee_changes` in the docs index).
- Fee rounding: trade fee ceiled to $0.0001, plus rounding fee and rebate accumulator ([fee rounding](https://docs.kalshi.com/getting_started/fee_rounding)).
- Create response may include `average_fee_paid` when `fill_count > 0`.
- Order object includes `taker_fees_dollars` / `maker_fees_dollars`.

**UNRESOLVED:** exact quadratic formula and inputs needed to *estimate* fees before a fill. M4 does **not** implement `KalshiFeeModel`. `FeeModel` stays injected. `ZeroFeeModel` remains paper-only.

Sub-cent fees cannot map into integer-cent `Money`. Observed fee strings stay venue-side until that domain gap is closed.

## Stop / liquidation

Official Create V2 reduction (no market-order endpoint):

- `side=ask` (sell YES)
- `reduce_only=true`
- `post_only=false`
- `time_in_force=immediate_or_cancel` (partial liquidation is allowed; not FOK)
- limit price = current best YES bid from `GET /markets/{ticker}/orderbook`
  (`orderbook_fp.yes_dollars` last level). If the book is empty, the host
  falls back to the YES bid that triggered the stop.

Immediate create `fill_count` is not mapped into a domain `Fill`. Fills
come from fill ingest. IOC remainder is reconciled via GET order (`canceled`).

50% stop uses VWAP of actual entry fills (`ProposedHalfEntryStop`: integer
division of hundredths of a cent). 89% GAME_LOCK does not liquidate.

## Settlement

Verified: winning YES or NO contracts receive $1 per contract; only net positions settle; settlement timing varies; simple yes/no settlement fees are documented as zero, scalar settlement may differ.

Adapter maps `result=yes|no` and `settlement_value_dollars` when they are whole cents. `scalar` fails closed.

## Paper vs Kalshi

```text
Execution ── PaperVenue     (deterministic, M3)
          └── KalshiVenue   (mapping + production Create V2 when live-armed)
```

Paper execution is unchanged.

## Tick size

Valid prices are per-market `price_ranges` (`start`, `end`, `step`). Structures include `linear_cent` ($0.01) and several sub-cent grids.

Domain `Price` is integer cents. Sub-cent venue prices fail closed in M4.
