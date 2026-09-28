# CTO-W3 — MLB Game / PBP Reconstruction

**Status:** ACCEPTED / CLOSED (CTO 2026-08-26).  
**Authorization:** 2026-08-26 implementation grant.  
**Numbering:** Under this grant, **CTO-W3 = MLB game/PBP reconstruction layer**. Kalshi **market** reconstruction is **W4**. Do not implement W4 here.

W2 remains the event/PBP **engine** (`crates/research-event`). W3 **reuses** it. W3 does not fork the parser or state machine.

| Doc | Role |
|-----|------|
| [SPEC.md](SPEC.md) | Objective |
| [DEPENDENCIES.md](DEPENDENCIES.md) | Upstream/downstream |
| [CONTRACTS.md](CONTRACTS.md) | Owned vs consumed |
| [DATA_MODEL.md](DATA_MODEL.md) | Types |
| [PBP_RECONSTRUCTION.md](PBP_RECONSTRUCTION.md) | Pipeline |
| [GAME_STATE.md](GAME_STATE.md) | Replay |
| [IDENTITY.md](IDENTITY.md) | gamePk |
| [TIMESTAMPS.md](TIMESTAMPS.md) | Clocks |
| [COVERAGE.md](COVERAGE.md) | Honesty |
| [VALIDATION.md](VALIDATION.md) | Rules |
| [TEST_PLAN.md](TEST_PLAN.md) | Fixtures |
| [PROGRESS.md](PROGRESS.md) | Ledger pointer |
| [HANDOFF.md](HANDOFF.md) | W4 |
| [ACCEPTANCE.md](ACCEPTANCE.md) | Bar (CTO signs) |

Crate: `crates/research-reconstruction`  
CLI: `apps/research-w3`  
Derived: `Backtesting Suite/Foundation/W3/`
