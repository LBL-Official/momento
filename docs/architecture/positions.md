# Positions and reconciliation (Milestone 5)

Strategy proposes. Risk approves. Execution executes. The position tracker
is fill-authoritative. P&L consumes fills, fees, and settlement events.

```text
ApprovedTradeIntent
  → Execution (paper or later Kalshi venue)
  → PositionEvent / Fill
  → InMemoryPositionTracker
       ├── GamePositionIndex  (one GameId → one PositionId)
       ├── orders + fills
       └── typed reconciliation
```

The tracker never creates a second `PositionId` for an unfilled remainder.
The Kalshi adapter still must not create `PositionId` values.

## Accounting

Actual exposure comes from fills only.

| Quantity | Meaning |
|---|---|
| submitted | requested size; not a fill |
| working | resting size; not a fill |
| filled | sum of actual fills |
| remaining target | approved budget − fill premium − entry fees |
| actionable remaining | zero after `GAME_LOCKED` |

A cancel does not erase prior fills. A late fill is applied to the existing
`PositionId` / `ClientOrderId`. Duplicate `FillId` values are ignored.

## Reconciliation

```text
UNKNOWN / timeout
  → RECONCILIATION_REQUIRED
  → RECONCILING
  → FOUND | NOT_FOUND | AMBIGUOUS
```

| Outcome | Meaning | New exposure |
|---|---|---|
| FOUND | venue identified the order; local state may be corrected from fills | allowed only after the gate returns Healthy **and** risk passes |
| NOT_FOUND | venue confirms absence; no fill is invented | same |
| AMBIGUOUS | insufficient or contradictory evidence | **blocked** |

A transport timeout is `UNKNOWN`, not `NOT_FOUND`, `CANCELLED`, `REJECTED`,
or `FILLED`. Ambiguous state is not retried automatically.

`VenueOrderSnapshot.presence`:

- `Found` / `NotFound` — venue evidence
- `Unknown` — timeout/partial payload; maps to `AMBIGUOUS`

## GAME_LOCKED

Permanent for **entry** only. Existing fills remain. Remaining target is
abandoned (`actionable_remaining_entry = 0`). The tracker does not flatten
or liquidate because of the lock.

## Settlement

`SettlementEvent` is authoritative. Proceeds are supplied by the caller.
This crate does not compute Kalshi `$1/contract` internally. A settled
position cannot be reopened.

## P&L

See `docs/architecture/pnl.md`. `ZeroFeeModel` remains a paper placeholder.
