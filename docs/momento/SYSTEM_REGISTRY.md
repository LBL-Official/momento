# Momento Systems — Registry

**SSOT:** [`momento/registry/systems.yaml`](../../momento/registry/systems.yaml)

Frontend and backend must both consume this file.
Do not hardcode a second map.

```text
schema_version: momento_systems_registry_v1
code_version:   momento_systems_v0.1.0
len(systems) == 19
live_execution: false
```

## Required fields

id, display_name, short_name, bracket_round, bracket_position, purpose,
status, version, implementation_paths, research_paths, frontend_target,
backend_target, api_namespace, upstream_systems, downstream_systems,
input_contracts, output_contracts, health_check, feature_flags,
live_capability, migration_sources, notes.

## IDs

`database`, `data_analysis`, `fair_odds_modeling`, `in_house_odds_modeling`,
`trade_breakdown`, `position_stratification`, `hedging_analysis`,
`relative_value_hedging`, `data_modeling`, `game_modeling`,
`dynamic_risk_engine`, `position_management`, `signal_generation`,
`algorithmic_execution`, `momento_systems`, `system_maintenance`,
`data_ingestion`, `trade_reconciliation`, `system_orchestration`.

## Status vocabulary

- `COMPLETE` — working product owns the problem.
- `PARTIAL` — real code exists; mandate is incomplete or research-only.
- `NOT_IMPLEMENTED` — placeholder. Do not disguise as complete.

Every `live_capability` is `false` in V0. MLB 001 live exists outside this
freeze and must not be modified by it.

## Loader

[`ROLLER/roller/momento/registry.py`](../../ROLLER/roller/momento/registry.py)
parses a YAML subset. No PyYAML dependency.

Tests: [`ROLLER/tests/test_momento_registry.py`](../../ROLLER/tests/test_momento_registry.py).
