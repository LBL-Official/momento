# CTO-W5 — Event ↔ Kalshi market time synchronization

**Grant:** implement the join. **Not W6.** No transition matrices, features,
Greeks, ML, live trading, Kalshi network, credentials, or invented L2.

Full contract: [`docs/architecture/w5-synchronization.md`](../../architecture/w5-synchronization.md).

## Purpose

Deterministic AS-OF mapping:

```text
MarketObservation(t) → latest W3 event with effective_time ≤ t → SynchronizedMarketObservation
```

W6 can ask “what baseball state existed at this market print?” without
implementing clocks.

## Authoritative dataset

PBP ∩ MATCHED Kalshi **trades** (not the 238 UNMATCHED W4 price-path set).

Brief target: 1,684 games / 3,368 contract sides. Actual measured counts live in
`Backtesting Suite/Foundation/W5/synchronization_report.json`.

## Timestamp contract

UTC internally. Source string + offset preserved. Host TZ never used.
Retrieval time never orders. Precision is measured, not upgraded.
No invented clock correction.

## Boundary rule (W6 depends on this)

| Observation time | Applicable game state | Status / relation |
|------------------|----------------------|-------------------|
| `t < first PBP` | none | `BEFORE_FIRST_EVENT` / `BEFORE_EVENT` |
| `event_A < t < event_B` | after(A) | `SYNCHRONIZED` / `AFTER_EVENT` |
| `t == event_B` | after(B), with before(B) also stored | `AT_EVENT` / `AT_EVENT` |
| `t > last PBP` | none (not snapped) | `AFTER_LAST_EVENT` |

W3 event time = instant the event becomes effective. Exact equality therefore
uses the after-state **and** is labeled `AT_EVENT` so the collision is visible.

`next_event_*` is diagnostic only.

## Anti-lookahead

No future PBP, final score, settlement, later occupancy/outs/count/inning.
Tests in `crates/research-sync/tests/w5_sync.rs`.

## Identity

Existing MATCHED `game_pk` ↔ ticker. No price/time guessing.
Unmatched catalog rows stay in ingest artifacts.

## Observation types

`TRADE | QUOTE | CANDLE | L2_SNAPSHOT | L2_DELTA`. This cohort is TRADE-only.
Trades are not quotes. Candles are not L2. Missing L2 stays missing.

`first_observed_price_cents` ≠ starting price / market open.

## Quality

ADR-0003: `EXACT` only when lag_ms = 0. Gap threshold 5s →
`SYNCHRONIZED_WITH_TIMESTAMP_GAP`.

## Code

- Crate: `crates/research-sync`
- CLI: `apps/research-w5` (`momento-research-w5 --sync`)
- Store: SQLite WAL under Foundation/W5 (gitignored db)

## W6

Not started. `StateTransition` / `GameMarketEpisode` / tensors are forbidden in
this crate.
