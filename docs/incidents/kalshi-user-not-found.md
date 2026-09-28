# Incident: Kalshi Create V2 `404 user_not_found` (MLB vs WNBA)

**Verdict: ROOT CAUSE EXTERNAL**

The Create V2 request path, signing path, credentials, host, and payload
schema are the same for MLB and WNBA. Kalshi accepted WNBA creates and
rejected every MLB create in the window. Official Predictions exchange
sharding (baseball → shard 3 after 2026-08-24 16:00 UTC) plus Kalshi’s
own `404` details citing Exchange Sharding explain the split. Momento
must not compensate by changing execution, retrying 404s, or relaxing
gates.

No code change is justified.

**Do not “fix” this by changing the MLB ticker, Create V2 path, or
request field set because WNBA succeeded.** Those objects already match
the official Create V2 schema. WNBA working only proves the
**authenticated identity and signer** can create orders in production.
It does not prove that `user_not_found` means “wrong ticker format.”

---

## 0. What `user_not_found` refers to

This is the question that must be settled **before** any production
code change. Official Create V2 and the published OpenAPI
(`https://docs.kalshi.com/openapi.yaml`, fetched 2026-08-28) **do not
define** the string `user_not_found`. Create V2’s documented statuses
are 201 / 400 / 401 / 409 / 429 / 500. There is no official REST enum
that maps this code to “API key,” “ticker,” or “subaccount.”

Observed body (two shapes, same `code`):

```json
{"error":{"code":"user_not_found","message":"user not found"}}
```

```json
{"error":{"code":"user_not_found","message":"user not found","details":"Exchange user not found. For Predictions: reference documentation Exchange Sharding documentation."}}
```

| Hypothesis | Official REST meaning | Evidence from this incident |
|---|---|---|
| Authenticated API-key user does not exist in production | Auth failures are documented as **401 Unauthorized**, not 404 | **Ruled out.** Same process, same key fingerprint `2139f81bbe6b98f3`, same signed Create V2 path created two WNBA orders (one fill). |
| A `user` field on the create body is missing | Create V2 has no `user` / `user_id` property | **Not applicable.** Body fields are ticker, client_order_id, side, count, price, TIF, STP, post_only, reduce_only. |
| The **ticker** is the missing resource (market/event not found) | FIX documents unknown market as `MARKET_NOT_FOUND` / unknown symbol. REST Create V2 documents invalid input as **400**. Neither documents ticker miss as `user_not_found` | **Not established.** Local system observed those `KXMLBGAME` books on production WS. Mapping “change the MLB ticker to look like WNBA” would invent a ticker-not-found meaning Kalshi did not send. |
| Exchange-instance user / wrong shard (Kalshi “Exchange user not found”) | Support: wrong shard for user/market, or user not migrated to that shard. REST: omit+ticker auto-routes; else default 0. Create V2 field text matches omit→auto-route. Funding: Intra Account Transfer / UI | **Matches the 404 `details`.** MLB vs WNBA does **not** tell H-route (stuck on 0) from H-user (auto-routed to 3, no instance user). Does **not** license ticker rewrite or copying example `exchange_index: 0`. |
| Undocumented catch-all | `code` is a free string on `ErrorResponse` | **Still true** for the 133 bodies with no `details`. Same `code`; do not invent a second cause. |

**Conclusion on the token:** `user_not_found` is **not** documented as
“authenticated account missing” and **not** documented as “ticker
invalid.” The only Kalshi-authored expansion in this incident is
**exchange user** (sharding). Until Kalshi publishes that code on
Create V2, production Momento code must not be rewritten to compensate
(no ticker rewrite, no extra create fields, no retries).

### Kalshi support text vs official REST (do not collapse these)

A Kalshi-authored explanation of **“Exchange user not found”** (same
`details` string we observed) is: the request is targeting the **wrong
exchange shard / instance for the user or market context**. The
remediation they list is:

1. **Routing:** do not leave the request on **instance 0** if the
   market lives elsewhere; `exchange_index` is the shard id.
