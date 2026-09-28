# Kalshi Data Observability Matrix

**Purpose:** State what historical Kalshi data **is**, **is not**, and **must never be invented**.  
**Sources inspected:** `crates/kalshi/src/public_data.rs`, `crates/research-data/src/{collector,schema,validate}.rs`, `docs/research/data-infrastructure.md`, local Data-Real payloads, official endpoint comments in code (Kalshi historical docs URLs in `public_data.rs`).

---

## 1. Official channels the collector already uses

| Data | Live / current | Historical | Used in LEGACY collector? |
|------|----------------|------------|---------------------------|
| Market list | `GET /markets` | `GET /historical/markets` | Yes (close_ts and settled_ts windows) |
| Historical cutoff | | `GET /historical/cutoff` | Yes (`market_settled_ts` routes trades/candles to historical vs live) |
| Public trades | `GET /markets/trades` | `GET /historical/trades` | Yes |
| Candlesticks | `GET /series/{series}/markets/{ticker}/candlesticks` | `GET /historical/markets/{ticker}/candlesticks` | Yes, `period_interval = 1` minute |
| Orderbook snapshot | `GET /markets/{ticker}/orderbook` | **No historical replay** | Yes — **at collection time** |
| Orderbook L2 deltas | WebSocket `orderbook_delta` | **Not available retrospectively** | Reconstructor exists in code; **not wired into daily collect** |

Kalshi does not expose archived WebSocket L2. Manifests already say so. Keep that sentence forever.

---

## 2. Field matrix (historical research)

Legend: **O** = OBSERVED in some local rows, **D** = DERIVED, **M** = MODELED only, **U** = UNAVAILABLE for historical backfill (do not invent).

| Field | Historical REST (what we have) | Live WS (forward) | Notes |
|-------|--------------------------------|-------------------|-------|
| Ticker / event_ticker / series | O | O | Identity aliases |
| Status / result / settlement_ts | O (metadata) | O | Catalog nulls in W1 |
| open_time / close_time | O (metadata strings) | O | Use for lifetime bounds |
| Public trades (price, qty, time, taker sides) | O | O | Dense on Jun 18–30 2026 |
| Last trade | D from trades | O | Not a substitute for bid |
| YES bid / ask (1-min **close**) | O as candle | n/a | LEGACY stored as `OrderbookEvent` |
| YES bid/ask **high/low/open** of the minute | O in raw candle payload | n/a | **Dropped** from normalized `OrderbookEvent` (only close mapped) — reconstruction gap |
| Candle `price` OHLC | Often **null** in sample | n/a | Do not fill from bid |
| Volume / OI on candle | O (`volume_fp`, `open_interest_fp`) | n/a | Not copied onto `OrderbookEvent` |
| Bid/ask **size** on candle | U | O on book | Do not invent size from volume |
| Spread | D from close bid/ask | D | |
| L2 levels | U historically | O if captured | |
| Queue position | U | U/M | Never fabricate |
| Sequence numbers | U on REST candles | O on WS | `sequence_gap` false on candles is **not** proof of a continuous book |
| PIT REST book levels | O at **ingest time** (Aug 25 2026 for June files) | O | **Must not** be treated as game-time L2 |
| Mid | U (not a venue field) | U | Forbidden for 80/81/89 |
| Fees | U in research (`FeesModel::NotModeled`) | Live fee types in core | MODELED later with explicit flag |
| Fill / resting queue | M | O (our orders only) | CONSERVATIVE_MAKER is MODELED and currently **unsupported** on candles |
| Historical markets before ~2026-06-18 | U **locally**; API returned 0 at collect time | n/a | Re-query in W1; may remain U |

---

## 3. How LEGACY maps candles (must not be silent)

`collector.rs` maps each candlestick to:

```text
event_type = "candlestick_close"
source     = RestCandlestick
yes_bid    = yes_bid.close_dollars → cents
yes_ask    = yes_ask.close_dollars → cents
levels     = []
depth      = None
exchange_timestamp_ms = end_period_ts * 1000
```

`research-execution` classifies this as `CANDLESTICK_ONLY` and **refuses maker and liquidation simulation**. That refusal is correct. The hazard is **naming**: the row still sits in `orderbook.parquet`.

Raw candle **also** contains minute high/low/open for bid and ask. Those are OBSERVED in gzip and **not** in the normalized event. Waterfall 1 should catalog them as present-in-raw, absent-in-normalize-v1.

---

## 4. Point-in-time snapshot hazard

After candles, collector calls `get_orderbook(ticker, depth=100)` and appends `event_type = "rest_snapshot"`, `source = RestSnapshot`, with levels.

For a market that settled in June, a snapshot taken on **2026-08-25** is not June L2. Possible contents: empty, settled, or leftover. Observability = OBSERVED **as of ingest**, UNAVAILABLE **as historical book**.

New engine must partition or tag these so path reconstruction never uses them as t_game.

---

## 5. Time and provenance hazards

| Issue | Fact |
|-------|------|
| `RawMarketEvent.received_at` | Collector clock (backfill day), not Kalshi |
| Trade exchange time | Inside payload `created_time` (OBSERVED) |
| Candle time | `end_period_ts` (period **end**, 1-minute bucket) |
| Discovery window | America/Los_Angeles 00:00–23:59:59 of **close or settled** date |
| Lifetime path | Not collected if open was on a prior calendar day |

First-touch and starting-price research **require lifetime queries** keyed by `open_time`/`ticker`, not only settlement-day partitions.

---

## 6. Execution quality enum (keep, do not weaken)

```text
FULL_L2 | TOP_OF_BOOK_ONLY | CANDLESTICK_ONLY | NO_EXECUTION_DATA
```

Rules:

- Candles ⇒ `CANDLESTICK_ONLY`
- `supports_maker_simulation` only for FULL_L2 / TOP_OF_BOOK_ONLY
- Mixing one WS snapshot into a candle day must not upgrade the **day** to FULL_L2 (existing aggregate logic is conservative-ish; still do not treat PIT REST as WS)

---

## 7. What Waterfall 1 may add without lying

Allowed:

- Re-fetch **documented** historical REST (markets, trades, candlesticks) for missing dates
- Store raw payloads unchanged
- Record cutoff responses as raw
- Prospective WS capture **from authorization date forward** (not backfilled)

Forbidden:

- Interpolating books between trades
- Setting bid = last trade
- Building L2 from candle OHLC
- Cloning Team A book from 100 − Team B last
- Silent imputation of missing minutes

---

## 8. Series in scope

MLB: `KXMLBGAME` only for the first complete sport.  
WNBA `KXWNBAGAME` exists in the same lake; **do not implement WNBA adapters** until MLB is done. Do not delete WNBA raw.
