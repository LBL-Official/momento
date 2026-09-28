# NBA Bot 001 — FIRST78_67 strategy

Pure logic for `nba-001` policy `nba-001-v1`. No I/O. It does not submit
and must not depend on `momento-kalshi` or `momento-execution`.

Contract: `research/vital/bots/nba-001/strategy/execution_contract.json`.
Field map: `research/vital/bots/nba-001/strategy/FIELD_TO_CODE.md`.

```text
CANDLE PATH ≠ FILL
68 PREPARES LOCALLY — NO ORDER BEFORE THE ≤67 CLOSE
UNRESOLVED FIELD ⇒ ENTRY BLOCKED
```

The worker is `apps/nba-001` (`momento-nba-001`).
