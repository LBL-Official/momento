# Kalshi `KXNCAAMBGAME` historical market-data warehouse

**Schema:** `ncaab_market_data_schema_v1`  
**Series:** `KXNCAAMBGAME` (men’s college basketball game) — discover from the live catalog; do not invent `KXNCAABGAME`  
**Sport:** NCAAB (first-class `ResearchSport::Ncaab`)  
**CLI:** `ncaab-data`

This is the same Momento backtest ingest logic as [`NBA_KXNBAGAME_MARKET_DATA.md`](NBA_KXNBAGAME_MARKET_DATA.md), applied to men’s NCAAB game markets.

## What data exists

Kalshi production historical REST (`https://external-api.kalshi.com/trade-api/v2`) provides:

- Event catalog (`GET /events?series_ticker=KXNCAAMBGAME`)
- Historical markets (`GET /historical/markets?series_ticker=KXNCAAMBGAME`)
- Live/unarchived markets (`GET /markets?series_ticker=KXNCAAMBGAME`)
- **1-minute candlesticks** with `yes_bid` / `yes_ask` OHLC (`GET /historical/markets/{ticker}/candlesticks`)
- **Public trades** (`GET /historical/trades?ticker=`)
- Market metadata including settlement/result, volume, open/close/settlement times
- Historical cutoff (`GET /historical/cutoff`)

## What data does not exist

**Historical L2 order books are not available.**

There is no `GET /historical/.../orderbook`. A live orderbook snapshot on a settled market is empty. WebSocket `orderbook_delta` is forward-only.

> Historical KXNCAAMBGAME data is 1-minute top-of-book/candlestick data plus public trades; it is not historical L2 order-book reconstruction.

Normalized candles are labeled:

```text
market_data_type = CANDLESTICK_TOP_OF_BOOK
orderbook_depth_available = false
```

The warehouse never fabricates depth, queue position, or L2 levels from candles. Future live capture can insert `L2_SNAPSHOT` / `L2_DELTA` into the same market-data layer.

Women’s `KXNCAAWBGAME` is out of scope.

## How this differs from NBA and MLB

MLB uses a date-partitioned collector and may store candle close as `orderbook.parquet`. That path is unchanged. NCAAB is **not** added to `CollectorConfig::default_sports()`.

NBA and NCAAB share the event-centric warehouse. NCAAB-specific pieces:

- Series `KXNCAAMBGAME` (confirm on a host that can reach Kalshi)
- Season phases from event titles, not NBA Play-In / Finals
- Exhibition-inclusive season label (October–April)
- Paths under `Backtesting Suite/Data/NCAAB/{season}/warehouse/`

```text
Backtesting Suite/Data/NCAAB/{season}/warehouse/
  raw/kalshi/ncaab/{events,markets,candlesticks,trades}/
  normalized/ncaab/{events,markets,games,candles_1m,trades}/
  derived/ncaab/{causal_features,complementarity,trade_minute,coverage}/
  manifests/ncaab/
```

Candles are never written as `orderbook.parquet`.

## NCAAB phases

Title/subtitle first. Do not invent March Madness from calendar month.

| Value | Title signals (if present) |
| --- | --- |
| `EXHIBITION` | exhibition, friendly |
| `PRESEASON` | preseason |
| `REGULAR_SEASON` | default when unlabeled |
| `CONFERENCE_TOURNAMENT` | conference tournament, championship week, conference championship |
| `NCAA_TOURNAMENT` | First Four, Round of 64/32, Sweet 16, Elite 8, Final Four, national championship, NCAA tournament, March Madness |
| `OTHER_POSTSEASON` | NIT, CBI — only if titles say so |
| `UNKNOWN` | flagged, not dropped |

## Price units

Same as NBA. Kalshi sends 4-decimal dollar strings (`"0.7100"`). The warehouse stores integer **E4**:

| API string | E4 | Probability |
|---|---:|---:|
| `0.7100` | 7100 | 0.71 |
| `1.0000` | 10000 | 1.00 |

No `f64` is used for stored prices. Derived mid is `(bid_e4 + ask_e4) / 2` only when both sides exist.

## Game ↔ market mapping

Each event is one game. `game_id` is the existing Kalshi `GameId` hash of `event_ticker`. Each game should have exactly two team YES markets. Anomalies are flagged, not dropped.

Observed event shape: `KXNCAAMBGAME-26JAN18TLSAUAB`.

## Cloud-host requirement

Some public wifi networks block Kalshi. All Kalshi HTTP must run on:

- a Cursor Cloud Agent VM, or
- a Momento AWS research/ingest EC2 that is **not** live trading `i-0f0849d5829476c31`

Do not run Kalshi HTTP from a blocked laptop. Do not start `momento-live` / `momento-paper`. Do not deploy DATA-INGEST CloudFormation (`LOCAL_CRON_ONLY`).

First command on the chosen host:

```bash
curl -sS -o /dev/null -w "%{http_code}\n" \
  https://external-api.kalshi.com/trade-api/v2/historical/cutoff
```

If that is not HTTP 200, switch hosts. Do not invent data.

Live 2025–2026 digest is on this machine. Confirmed series `KXNCAAMBGAME`. Events=5280 markets=10560 games=5280 candles=13429581 trades=32139837 status=PASS. See [`ncaab/IMPLEMENTATION_REPORT.md`](ncaab/IMPLEMENTATION_REPORT.md).

## How to run

```bash
# Catalog only
cargo run -p momento-ncaab-data -- discover --season 2025-2026

# Plan without downloading time series
cargo run -p momento-ncaab-data -- download-all --season 2025-2026 --dry-run

# Full 2025-26 ingest (resumable, idempotent)
cargo run -p momento-ncaab-data -- download-all --season 2025-2026 --max-workers 4 --rps 4

# Single game
cargo run -p momento-ncaab-data -- download-all --event KXNCAAMBGAME-26JAN18TLSAUAB

# Rebuild parquet/derived from raw
cargo run -p momento-ncaab-data -- rebuild-derived --season 2025-2026
```

Re-running `download-all` skips `COMPLETE` ticker jobs.

## Query API

Same `NbaQuery` surface after `NbaWarehouse::query()` (shared warehouse type):

- `get_games(season, phase)`
- `get_markets(game_id)` / `get_market(ticker)`
- `get_candles(ticker, start, end)`
- `get_trades(ticker, start, end)`
- `get_game_market_data(game_id, start, end)`
- `get_season_market_data(season, phase)`
- `aligned_two_sided(game_id)`

Derived causal features (`return_1m/5m/15m`, mid, spread) use only information at or before `t` (`look_ahead = false`). Complementarity `(a_mid + b_mid) - 1` is a diagnostic, not an arb signal.

## MLB / live safety

`CollectorConfig::default_sports()` remains MLB + WNBA only. NCAAB is not added to the date-partitioned collector, W1–W3 trees, FIRST01, or live trading.
