# Paper execution (Milestone 3)

`PaperExecutionEngine` submits only `ApprovedTradeIntent`.

```text
TradeIntent
  → PaperRiskEngine
  → ApprovedTradeIntent
  → PaperExecutionEngine
  → PaperExecution (deterministic venue)
  → fills/cancels/unknown
  → Risk reservation ledger
  → InMemoryPositionTracker
  → AuditLog (same append-only log as Risk)
```

Execution does not approve exposure and does not duplicate reservation math.
Fill premium is `contracts × price`. Fees come from the injected `FeeModel`
(`ZeroFeeModel` is a paper placeholder, not Kalshi economics).

UNKNOWN requires reconciliation (`Found` / `NotFound` / `Ambiguous`).
GAME_LOCKED cancels working entry and blocks new entry; it does not flatten.
See `docs/architecture/positions.md` for the M5 tracker.
