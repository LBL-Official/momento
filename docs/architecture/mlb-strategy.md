# MLB strategy (Milestone 6)

Strategy proposes. Risk approves. Execution executes. The tracker is
fill-authoritative.

```text
MarketEvent
  → MlbStrategy::observe
  → MlbDirective::{Build(TradeIntent), CancelRemainingEntries, PauseEntry, StopWatch, ExecuteStop}
  → Risk (for Build only)
  → Execution
```

This crate does **not** depend on `momento-kalshi` or `momento-execution`.
It does not compute bankroll, fees, or Kalshi orders.

## Qualifying price (fail closed)

Authoritative MLB observation (strategy spec, 2026-08-24):

```text
qualifying_price = yes_bid_dollars  →  MarketEvent.bid
```

Kalshi has no official mid. Adapter `mid` remains `None`. M6 does not invent
`(bid+ask)/2`, does not use last trade, and does not use YES ask as the
80/81/89 observation.

Convert `yes_bid_dollars` only when it maps exactly onto integer-cent
`Price`. `price_ranges[].step` must be a positive integer-cent tick; sub-cent
or off-grid quotes fail closed and produce no signal. Missing YES bid = no
signal.

Ask is required on a valid quote solely so maker-only entry never rests at
or through the ask. Last may be present on the event and is ignored for
80/81/89. Missing bid/ask, inverted bid/ask, stale data, or
receipt-before-exchange: no 80/81/89 trigger and no entry intent.

## State machine

```text
WATCHING
  → FIRST_80_TRIGGERED / WAITING_FOR_81
  → ENTRY_ELIGIBLE
  → POSITION_BUILDING   (partial fills; same PositionId)
  → POSITION_OPEN       (actual remaining target is 0)
  → GAME_LOCKED         (first 89% YES bid; permanent)
```

`>83` pauses entry. It is not `GAME_LOCKED`. Return to 80–83 may resume
only if the game is not locked.

## First 80 / 81 / 89

- First YES bid ≥ 80¢ on a valid quote is persisted (side, market, timestamps,
  bid/ask, depth, optional game-state note).
- 81 confirmation must be the same `GameId` / `MarketId` / `Side`.
- Opposite-side 81 does not confirm and does not switch the candidate.
- First YES bid ≥ 89¢ on the relevant market (candidate side after first 80;
  any side before first 80) permanently locks entry.
- 89 emits `CancelRemainingEntries` when working/UNKNOWN entry exists.
  It does not liquidate. It does not create a `PositionId` for a zero fill.

## Entry intent

Maker-only, limit in 80–83, never ≥ ask (does not cross). Desired exposure
is `RemainderOfApprovedBudget`. Risk sizes the incremental amount. Fees
stay in `FeeModel`.

## Stop

`StopWatch` records proposed VWAP of actual entry fills (once).

`ExecuteStop` fires when the YES bid is at or below 50% of that VWAP
(`ProposedHalfEntryStop`: integer division of hundredths of a cent).
The host submits a Kalshi reduce-only IOC ask at the current best YES bid.
Partial liquidation is retried until remaining filled quantity is zero.
UNKNOWN liquidation is reconciled, not blindly resubmitted.

89% GAME_LOCK does not emit `ExecuteStop`.

No take-profit. No discretionary exit. Exits: stop-loss path or venue settlement.

## Persistence

`MlbStrategy::snapshot` / `restore` preserve first-80, first-89, and
`GAME_LOCKED` across restart/replay.
