# State machines (Milestone 1)

## Game / entry (MLB)

See `docs/architecture/mlb-strategy.md`.

```
WATCHING
  → FIRST_80_TRIGGERED
  → WAITING_FOR_81_CONFIRMATION
  → ENTRY_ELIGIBLE
  → POSITION_BUILDING / OPEN_PARTIAL
  → ENTRY_PAUSED_ABOVE_MAX_PRICE   (price > 83; not a lock)
       → resume Permitted if GAME_LOCKED has not occurred
  → GAME_LOCKED                    (first 89%; permanent entry lock)
```

`GAME_LOCKED` does not set lifecycle to Flat.

## Position lifecycle

```
Building
  → OpenPartial     (fill, remaining budget > 0)
  → OpenComplete    (remaining budget = 0)
  → Holding
  → StopTriggered   (signal; not flat)
  → LiquidationActive (exit in flight; not flat until fills)
  → SettlementPending
  → Flat            (liquidation fills reduce qty to 0)
  → Settled
```

No take-profit variant. Exit causes: `StopLoss`, `Settlement`.

## Order lifecycle

`NEW → SUBMITTING → ACKNOWLEDGED → WORKING → PARTIALLY_FILLED → FILLED`

Also: `CANCEL_PENDING`, `CANCELLED`, `REJECTED`, `EXPIRED`, `UNKNOWN`.

`UNKNOWN` requires reconciliation before retry.
