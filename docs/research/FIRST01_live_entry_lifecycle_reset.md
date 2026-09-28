# FIRST01 Live Entry Lifecycle — Reset / Re-entry Audit

Source: `strategies/mlb/src/strategy.rs`, `strategies/mlb/src/state.rs`,
`crates/core/src/position.rs` (`can_attempt_entry`).

## What creates an entry intent?

1. YES bid ≥ 80 records `first_80` (MarketId + Side sticky forever for the game).
2. Same market+side YES bid ≥ 81 sets `confirmed_81`.
3. Maker limit valid (80–83, bid < ask).
4. Gates clear: not kill/recon/unknown, not `has_working_entry`, not
   Settled/StopTriggered/LiquidationActive/SettlementPending.
5. Phase ∈ {EntryEligible, PositionBuilding}, not PositionOpen.
6. Emits `MlbDirective::Build` for the **bound** market (from `first_80`).

## What prevents a second independent FIRST01 trade?

| Condition | Effect |
|-----------|--------|
| `first_80` sticky | Opponent market/side never confirms sequencing |
| `has_working_entry` | No Build while resting entry exists |
| `PositionOpen` (filled>0, remaining budget ≤0) | No further entry |
| `can_attempt_entry` false for Flat / OpenComplete / Settled / Holding | Permanent block after lifecycle ends |
| `GameLocked` (≥89) | Permanent; cancels working entries; does not flatten |

## Unfilled order then cancel?

Live may emit **another Build** for the **same** `first_80` opportunity while
phase returns to `EntryEligible` and `has_working_entry=false`. That is the
**same** game lifecycle / same position id — not a new FIRST01 trade.

## After fill / flat?

`filled_quantity` remains > 0 → phase becomes `PositionOpen` when remaining ≤ 0.
`can_attempt_entry` rejects `Flat` and `OpenComplete`. **No second independent
FIRST01 opportunity for that game.**

## Research mapping

`canonical_lifecycle_consumed` sticky once the first opportunity is created.
Matches live: one canonical FIRST01 opportunity per GameId for the game's
entry lifecycle; remainder Builds (if any) attach to the same opportunity.
