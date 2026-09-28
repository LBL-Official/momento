# DATA-INGEST operator runbook

**Plane:** DATA-INGEST  
**Cloud:** `IMPLEMENTED_NOT_DEPLOYED`  
**PBP source:** MLB StatsAPI (`https://statsapi.mlb.com`). There is **no ESPN** ingest in this plane.

## Network

Live fetch requires:

```text
--authorize-network ENABLE_RESEARCH_INGEST_NETWORK
```

Bare `--network` exits 2.

## Commands

```text
cargo run -p momento-research-ingest-app -- schedule-info
cargo run -p momento-research-ingest-app -- plan-windows
cargo run -p momento-research-ingest-app -- cloud-spec

# Identity-scale (PBP + Kalshi tickers/metadata; no trade download)
cargo run -p momento-research-ingest-app -- backfill \
  --authorize-network ENABLE_RESEARCH_INGEST_NETWORK \
  --window 2025-04-16:2026-08-26 \
  --kalshi-metadata-only \
  --out "Backtesting Suite/Foundation/Ingest" \
  --lake "Backtesting Suite/Data-Real"

# Trades/candles where available (upgrades MARKET_METADATA_ONLY landings)
cargo run -p momento-research-ingest-app -- backfill \
  --authorize-network ENABLE_RESEARCH_INGEST_NETWORK \
  --window 2025-04-16:2026-08-26 \
  --out "Backtesting Suite/Foundation/Ingest" \
  --lake "Backtesting Suite/Data-Real"
```

`--window START:END` sets overlap to 0 so a bounded backfill is not expanded to `as_of`.

## Cadence

Sunday 00:00 America/Los_Angeles is the **weekly** cadence (overlap 3 days). Historical `--window` / `backfill` does not use that expansion.

## Landing

New bytes: `Backtesting Suite/Foundation/Ingest/landing/**`

Never: Data-Real, Foundation/W1, Foundation/W2/raw, production trees.

## W1 commit → W2/W3

Committed checksum-verified StatsAPI envelopes are the only MLB PBP research truth for W2/W3. Kalshi discovery envelopes are W4-compatible **source** artifacts, not reconstructed `MarketState`.

## Failure states

| Symptom | State |
|---------|--------|
| Concurrent writer | `BLOCKED` (`ConcurrentWriter`) — remove stale `locks/ingest.lock` only if no ingest process |
| Checksum mismatch | fail closed |
| Same bytes | `ALREADY_KNOWN` |
| Different bytes | `VERSION_CONFLICT` sibling; original preserved |
| Source listed nothing | `UNAVAILABLE` |
| Bounded retries exhausted | `FAILED` |
| Identity | `MAPPED` / `UNMATCHED` / `AMBIGUOUS` — never guessed |
