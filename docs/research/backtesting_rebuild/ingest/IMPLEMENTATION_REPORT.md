# DATA-INGEST implementation report

**Date:** 2026-08-26  
**W1:** CEO **ACCEPTED / CLOSED** ([W1_CEO_ACCEPTANCE.md](../W1_CEO_ACCEPTANCE.md))  
**W3:** **not started**

## What was built

A cross-cutting ingestion control plane (`momento-research-ingest` + `momento-research-ingest` binary):

- Sunday 00:00 Pacific weekly schedule (`next_weekly_ingest`)
- Exclusive lock (fail-closed concurrent writer)
- Immutable landing (same SHA-256 → no-op; different bytes → version sibling + alert)
- W1 provenance + checksum-verified commit handoff
- W2 canonicalize **only** COMMITTED + checksum-matched StatsAPI artifacts
- Kalshi **catalog of existing manifests** (no Data-Real writes, no fabricated COMPLETE)
- Per-run audit / manifest / handoff / provenance JSON
- Bounded retries (not infinite)

PBP windows for 2024–2025 and 2025–2026 exist as `DateWindow` helpers. Live StatsAPI is compiled (`LiveStatsApiSource`) but **not** invoked by the CLI (`--network` exits 2). This session did **not** download historical PBP and did **not** write Data-Real.

## Ownership (concurrent writers)

See [ARCHITECTURE.md](ARCHITECTURE.md). Ingest writes only `Foundation/Ingest/**`. Data-Real, production, W1 derived tree, and frozen `Foundation/W2/raw` are not ingest-writable.

## Tests

`cargo test -p momento-research-ingest` covers: idempotency, checksum preservation, partial failure, duplicate runs, missing dates, source failure, W1→W2 uncommitted refusal, committed consume, lock, version conflict, Kalshi honesty, lake-write refusal.
