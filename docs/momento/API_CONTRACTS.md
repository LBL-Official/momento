# Momento Systems — API Contracts

Phase 2 mounts `/momento/*` adapters on `:8791`.
Phase 4 typed models live in `ROLLER/roller/momento/contracts.py`.

Do not duplicate engines merely so they appear under `/momento`.

## Planned façade (not mounted)

```text
GET /momento/systems
GET /momento/systems/{system_id}
GET /momento/systems/{system_id}/logic
GET /momento/systems/{system_id}/health
GET /momento/systems/{system_id}/schema
GET /momento/dataflow
GET /momento/health
```

Existing APIs stay:

```text
:8791  /health /warehouse-research /research-query /superasi
       /choosin-texas /austin /vital /auto-roller /stax /jump /systimo
:8792  /health /observe
:8787  research-api (submodule pointer only)
```

## Named objects

GameState, MarketState, OddsSnapshot, PathModelSnapshot,
TerminalModelSnapshot, TradeSignal, TradeBreakdown, PositionStratum,
PositionSnapshot, RiskAssessment, HedgeAnalysis, RVHedgeAssessment,
TargetExposure, ExecutionIntent, ExecutionReport, Fill,
PositionReconciliation, SystemHealth.

Required metadata on every future object:

- `schema_version`
- `generated_at`
- `as_of`
- `source_system`
- game/event identity
- provenance

No silent future leakage.

## Existing versioned contracts (leave)

These are not replaced. They may later adapt into the names above.

- SuperASI `superasi_package_v1`
- STAX `stax_v1`
- Base TE `SCHEMA_VERSION=1.0.0`
- FIRST80 `frozen_v1`
- Choosin book `choosin_texas_book_v1`
- Austin feature registry and experiment hashes
- XIB frozen identity tuple + `artifact_manifest_hash`
- B1 `B1.SCHEMA.1.1.0`
