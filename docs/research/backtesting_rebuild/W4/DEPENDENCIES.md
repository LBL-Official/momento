# CTO-W4 DEPENDENCIES

**Upstream:** DATA-INGEST (discovery envelopes + identity pairs), W1 lake
COMPLETE (read-only), W2/W3 identity (read-only).  
**Downstream:** CTO-W5 (event ↔ market **sync** — not implemented here).

## New crate dependency

`momento-research-market` depends on:

- `momento-research-data` — observability, starting price, lake guard, gzip raw reader, checksums
- `momento-research-ingest` — handoff, identity mapping, discovery source constants
- `chrono` / `chrono-tz` — venue timestamps; PT settlement-day classification
- `serde` / `serde_json` / `sha2` / `thiserror`

No `momento-risk`, `momento-execution`, `momento-strategy-mlb`, `momento-kalshi`
order client, parquet, or network HTTP client.

## Blocking conditions

| Blocker | W4 behavior |
|---------|-------------|
| Historical L2 | Classify UNAVAILABLE; do not wait |
| Most mapped pairs metadata-only | `BLOCKED_ON_INGEST_OBSERVATIONS` on those tickers |
| 2024 Kalshi catalog empty | Do not claim 2024 coverage |

## Parallelism

Allowed vs DATA-INGEST observation upgrade (trades/candles backfill). W4 must
not implement that upgrade. Forbidden: W5 sync, W6+ transitions/theta.
