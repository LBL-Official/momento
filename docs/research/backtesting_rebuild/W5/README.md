# CTO-W5 — Event ↔ market synchronization (grant numbering)

**Status:** **IMPLEMENTED** (sync layer). W6 is not started.  
**Authorization:** granted 2026-08-26 (implementation). Canonical `StateTransition` / path packaging remains **downstream**.

| Doc | Role |
|-----|------|
| [W5_EVENT_MARKET_SYNC.md](../W5_EVENT_MARKET_SYNC.md) | Grant closeout |
| [../../architecture/w5-synchronization.md](../../../architecture/w5-synchronization.md) | Architecture |
| [S_OF_T_FIELD_CONTRACT.md](S_OF_T_FIELD_CONTRACT.md) | Layer-4 `S(t)` product shape (W4+W5+later) |
| [SPEC.md](SPEC.md) | Sync objective |
| [DEPENDENCIES.md](DEPENDENCIES.md) | W3 PBP + MATCHED trades |
| [CONTRACTS.md](CONTRACTS.md) | Sync meta; episode types reserved downstream |
| [ACCEPTANCE.md](ACCEPTANCE.md) | Done-when |
| [PROGRESS.md](PROGRESS.md) | Ledger |

**Do not merge W5+W6+W7 into one implementation.** Do not invent L2, mids, 1-second
grids, or opening depth.
