# ADR-0002 — Timestamp authority

# Decision

Multiple clocks are stored; none is silently substituted for another. Exchange /
official event time is the research authority for “what was knowable at t.”
Collector receive time is provenance only.

# Context

LEGACY_V1 `RawMarketEvent.received_at` is collector wall clock (backfill day
2026-08-25 for June files). Trade `created_time` and candle `end_period_ts` live
inside payloads. Live production uses `MarketEvent.exchange_ts` plus `received_at`.

# Problem

Using ingest time as event time fabricates when the market was observed. Mixing
candle period-end with trade created_time without labeling the kind of clock
produces false synchronization.

# Alternatives Considered

1. Single timestamp column; pick “best available.”
2. Always use collector receive time.
3. Preserve distinct timestamp kinds with explicit authority rules.

# Decision Made

Alternative 3. Required kinds (nullable + reason when missing):

| Kind | Authority |
|------|-----------|
| `source_timestamp` | Exchange or official PBP time |
| `source_timestamp_kind` | `trade_created` \| `candle_end` \| `metadata_open` \| `pbp_official` \| `ingest_only` \| … |
| `ingestion_timestamp` | Collector receive (provenance) |
| `event_timestamp` | Sport event clock join key (later waterfall) |
| `market_timestamp` | Market-domain join key |

Never promote `ingestion_timestamp` to `source_timestamp`.

# Rationale

Lookahead prevention and sync confidence depend on knowing which clock was used.

# Consequences

Envelope v2 must allow missing `source_timestamp` with a reason. Partition dates
remain America/Los_Angeles close/settled day for v1; lifetime paths are a later
collection concern, not a timestamp lie.

# Data/Model Implications

Features at t may only use data whose source timestamp is ≤ t on the declared clock.

# Testing Implications

Timestamp tests: ingest ≠ exchange; candle_end labeled; missing source time allowed
with reason; no silent upgrade of confidence.

# Future Compatibility

PBP official times and live WS exchange times join through the same kind enum.

# Status

ACCEPTED

# Date

2026-08-26
