# Systimo V0 specification

```text
LIVE EXECUTION = FALSE
SYSTIMO REGISTERS AND OPERATES THE TUNNEL
SOURCE SYSTEM ─────────► CONSUMER SYSTEM
19 SYSTEMS ≠ 20
CANDLE PATH ≠ FILL
Austin 604 ≠ Choosin 936 ≠ asked-six 1182
```

Systimo is the System Maintenance **product Frontend**. It registers
connections. It does not become the source. It does not replace Momento LS
live-host observe. It does not own Austin, Choosin, Vital, or warehouse data.

| Role | Product | Keep |
|---|---|---|
| System Maintenance Frontend | Systimo `:5193` `/systimo` on `:8791` | This spec |
| Live-host observe adapter | Momento LS `:5181` `:8792` | Unchanged |
| Ingest orchestration | `ROLLER/roller/maintenance/update.py` | `data_ingestion` |

CSV under `research/systimo/` is SSOT. Optional DuckDB/SQLite indexes are
rebuildable only. `momento/registry/systems.yaml` is discovered evidence of
the 19-bracket via `load_registry()`. Drift is `DRIFT` /
`UNREGISTERED_INTERFACE` / `MISSING_INTERFACE`, never silent rewrite.

See:

- [`DATA_MODEL.md`](DATA_MODEL.md)
- [`CONNECTION_CONTRACT.md`](CONNECTION_CONTRACT.md)
- [`QUERY_ENGINE.md`](QUERY_ENGINE.md)
- [`GOVERNANCE.md`](GOVERNANCE.md)
- [`AGENT_RUNTIME.md`](AGENT_RUNTIME.md)
- How-to: [`docs/operations/SYSTIMO.md`](../../docs/operations/SYSTIMO.md)

## Absolute

- No Kalshi. No `ENABLE_LIVE_TRADING`. No start/stop `momento-live.service`.
- Do not edit `first80.py`, live FIRST01 / 80/81/83/89, `book.json`, W9,
  warehouse Phase 21, MLB 001.
- Do not mix N 604 / 936 / 1182. Lock drift → `INTEGRITY_DRIFT`. Do not
  update expected N.
- Do not duplicate Austin/Choosin/ROLLER warehouses.
- Writes/control default DENY. Jump tunnels are QUERY only.
- Position Management stays `NOT_IMPLEMENTED`.
- Not a 20th system. Not System Orchestration. Not program 13 RV HFT.