2. **Account state:** the user profile / intra-exchange transfer must
   actually exist on that shard before order placement.

That is **not** a ticker-format bug. Official sharding:
[ticker formats are unaffected](https://docs.kalshi.com/getting_started/exchange_sharding);
`exchange_index` on `GET /markets` is the authority.

It also does **not** by itself prove Momento defaulted to shard 0.
Official Create V2 `exchange_index` (inspected 2026-08-28):

> If omitted, auto-routes when ticker is provided; otherwise defaults
> to 0. Use -1 to require auto-routing by ticker.

Momento **omits** `exchange_index` and **sends** `ticker`. Under that
text, the request must **auto-route**, not fall through to 0. The
Create V2 **example payload** that sends `"exchange_index": 0` is the
opposite of what baseball needs; copying it would **force shard 0**.

MLB 404 + WNBA 201 is **predicted by both** remaining hypotheses:

| Id | Claim | Would WNBA work and MLB 404? |
|---|---|---|
| H-route | Omit was treated as shard **0** (support “don’t default to 0”) | Yes: basketball catch-all is 0; baseball after 2026-08-24 is **3** |
| H-user | Omit auto-routed to **3**; exchange-instance user / collateral is missing there | Yes: same split |

The 201 MLB rejects do **not** distinguish H-route from H-user.
Sending `exchange_index: 3` on Create V2 is therefore **not** an
established production fix: if H-user is true, explicit 3 still 404s
until Intra Account Transfer / UI funds index 3. If H-route is true
**and** the user already exists on 3, explicit `3` or `-1` would be
the client change — still **not** a ticker rewrite, and still not
authorized here.

Discriminator not yet run: `GET /portfolio/balance` →
`balance_breakdown[]` (`exchange_index`, `balance`). Official
[Get Balance](https://docs.kalshi.com/api-reference/portfolio/get-balance).
Official funding:
[Intra Account Transfer](https://docs.kalshi.com/api-reference/portfolio/intra-account-transfer)
(`POST /portfolio/intra_exchange_instance_transfer`, amount in
**centicents**, `source_exchange_shard` / `destination_exchange_shard`).

---

## 1. Incident window

| Field | Value |
|---|---|
| `incident_start_utc` | `2026-08-27T23:18:56Z` (live process restart after cutoff-parse fix; first Create V2s in this PID) |
| `incident_end_utc` | `2026-08-28T03:49:03Z` (last MLB `Rejected` persist in window) |
| Host timezone | UTC (Amazon Linux); config `timezone = America/Los_Angeles` |
| Process | `momento-live.service` PID `163366` on `i-0f0849d5829476c31` |
| Paper | `momento-paper.service` **inactive** (entire window) |
| Mode | `live`, `live.enabled=true`, `live.confirmation=ENABLE_LIVE_TRADING` |
| Binary SHA-256 | `71319cae23bfd37225f49bef5053db7a03f47b11b49cb5c121c89731f7ccef26` |
| Credential fingerprint | SHA-256 of API key ID, first 16 hex: `2139f81bbe6b98f3` (key ID UUID-shaped, length 36; value not recorded) |

Earlier the same calendar day, Create V2 for COL@WSH also returned
`404 user_not_found` (that order became the UNKNOWN stall). That event
is the same Kalshi error class; it is not re-counted in the 201.

---

## 2. Counts

| Sport | Create V2 outcomes in window (persisted tracker orders) |
|---|---|
| MLB | **201 rejected** (0 acked, 0 filled) |
| WNBA | **2 accepted** (1 filled then settled, 1 acked then cancelled unfilled) |

Journal `submit_refused` bodies in `2026-08-27 23:18:56Z`–`2026-08-28 04:00:00Z`:

| n | Body (redacted: no secrets) |
|---|---|
| 133 | `order rejected by venue HTTP 404: {"error":{"code":"user_not_found","message":"user not found"}}` |
| 68 | same, plus `"details":"Exchange user not found. For Predictions: reference documentation Exchange Sharding documentation."` |

Journal `latency_us submit_to_ack`: **2** (matches the two WNBA accepts).

Risk released reservations on 404 (Create V2 `400|404` → `VenueError::Unsupported` → `PositionEvent::Rejected` + `risk.on_cancel`). No MLB fill. No 404 retry loop as UNKNOWN.

---

## 3. What was actually sent (reconstructed)

The live host does **not** persist the raw HTTP wire (no request dump, no
response headers). The Create V2 JSON is reconstructed from
`KalshiVenue::submit_post_only` (`crates/kalshi/src/venue.rs`) plus
persisted `Order` fields (ticker via identity map). That reconstruction
is deterministic: there is **no sport branch** in the adapter.

### Shared request metadata (MLB and WNBA)

| Item | Value |
|---|---|
| Method | `POST` |
| Origin | `https://external-api.kalshi.com` |
| Path / URL | `/trade-api/v2/portfolio/events/orders` |
| Full URL | `https://external-api.kalshi.com/trade-api/v2/portfolio/events/orders` |
| Signed path | exactly that path (query stripped; none present) |
| Signature payload | `{unix_ms}POST/trade-api/v2/portfolio/events/orders` |
| Auth headers | `KALSHI-ACCESS-KEY`, `KALSHI-ACCESS-TIMESTAMP`, `KALSHI-ACCESS-SIGNATURE` (values **REDACTED**) |
| API version | Trade API v2, Create Order V2 |
| `side` | always `"bid"` (YES buy) |
| `time_in_force` | `"good_till_canceled"` |
| `self_trade_prevention_type` | `"taker_at_cross"` |
| `post_only` | `true` |
| `reduce_only` | `false` |
| Omitted Create V2 fields | `expiration_time`, `cancel_order_on_pause`, `subaccount`, `order_group_id`, **`exchange_index`** |
| Response headers | **not logged** (`OBSERVABILITY_GAP`) |

Official Create V2 field text: omitting `exchange_index` while sending
`ticker` **auto-routes**. Official REST sharding: `>= 0` direct;
`-1` auto-route; omit + ticker auto-route; else default **0**.
Momento’s reconstructed body matches omit + ticker (not explicit `0`).

`Order.side` / `Order.market_id` are unset on `Order::new_entry`; the
host supplies ticker from `identity.ticker_for_market(approved.market_id())`.
That lookup is the only sport-varying input besides count/price/client id.

### Representative MLB reject (reconstructed body)

Source persist: client `1787872869339608903`, state `Rejected`,
`2026-08-27T23:21:09.339609Z`.

```json
{
  "ticker": "KXMLBGAME-26AUG271910MILNYM-MIL",
  "client_order_id": "00000000-0000-0000-18cf-cce6f08bb747",
  "side": "bid",
  "count": "7.00",
  "price": "0.8000",
  "time_in_force": "good_till_canceled",
  "self_trade_prevention_type": "taker_at_cross",
  "post_only": true,
  "reduce_only": false
}
```

- Timestamp used for signature: unix milliseconds at send; not persisted.
  Client-order-id nanos are the local clock at id generation (~submit time).
- Response: HTTP **404**, body
  `{"error":{"code":"user_not_found","message":"user not found"}}`
  (this hour’s journal lines had no `details` field).
- `venue_order_id`: none.

All 201 MLB rejects: `count` **7**, prices in **80–83¢**, five tickers
only (see matrix below).

### Representative WNBA accept — filled

Source persist: client `1787879525715286233`, state `Filled`,
`2026-08-28T01:12:05.715286Z`. Journal: `submit_to_ack` then
`fill_applied … qty=5 price_cents=81`.

```json
{
  "ticker": "KXWNBAGAME-26AUG27GSNY-GS",
  "client_order_id": "00000000-0000-0000-18cf-d2f4bf7418d9",
  "side": "bid",
  "count": "5.00",
  "price": "0.8100",
  "time_in_force": "good_till_canceled",
  "self_trade_prevention_type": "taker_at_cross",
  "post_only": true,
  "reduce_only": false
}
```

- Response: HTTP **200/201** (ack logged; raw status not stored).
- Fill: 5 @ 81¢; position settled.

### Representative WNBA accept — cancelled, never filled

Source persist: client `1787885077489063820`, state `Cancelled`,
`2026-08-28T02:44:37.489064Z`.

```json
{
  "ticker": "KXWNBAGAME-26AUG27WSHPHX-WSH",
  "client_order_id": "00000000-0000-0000-18cf-d8015ef5178c",
  "side": "bid",
  "count": "5.00",
  "price": "0.8100",
  "time_in_force": "good_till_canceled",
  "self_trade_prevention_type": "taker_at_cross",
  "post_only": true,
  "reduce_only": false
}
```

- Acked (`venue_order_id` present). Filled qty 0. Later cancelled.

---

## 4. MLB vs WNBA comparison

| Dimension | MLB (201 rejects) | WNBA (2 accepts) | Correlates with 404? |
|---|---|---|---|
| Endpoint / method / signed path | identical | identical | no |
| Host / `MOMENTO_KALSHI_ENV` | production | production | no |
| Credential / process / binary | same PID `163366` | same | no |
| `post_only` / `reduce_only` / TIF / STP / `side=bid` | identical | identical | no |
| `client_order_id` | UUID layout of nanos | same encoding | no (unique per order) |
| `count` | always `"7.00"` | always `"5.00"` | allocation (12.5% vs 8.33%), not proven as Kalshi cause |
| `price` | 80–83¢ | 81¢ | no (MLB 81¢ also 404) |
| Ticker series | `KXMLBGAME-…` (baseball) | `KXWNBAGAME-…` (basketball) | **yes** |
| Sport-specific request mutation in adapter | **none** | **none** | — |

MLB rejected tickers (all `KXMLBGAME`, date `26AUG27`):

| Ticker | Rejects |
|---|---|
| `KXMLBGAME-26AUG271910MILNYM-MIL` | 72 |
| `KXMLBGAME-26AUG272145AZSF-SF` | 68 |
| `KXMLBGAME-26AUG271907KCTOR-KC` | 30 |
| `KXMLBGAME-26AUG271905HOUNYY-HOU` | 26 |
| `KXMLBGAME-26AUG271915LADATL-ATL` | 5 |

Local system believed those MLB markets existed: they were bound from
`GET /markets?series_ticker=KXMLBGAME&status=open` and quoted on the
production WebSocket (`yes_bid_update ticker=KXMLBGAME-…`). Kalshi did
**not** return a market-not-found code. No experimental Create or GET
was sent for this write-up.

---

## 5. Environment / auth (same for both sports)

| Item | Evidence |
|---|---|
| REST origin | `REST_PRODUCTION_ORIGIN` = `https://external-api.kalshi.com` |
| Create path | `CREATE_ORDER_PATH` = `/trade-api/v2/portfolio/events/orders` |
| URL join | `origin + path` (no double `/trade-api/v2`) |
| Trading allowlist | `POST` only that create path; `GET` `/trade-api/v2/…`; `DELETE` events/orders |
| Sign | `timestamp_ms + METHOD + path` (`signature_payload`); path signed equals path requested |
| Config | `/var/lib/momento/config/live.toml` matches repo `config/live.toml` gates |
| Paper accidentally live | no; paper unit inactive; `mode=live` |

Auth failure would be HTTP **401** (`VenueError::AuthenticationFailed`),
not 404. WNBA 201/fill on the same signer disproves “key does not exist
in production.”

---

## 6. Official Kalshi semantics vs observed 404

[Create Order V2](https://docs.kalshi.com/api-reference/orders/create-order-v2)
documents responses **201, 400, 401, 409, 429, 500**. It does **not**
document HTTP 404 or `user_not_found`.

[Quick start: create order](https://docs.kalshi.com/getting_started/quick_start_create_order)
lists 401 / 400 / 409 / 429 only.

Classification against the requested A–G list:

| Id | Claim | Finding |
|---|---|---|
| A | Authenticated user does not exist in the target environment | **Ruled out.** Same production key created WNBA orders minutes around the MLB 404s. |
| B | Referenced user/resource does not exist | **Supported at shard scope.** 68 bodies: `details` = `Exchange user not found. For Predictions: reference documentation Exchange Sharding documentation.` |
| C | Ticker/event/market resource does not exist | **Not supported.** Error code is `user_not_found`; markets were WS-quoted. Official create errors for bad params are 400. |
| D | Malformed / invalid resource in the JSON schema | **Not supported.** Same required fields as accepted WNBA; official malformed → 400. |
| E | Environment mismatch | **Ruled out.** Production origin, `MOMENTO_KALSHI_ENV=production`, demo refused in transport. |
| F | Authorization/account mismatch (wrong key / 401) | **Ruled out.** 401 is a distinct adapter path; WNBA succeeded. |
| G | Undocumented / insufficient evidence | Create V2 OpenAPI omits 404. H-route vs H-user unresolved. `GET /markets.exchange_index` and `GET /portfolio/balance` `balance_breakdown` not persisted. |

[Exchange Sharding](https://docs.kalshi.com/getting_started/exchange_sharding)
(official, inspected 2026-08-28):

- After **2026-08-24 12:00 PM ET**, **new tennis and baseball events are
  created on shard 3**. Shard 0 is the catch-all for categories/tags not
  listed (WNBA/basketball is not Tennis/Baseball).
- “Programmatic traders must **preallocate collateral on a given
  exchange shard before order placement**.”
- REST: omit `exchange_index` + provide ticker → **auto-route to that
  market’s shard**. Explicit `>= 0` routes **directly** (Create V2
  example `exchange_index: 0` is direct shard 0).
- Collateral checks run **on the shard**. Preallocate via UI
  (`https://kalshi.com/account/exchange-indexes`) or Intra Account
  Transfer before placing on a new instance.

**Pinpoint for Kalshi (requested fields):**

| Item | Value |
|---|---|
| Method / endpoint | `POST /trade-api/v2/portfolio/events/orders` (Create Order V2) |
| Production URL | `https://external-api.kalshi.com/trade-api/v2/portfolio/events/orders` |
| `exchange_index` on the wire | **omitted** (not `0`, not `3`, not `-1`) |
| MLB / asset | Sports, **Baseball**, series `KXMLBGAME` (not crypto, not combos) |
| Expected shard (series table, events dated 26AUG27, after 2026-08-24 12:00 PM ET) | **3** |
| WNBA / asset | Sports, **Basketball** (tag not Tennis/Baseball) series `KXWNBAGAME` |
| Expected shard | **0** (catch-all) |
| HTTP | **404** `user_not_found`; 68 bodies cite Exchange Sharding |

Incident MLB tickers are `KXMLBGAME` events dated **26AUG27**, after the
baseball shard cutover. WNBA tickers are `KXWNBAGAME`.

Adapter omit+ticker matches the **documented** auto-route. That is not
proof auto-route ran. Explicit `exchange_index: 3` or `-1` is a
possible later client change for H-route only; it is not a ticker
change and is **not** implemented here. Intra-shard funding is
required under H-user either way.

---

## 7. Sport-specific mutation check

Path: `ApprovedTradeIntent` → `submit_approved` → ticker from identity →
`submit_post_only` → one `CreateOrderV2Request` struct.

No MLB-only ticker rewrite, side map, price map, TIF, or path. Count 7
vs 5 is risk sizing (`RiskConfig::mlb_paper_experimental`: 1250 bps vs
833 bps), not an adapter fork. MLB 404s occurred at 80, 81, 82, and 83¢
with the same count; WNBA 81¢ with count 5 was accepted. The sport
series (shard assignment) is the difference that matches both the
ticker split and Kalshi’s sharding `details`.

---

## 8. Root cause

**ROOT CAUSE EXTERNAL** (Kalshi exchange-instance user / shard
context). **H-route vs H-user is unresolved.**

Kalshi: “Exchange user not found” means the Create V2 hit the **wrong
shard for this user/market**, or the user is **not provisioned** on
the shard that baseball now uses. After 2026-08-24 12:00 PM ET, new
baseball events are created on **index 3**; WNBA basketball stays on
**index 0**. Same Create V2 path; only series/ticker (hence shard
assignment) differs.

Not established: that Momento sent the request to 0. Official omit +
ticker is auto-route. Not established: that adding `exchange_index: 3`
to production Create V2 would accept MLB without funding index 3.

This is **not**:

- an MLB ticker / Create V2 field-set bug to “match WNBA”
- an MLB strategy miss
- a Risk reject of those 201 creates (they were approved, then venue 404)
- a signing/path/credential bug (WNBA proof)
- a reason to retry 404s or treat them as UNKNOWN
- a reason to copy Create V2 docs example `"exchange_index": 0`

---

## 9. Unresolved (explicit)

- H-route vs H-user (omit defaulted to 0 vs auto-route to 3 with no
  exchange-instance user / collateral).
- Per-ticker `exchange_index` from `GET /markets` was not stored, so
  shard **3** is from the official series table + `KXMLBGAME`, not from
  a persisted market payload.
- Why 133/201 404s omitted `details` (same `code`). Not used to invent
  a second cause.
- H-route vs H-user: **H-user is now evidenced.** Read-only
  `GET /portfolio/balance` on 2026-08-28 (same production key
  `2139f81bbe6b98f3`): HTTP 200 on `exchange_index=3` with
  `balance_dollars=0.0000`. Index 0 holds `59.4639`. Open
  `KXMLBGAME` markets return `exchange_index: 3`; open `KXWNBAGAME`
  return `0`. Index 3 is a known portfolio line at $0, not a missing
  API user. Create V2 404 is collateral/instance trading user on the
  baseball shard, not ticker format. H-route (omit defaulted to 0) is
  **not required** to explain the split and was not proven on the
  create wire.

---

## 10. Recommended next action

1. **Do not retry** the 201 rejected client order ids.
2. **Do not change** Momento Create V2, MLB tickers, strategy, or risk.
   Do not add `"exchange_index": 0`. Do not add `"exchange_index": 3`
   as an unproven production “fix.”
3. On the Kalshi account: **Get Balance** with `balance_breakdown`
   (indexes 0 and 3). Then **fund / provision index 3** via
   [Kalshi UI](https://kalshi.com/account/exchange-indexes) or
   `POST /portfolio/intra_exchange_instance_transfer`
   (`source`/`destination` `event_contract`,
   `source_exchange_shard=0`, `destination_exchange_shard=3`, amount
   in centicents) per official Balance Management.
4. Optional later (not this incident): persist `GET /markets`
   `exchange_index` for audit; only then consider Create V2 `-1` or
   explicit index if Get Balance already shows index 3 funded and MLB
   still 404s (H-route).

---

## 11. Code change

**None.** In particular:

- Do not rewrite `KXMLBGAME` tickers or discovery because WNBA uses
  `KXWNBAGAME`. Ticker format is officially unchanged by sharding.
- Do not add `"exchange_index": 0` (docs example; would force shard 0).
- Do not add `"exchange_index": 3` or `-1` in this change set.
- Do not retry 404 `user_not_found`.

`user_not_found` is not an official Create V2 enum. The only Kalshi
expansion in the body is “Exchange user not found” (sharding). Treating
that as a Momento ticker/format bug would invent venue semantics.

---

## 12. Trading resume

Live may stay armed. After the 2026-08-28 Kalshi UI transfer, Get
Balance shows **$35.0000 on index 3** and **$24.4639 on index 0**.
New MLB creates should no longer 404 solely for an unfunded baseball
shard. Post-only still may not fill. Kill switch untouched. Paper
remains stopped.
