# CTO-W8 — FIRST01 Strategy Replay

**Status:** **IMPLEMENTED** (observational FIRST01 replay).  
**Authorization:** Implementation grant 2026-08-27.  
**PLAN alias (not this grant):** PLAN-W9 / PLAN-W10 / PLAN-W17-A1 Greeks remain later work.  
**Owner:** W8 (`momento-research-replay`)

This directory’s older PLAN-W9 “Event / Market Greeks” package is **not**
what this grant implemented. Canonical architecture:

[W8_FIRST01_REPLAY.md](../W8_FIRST01_REPLAY.md)

| Doc | Role |
|-----|------|
| [SPEC.md](SPEC.md) | Historical PLAN-W9 Greeks draft (not this implementation) |
| [DEPENDENCIES.md](DEPENDENCIES.md) | Upstream / downstream |
| [CONTRACTS.md](CONTRACTS.md) | Historical draft contracts |
| [ACCEPTANCE.md](ACCEPTANCE.md) | Historical PLAN-W9 done-when |
| [PROGRESS.md](PROGRESS.md) | Ledger |

**This grant:** replay existing FIRST01 over accepted W7 EventMarketPath.
No fills, no P&L, no outcome labels, no invented L2, no W9.

Control plane: [../WATERFALL_MASTER_REGISTRY.md](../WATERFALL_MASTER_REGISTRY.md)
