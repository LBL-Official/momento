# ROLLER Terminal — Phase 0 Status

**Date:** 2026-09-07  
**Status:** COMPLETE (contracts only — awaiting acceptance before Phase 1)  
**Architecture:** Locked — research terminal for rolling empirical DB; not a FIRST80 strategy dashboard.

```text
AUTHORITY → RECONCILIATION → research_spec → VOCABULARY → ADAPTERS → API DRAFT
```

## Deliverables

| ID | Artifact | Path |
|----|----------|------|
| A | Authority matrix | `AUTHORITY_MATRIX.md` |
| B | FIRST80 reconciliation tests | `ROLLER/tests/test_first80_reconciliation_phase0.py` + fixture |
| C | Universal schema + samples | `research_spec.schema.json`, `RESEARCH_SPEC.md`, `samples/` |
| D | Vocabulary v0 | `research_vocabulary_v0.json` |
| E | Import-only adapter | `ROLLER/roller/dashboard_adapter/` |
| F | API surface draft | `API_SURFACE_DRAFT.md` |
| G | Research Object Model | `RESEARCH_OBJECT_MODEL.md` (aligned) |

## Validation

```bash
cd ROLLER
.venv/bin/python -m roller.dashboard_adapter.validate_samples
.venv/bin/python -m pytest -q tests/test_research_spec_v0.py tests/test_first80_reconciliation_phase0.py
```

Samples: FIRST80 runnable · fundamental/basis runnable · large-move **valid but not runnable** (unresolved).

## Explicitly not done

- No React / Phase 1 UI  
- No vocabulary compiler runtime  
- No HTTP server  
- No new EV / fee / scan mathematics  
- No Phase 1 authorization

## Phase 1 gate

Only after this contract is **accepted**:

```text
WHAT EXISTS?
  → BBALL1 universe
  → as_of / Data Explorer
  → Object Inspector
  → Research Terminal input shell (compile later)
```

Not: WHAT BACKTEST CAN I RUN?
