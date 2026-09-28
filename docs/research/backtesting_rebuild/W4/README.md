# CTO-W4 — Kalshi market reconstruction

**Status:** **COMPLETE** (price-path foundation). W5 is not started.  
**Authorization:** Granted 2026-08-26 (this chat).  
**PLAN alias:** PLAN-W6 + PLAN-W7 (market path). **Not** PLAN-W3 (time sync).  
**Owner:** W4

This directory is the **execution** W4 pack under the 2026-08-26 grant.

```text
W4  = Kalshi MARKET reconstruction   (this waterfall)
W5  = event ↔ market synchronization (NOT this waterfall)
```

Older files in this folder described “Event ↔ Market Synchronization.” That
objective is **superseded**. Sync is **CTO-W5**. Do not implement
`SynchronizedState` here.

| Doc | Role |
|-----|------|
| [SPEC.md](SPEC.md) | Objective, interfaces, invariants, failure modes, tests |
| [CONTRACTS.md](CONTRACTS.md) | Owned vs consumed types |
| [DATA_MODEL.md](DATA_MODEL.md) | MarketPath / MarketPoint / completeness |
| [DEPENDENCIES.md](DEPENDENCIES.md) | Upstream / downstream / blockers |
| [TEST_PLAN.md](TEST_PLAN.md) | Required tests |
| [ACCEPTANCE.md](ACCEPTANCE.md) | Done-when (CTO still owns ACCEPTED/CLOSED) |
| [COVERAGE.md](COVERAGE.md) | How coverage is measured |
| [HANDOFF.md](HANDOFF.md) | W5 handoff: path exists; sync is not done |
| [PROGRESS.md](PROGRESS.md) | Ledger |
| [CAPABILITY.md](CAPABILITY.md) | Downstream gates (TRADES_ONLY usable; L2 not invented) |
| [RECONSTRUCTION.md](RECONSTRUCTION.md) | Bounded TRADES_ONLY reconstruct + W8–W11 funnel |
| [../W4_UNIVERSE_INVENTORY.md](../W4_UNIVERSE_INVENTORY.md) | Universe inventory + reconstruct counts |

Crate: `crates/research-market`  
CLI: `apps/research-w4`  
Artifacts: `Backtesting Suite/Foundation/W4/` only

**Honesty:** Reconstruct whatever observation tier is committed. Do not upgrade
candles or PIT REST snapshots to L2. Do not reconstruct all metadata-only
mapped pairs and call that a market engine. TRADES_ONLY is the broad
price-path universe.
