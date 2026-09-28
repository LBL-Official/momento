# DATA-INGEST — Continuous Historical + Forward Feed

**Plane:** `DATA-INGEST` (cross-cutting). Not W4. Does not redefine W1 or W2/W3.  
**Artifact version:** `INGEST.2.0.0`  
**Date:** 2026-08-26  
**Cloud:** IMPLEMENTED_NOT_DEPLOYED

## Ownership

| Plane | Owns | Must not |
|-------|------|----------|
| **INGEST** | Scheduling, discovery, acquisition, immutable landing, run IDs, manifests, checksums, watermarks, audit, W1 commit handoff | Write Data-Real; overwrite Foundation/W1 or frozen W2/raw; reconstruct GameState; reconstruct Kalshi `MarketState`; compute theta; touch production |
| **W1** | Immutable source truth, provenance vocabulary, lake integrity | Download PBP; schedule |
| **W2/W3** | MLB event/PBP reconstruction from COMMITTED artifacts | Acquire raw; consume uncommitted landing |
| **W4** | Kalshi market reconstruction | **Not started** |

## Concurrent writers (forbidden pairs)

| Tree | Exclusive writer |
|------|------------------|
| `Backtesting Suite/Data-Real/**` | **None** (immutable) |
| `Backtesting Suite/Foundation/Ingest/landing/**` | Ingest plane only |
| `Backtesting Suite/Foundation/W1/**` | W1 foundation job only |
| `Backtesting Suite/Foundation/W2/**` (derived JSON) | W2 reconstruction job only |
| `Backtesting Suite/Foundation/W2/raw/**` | **Frozen**. Ingest must not overwrite |
| `Backtesting Suite/Foundation/W3/**` | W3 reconstruction job only |
| Production / live / risk / execution | Untouched |

## Flow

```text
mode = backfill | weekly | manual | replay | recovery
  → exclusive lock or BLOCKED
  → partition windows (2024 / 2025 / 2026-through-as_of / forward / overlap)
  → discover (StatsAPI schedule or Kalshi discovery adapter)
  → fetch with bounded retries
  → land bytes: new | ALREADY_KNOWN | VERSION_CONFLICT sibling
  → W1 provenance + SHA-256 COMMIT
  → optional W2 consume of COMMITTED StatsAPI refs
  → persist watermarks (do not advance past FAILED)
  → reports
  → unlock
```

Sunday 00:00 America/Los_Angeles is the weekly cadence, not the only execution.

## Coverage honesty

Windows report scheduled/discovered/fetched/committed/reconstructed-ready/failed/unavailable/skipped/duplicates/checksum conflicts.

Status: COMPLETE | COMPLETE_WITH_GAPS | FAILED | UNAVAILABLE. Never convert UNAVAILABLE into COMPLETE because the scheduler ran.

## Kalshi

Discovery lands observed tickers under ingest landing. Identity: UNMATCHED / AMBIGUOUS / OBSERVED (only if the source provided gamePk). Ticker text is never parsed into a fabricated gamePk. Lake catalog remains read-only vs Data-Real. Live Kalshi GET is **BLOCKED** in the CLI.

## Authorized sources

| Source | Mode | Notes |
|--------|------|-------|
| MLB StatsAPI | Gated network (`LiveStatsApiSource`) | CLI refuses `--network`. Tests use fixtures. |
| Kalshi lake | Catalog existing manifests | No lake writes |
| Kalshi discovery | Fixture / blocked-network / future live | Lands discovery envelopes only |
