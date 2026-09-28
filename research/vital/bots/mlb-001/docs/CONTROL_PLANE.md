# MLB Bot 001 — control plane

API prefix: `/vital/bots/mlb-001`.

```text
GET  /plane /status /health /configuration /strategy
GET  /positions /orders /risk /heartbeat /logs /events
GET  /controls /boundary /worker /pipeline
POST /commands   fail-closed
```

Worker: `momento-live.service` (independent of this API).
Path: Kalshi WS → `strategies/mlb` → Risk → `live.rs` → fill.
Trades: one host Position per market. Catalog fills are not trades.

This folder does not submit orders.
