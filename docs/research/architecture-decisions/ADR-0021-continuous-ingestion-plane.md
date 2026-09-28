# ADR-0021 — Continuous historical + forward ingestion plane

## Decision

Acquisition and scheduling live in a cross-cutting **DATA-INGEST** plane. W1 remains immutable raw foundation. W2 remains canonical MLB event/PBP reconstruction. W3 remains Kalshi market reconstruction and is not this plane.

## Context

W1 catalogs Kalshi lake truth. W2 interprets official PBP. Recurring backfill and Sunday 00:00 Pacific forward-feed must not wait on W3, must not overwrite Data-Real, and must not let W2 consume uncommitted raw.

## Problem

If W1 or W2 owns the scheduler, they become concurrent writers and W3 is blocked on a giant one-shot historical project.

## Alternatives considered

1. Extend W1 foundation job to download PBP.
2. Extend W2 `collect.rs` as the permanent writer of all future raw.
3. Separate ingest plane that lands immutable raw, commits a W1 handoff, then invokes W2 as consumer.

## Decision made

Alternative 3.

## Rationale

Matches the required split: scheduler owns *when*; W1 owns *source truth*; W2 owns *event meaning*. Continuous feed can run after W3 starts.

## Consequences

- New crate `momento-research-ingest` and binary `momento-research-ingest`.
- New landing tree under `Foundation/Ingest/` (not Data-Real).
- Existing `Foundation/W2/raw/` is frozen historical collect; ingest must not overwrite it.
- Network StatsAPI is opt-in; tests use fixtures.

## Data/model implications

No fabricated partitions. Completeness is only claimed when the source returned bytes that committed.

## Testing implications

Idempotency, checksum preservation, partial failure, duplicate runs, missing dates, source failures, W1→W2 uncommitted refusal.

## Future compatibility

W3 reads coverage/sync indexes; it does not become the ingest writer.

## Status

ACCEPTED

## Date

2026-08-26

## Amendment (2026-08-26 W3 grant)

Under the 2026-08-26 control-plane grant, **CTO-W3** is the MLB game/PBP
reconstruction **layer** (now ACCEPTED / CLOSED) and **CTO-W4** is Kalshi market
reconstruction. This ADR’s original sentence that “W3 remains Kalshi market
reconstruction” is **superseded** for execution numbering. DATA-INGEST still
must not reconstruct `MarketState`.

