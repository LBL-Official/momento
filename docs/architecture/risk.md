# Risk and fees (Milestone 2)

Risk approves or rejects `TradeIntent`. It does not submit orders or mutate fills.

## FeeModel

```text
Risk
  ↓
FeeModel
  ↓
ZeroFeeModel     ← M2 temporary paper placeholder
  ↓
KalshiFeeModel   ← later, after official docs
```

`ZeroFeeModel` returns `$0` estimates. That is **not** Kalshi economics.

## Reservation

`used = actual_fill_premium + entry_fees_paid + open_reservations`

UNKNOWN reservations are not released until reconciliation (`NotFound` may release).

## Available capacity

`AvailableCapacity` / `SnapshotPaperBalance` uses the weekly snapshot bankroll.
Live venue balance is not implemented and must not be read from Kalshi in M2.
Liquidation proceeds are not recycled into entry capacity.

## Open MLB position cap

Risk is the authority for occupancy. Confirmed: at most five simultaneously
open MLB positions.

A slot is occupied when a `PositionId` has actual non-zero open contracts, or
when a first-entry reservation is pending (so concurrent approvals cannot
create a sixth). A reservation with zero fills does not persist after cancel
or `NotFound`. `GAME_LOCKED` positions continue to occupy a slot until the
position is flat or settled. UNKNOWN / AMBIGUOUS reconciliation fails closed
and blocks a new slot.
