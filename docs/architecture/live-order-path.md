# Live MLB order path (simple)

Personal reference for how a **production entry** reaches Kalshi.

Strategy proposes. Risk approves. Venue submits. Nothing bypasses that.

An **accepted resting order is not a fill**. Maker GTC can sit on the book
until someone trades against it. That is expected.

---

## Big picture

```text
Kalshi production WebSocket
        │
        ▼
  Local order book
  (best YES bid)
        │
        ▼
  MLB 80 → 81 signal
        │
        ▼
  maker_limit (80–83¢, below ask)
        │
        ▼
  TradeIntent
        │
        ▼
  Risk.decide_entry
  ($6.25 / game, max 5 positions,
   kill switch, UNKNOWN block)
        │
        ▼
  ApprovedTradeIntent
        │
        ▼
  submit_approved
        │
        ▼
  KalshiVenue::submit_post_only
  signed POST Create Order V2
        │
        ▼
  Kalshi response
  (ack / reject / UNKNOWN)
```

---

## Strategy signal (what “natural 80→81” means)

Observation is **best YES bid only** — not last, not ask, not mid.

```text
YES bid rises
      │
      ├─ bid < 80¢ ──────────────► keep watching
      │
      ├─ first bid ≥ 80¢ ────────► remember first_80 (side + market)
      │
      ├─ same side reaches ≥ 81¢ ► confirmed_81
      │
      ├─ bid ≥ 89¢ ──────────────► GAME_LOCKED (no new entry; does not flatten)
      │
      └─ confirmed + still in band
               │
               ▼
         maker_limit()
               │
               ├─ not in 80–83¢ ─────────► no entry
               ├─ limit ≥ YES ask ───────► no entry (never cross)
               └─ ok ────────────────────► TradeIntent (maker-only)
```

Limit price joins the current YES bid in **80–83¢ inclusive**, strictly
**below** the current YES ask. Max 83 is a ceiling, not a target. Never chase.

---

## Risk gate (before any POST)

```text
TradeIntent
      │
      ▼
Risk.decide_entry
      │
      ├─ kill switch tripped ─────────────► reject
      ├─ UNKNOWN / recon required ───────► reject
      ├─ price outside 80–83¢ ───────────► reject
      ├─ game budget exceeded ($6.25) ───► reject
      ├─ already 5 open MLB slots ───────► reject
      └─ ok ─────────────────────────────► ApprovedTradeIntent
                                              (+ new ClientOrderId)
```

Strategy cannot submit. Only an approved intent may call the venue.

---

## Production HTTP (what gets sent)

```text
POST /trade-api/v2/portfolio/events/orders
  side            = bid
  price           = 0.80xx … 0.83xx
  count           = N.00
  time_in_force   = good_till_canceled
  post_only       = true
  reduce_only     = false
```

Signed with production RSA-PSS credentials from the live secret mechanism.

### Response handling (fail closed)

| Kalshi result | Momento behavior |
|---|---|
| 200/201 + `order_id`, no immediate fill | Order **working** (may rest) |
| 200/201 but immediate fill on post-only create | Fail closed — not treated as “resting” |
| 400 | Rejected; reservation released |
| 404 (`user_not_found` or other create 404) | Rejected; order was not created; reservation released |
| Timeout or 409 | **UNKNOWN** — no blind retry; blocks new exposure until recon |

Reconcile of an unknown create (no venue `order_id`) uses `GET /historical/cutoff`
then live `GET /portfolio/orders` by `resting|canceled|executed`. Complete
absence after a parsed cutoff that does not hide the order is `NOT_FOUND`
(reservation released). Cutoff parse failure, list timeout, or a cutoff that
hides the order stays **UNKNOWN** / ambiguous — new entries remain blocked.

---

## What is proven vs what is waiting

| Proven | Still waiting on the world |
|---|---|
| Code path WS → Risk → signed Create V2 | A real market walking 80 → 81 |
| Request shape and live arming | Kalshi’s first natural ack/reject |
| Safety gates (budget, cap, kill, UNKNOWN) | A later **fill** (separate from ack) |

Do not invent a synthetic production order to “prove” this. The first real
qualifying signal is the test.

---

## Code map (if you need to re-read)

| Step | Where |
|---|---|
| Book YES bid / ask | `crates/kalshi/src/book.rs` |
| WS → observe | `apps/trading-engine/src/live.rs` |
| 80/81/89 + maker | `strategies/mlb/src/quote.rs`, `strategy.rs` |
| Risk | `crates/risk/src/engine.rs` |
| Submit + Create V2 | `live.rs` `submit_approved`, `crates/kalshi/src/venue.rs` `submit_post_only` |
| Sign | `crates/kalshi/src/http.rs`, `auth.rs` |
