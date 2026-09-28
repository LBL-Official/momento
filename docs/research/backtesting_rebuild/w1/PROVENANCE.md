# W1 Provenance Specification

## Timestamp roles

| Role | Typical field | Do not treat as |
|------|---------------|-----------------|
| `INGESTION` | `received_at` | Exchange/event time |
| `EXCHANGE_OR_EVENT` | trade `created_time` | Collector clock |
| `CANDLE_PERIOD_END` | `end_period_ts * 1000` | A tick |
| `VENUE_METADATA` | `open_time` / `close_time` / `settlement_ts` | Proven open **price** |
| `UNKNOWN` | missing | Anything |

Envelope v2 (`schema 2.0.0`) lifts v1 rows **into Foundation output only**. It copies `received_at` → `ingestion_timestamp` and never fills `source_timestamp` from `received_at` for orderbook snapshots.

## File provenance

Each catalogued file gets `ProvenanceRecord`: source `kalshi_v1_lake`, path, SHA-256, schema 1.0.0, coverage status, timestamp semantics for that layer.
