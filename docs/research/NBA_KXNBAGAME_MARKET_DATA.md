# Kalshi `KXNBAGAME` historical market-data warehouse

**Schema:** `nba_market_data_schema_v1`  
**Series:** `KXNBAGAME` (Pro Basketball Game)  
**Sport:** NBA (first-class `ResearchSport::Nba`)  
**CLI:** `nba-data`

## What data exists

Kalshi production historical REST (`https://external-api.kalshi.com/trade-api/v2`) provides:

- Event catalog (`GET /events?series_ticker=KXNBAGAME`)
- Historical markets (`GET /historical/markets?series_ticker=KXNBAGAME`)
- Live/unarchived markets (`GET /markets?series_ticker=KXNBAGAME`)
- **1-minute candlesticks** with `yes_bid` / `yes_ask` OHLC (`GET /historical/markets/{ticker}/candlesticks`)
- **Public trades** (`GET /historical/trades?ticker=`)
- Market metadata including settlement/result, volume, open/close/settlement times
- Historical cutoff (`GET /historical/cutoff`)

## What data does not exist

**Historical L2 order books are not available.**

There is no `GET /historical/.../orderbook`. A live orderbook snapshot on a settled market is empty. WebSocket `orderbook_delta` is forward-only.

> Historical KXNBAGAME data is 1-minute top-of-book/candlestick data plus public trades; it is not historical L2 order-book reconstruction.

Normalized candles are labeled:

```text
market_data_type = CANDLESTICK_TOP_OF_BOOK
orderbook_depth_available = false
```

The warehouse never fabricates depth, queue position, or L2 levels from candles. Future live capture can insert `L2_SNAPSHOT` / `L2_DELTA` into the same market-data layer.

## How this differs from the MLB collector

The MLB daily collector maps 1-minute candle **close** bid/ask into `orderbook.parquet` as `OrderbookEvent` (`CANDLESTICK_ONLY`). That path is unchanged.

NBA uses an **event-centric warehouse** under:

```text
Backtesting Suite/Data/NBA/{season}/warehouse/
  raw/kalshi/nba/{events,markets,candlesticks,trades}/
  normalized/nba/{events,markets,games,candles_1m,trades}/
  derived/nba/{causal_features,complementarity,trade_minute,coverage}/
  manifests/nba/
```

Candles are never written as `orderbook.parquet`.

## Price units

Kalshi sends 4-decimal dollar strings (`"0.7100"`). The warehouse stores integer **E4** (ten-thousandths of a dollar):

| API string | E4 | Probability |
|---|---:|---:|
| `0.7100` | 7100 | 0.71 |
| `1.0000` | 10000 | 1.00 |

No `f64` is used for stored prices. Derived mid is `(bid_e4 + ask_e4) / 2` only when both sides exist.

## Game ↔ market mapping

Each event is one game. `game_id` is the existing Kalshi `GameId` hash of `event_ticker`. Each game should have exactly two team YES markets (`yes_sub_title` / ticker suffix). Anomalies are flagged, not dropped.

Season phase uses event title/subtitle first (`Play-In`, `Game N:`). Preseason has no Kalshi title signal and is labeled with a documented October calendar window. June `Game N:` titles are labeled `FINALS`.

## How to run

```bash
# Catalog only
cargo run -p momento-nba-data -- discover --season 2025-26

# Plan without downloading time series
cargo run -p momento-nba-data -- download-all --season 2025-26 --dry-run

# Full 2025-26 ingest (resumable, idempotent)
cargo run -p momento-nba-data -- download-all --season 2025-26 --max-workers 4 --rps 4

# Single game
cargo run -p momento-nba-data -- download-all --event KXNBAGAME-26JUN13NYKSAS

# Rebuild parquet/derived from raw
cargo run -p momento-nba-data -- rebuild-derived --season 2025-26
```

Re-running `download-all` skips `COMPLETE` ticker jobs.

## Query API

`NbaQuery` (in-memory after `NbaWarehouse::query()`):

- `get_games(season, phase)`
- `get_markets(game_id)` / `get_market(ticker)`
- `get_candles(ticker, start, end)`
- `get_trades(ticker, start, end)`
- `get_game_market_data(game_id, start, end)`
- `get_season_market_data(season, phase)`
- `aligned_two_sided(game_id)` — team A/B bid/ask/mid on shared timestamps

Derived causal features (`return_1m/5m/15m`, mid, spread) use only information at or before `t` (`look_ahead = false`). Complementarity `(a_mid + b_mid) - 1` is a diagnostic, not an arb signal.

## MLB safety

`CollectorConfig::default_sports()` remains MLB + WNBA only. NBA is not added to the date-partitioned MLB/WNBA collector or W1/W2/W3 reconstruction trees.
