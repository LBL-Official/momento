# Historical Kalshi Research Data Infrastructure

> **Platform note (2026-08-26):** This lake remains the seed for Waterfall 1 of the
> new historical engine ([plan](HISTORICAL_ENGINE_DEVELOPMENT_PLAN.md)). Candlestick
> partitions are **`observability = CANDLESTICK`** — never silently treated as L2 ticks.
> Extend with immutable raw + PBP; do not rewrite existing raw truth.

This document describes Momento's isolated research data pipeline for MLB (`KXMLBGAME`)
and WNBA (`KXWNBAGAME`) backtesting. It does **not** modify live trading.

## Official Kalshi data sources

| Data | Live endpoint | Historical endpoint | Notes |
|------|---------------|---------------------|-------|
| Market discovery | `GET /markets` | `GET /historical/markets` | Routed by `GET /historical/cutoff` |
| Public trades | `GET /markets/trades` | `GET /historical/trades` | Paginated, timestamp filters |
| Candlesticks (bid/ask OHLC) | `GET /series/{series}/markets/{ticker}/candlesticks` | `GET /historical/markets/{ticker}/candlesticks` | 1/60/1440 minute periods |
| Orderbook snapshot (current) | `GET /markets/{ticker}/orderbook` | N/A for past state | Point-in-time only when collected |
| Orderbook deltas (L2) | WebSocket `orderbook_delta` | **Not available historically** | Must be captured prospectively |

Kalshi does **not** expose a historical WebSocket replay or archived L2 orderbook.
The collector records this limitation in daily manifests and stores candlesticks separately
from L2 snapshots.

## Storage layout

Default root: `Backtesting Suite/Data` (override with `MOMENTO_RESEARCH_DATA_DIR`).

```
{root}/{MLB|WNBA}/{2025-2026}/
  raw/date=YYYY-MM-DD/events.jsonl.gz
  orderbook/date=YYYY-MM-DD/{metadata,orderbook}.parquet
  trades/date=YYYY-MM-DD/trades.parquet
  manifests/date=YYYY-MM-DD.json
  validation/
  catalog.json (root index for Notion handoff)
```

Publication is atomic: write under `.staging/`, validate, rename.

## Schema (`schema_version = 1.0.0`)

See `crates/research-data/src/schema.rs` for:

- `RawMarketEvent` — immutable gzip JSONL archive rows
- `MarketMetadata` — `game_id`, `market_id`, `ticker`, side label
- `OrderbookEvent` — exchange vs received timestamps, levels, gap metadata
- `PublicTrade` — distinct from quotes
- `DailyManifest` — completeness, checksums, counts

Prices: integer cents for normalized fields. Quantities: hundredths of contracts
(Kalshi `count_fp` × 100).

## Collector

Binary: `momento-research-collector`

```bash
cargo run -p momento-research-collector -- reconcile
cargo run -p momento-research-collector -- collect-date 2025-08-20
cargo run -p momento-research-collector -- schedule-info
cargo run -p momento-research-collector -- catalog
```

Systemd: `deploy/momento-research-collector.timer` runs daily at **03:00 America/Los_Angeles**.

## Replay interface

`momento_research_data::ReplayDataset::load` reads normalized Parquet for a sport/date.
`ReplayCursor` iterates trades and orderbook events in chronological order and exposes
gap state. No strategy logic is included.

## Notion

High-volume data stays on disk. `catalog.json` is the machine-readable index intended
for Notion catalog pages (coverage, completeness, manifest paths).

## Data limitations (2025-2026 season)

- **MLB / WNBA pre-capture dates**: trades + metadata + candlesticks can be backfilled;
  full L2 history cannot unless it was captured live via WebSocket.
- **REST orderbook snapshots** in backfill reflect collection-time state, not historical
  intraday evolution.
- No synthetic mids or interpolated books enter normalized datasets.
