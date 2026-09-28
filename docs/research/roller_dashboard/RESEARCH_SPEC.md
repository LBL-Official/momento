# Research Spec v0

**Schema:** `research_spec.schema.json`  
**Model:** `RESEARCH_OBJECT_MODEL.md`  
**Permanent query format.** Natural language is a compiler input only.

```text
UNIVERSE → POPULATION → RESEARCH OBJECT → MEASUREMENT → RESULT
→ (optional) ECONOMIC → PORTFOLIO
```

---

## Required fields

| Field | Role |
|-------|------|
| `schema_version` | Must be `research_spec_v0` |
| `universe` | e.g. `BBALL1` |
| `anchor` | Entry / event definition |
| `information_regime` | e.g. `CANDLE_1M`, `POINT_IN_TIME` |
| `execution_interpretation` | Default research: `OBSERVABLE_PATH_ONLY` |
| `definition_versions` | Explicit engine bindings |
| `caveats` | At least one disclosure string |

## Optional but first-class

| Field | Role |
|-------|------|
| `population_binding` | Leagues, ASKED_SIX, P5, locked population; optional `seasons` / `season_months` / `season_weeks` (STRUCTURAL until a population route applies them) |
| `state_filters` | AND/OR/NOT tree |
| `path_conditions` / `terminal_conditions` | Forward / settlement |
| `measurement_requests` | F_t, Greeks, rates — **not edge** |
| `sample_binding` | as_of, train/val/forward |
| `economic_layer` / `portfolio_layer` | Phase 7 consumers; null/absent OK |
| `persistence` | ephemeral / saved / frozen / locked_population |

## Freeze trilogy

| `persistence.kind` | Meaning |
|--------------------|---------|
| `saved` | Mutable named work |
| `frozen` | Immutable spec + dataset + definitions + result snapshot |
| `locked_population` | Immutable member set (`population_hash`) |

## Run gate

A spec **must not run** if:

- `anchor.unresolved_parameters` is non-empty, or  
- any path/terminal `kind` is `UNRESOLVED`, or  
- `execution_interpretation` is `UNRESOLVED` without user confirmation, or  
- required `definition_versions` for requested measurements are missing.

## Samples

| File | Demonstrates |
|------|----------------|
| `samples/first80_q3_path_terminal.json` | FIRST80 Research Object with explicit warehouse binding |
| `samples/observation_large_move_unresolved.json` | Observation study — **invalid for run** until threshold resolved |
| `samples/fundamental_basis_measurement.json` | Measurement study without FIRST80 |

Validate with the Phase 0 adapter: `python -m roller.dashboard_adapter.validate_samples`.
