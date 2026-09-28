# ROLLER V2 — Implementation Summary

**Date:** 2026-09-08  
**Scope:** Frontend research workstation only. Phase 0–6 empirical stack unchanged.

## Verification

```text
TypeScript: PASS (npx tsc --noEmit)
Phase 0–6 regression: 63 passed
FIRST80_Q3 lock: n = 290 unchanged (not modified)
NCAAB_FIRST80_P5 lock: n = 721 unchanged (not modified)
```

## V2 IMPLEMENTED

### Navigation
- Persistent collapsible sidebar (~260px): Home, Research, Library, Explore, Templates, Phenomena, Dictionary, Docs
- Desktop-first graphite shell; quiet selected surfaces

### Research workflow
- Focused Research workspace modes: **Overview · Define · Results · Evidence**
- Object hero + status badges
- Click-to-focus **DetailDrawer** for population / measurements
- Existing builder + executor preserved under Define / Results

### Library
- `localStorage` UI library (`roller.v2.research_library.v1`)
- Save / rename / move / duplicate / delete / folders
- Explicitly **not** authoritative warehouse persistence

### Vocabulary
- Data Dictionary search over `/api/vocabulary` + `research_vocabulary_v0.json` + catalogs
- How-to-write-a-query guide (finite vocabulary)

### Documentation
- In-app Docs center with short operator pages (what / why / can / cannot / example)

### Templates

```text
TOTAL: 51
IMPLEMENTED: 2 (FIRST80_Q3, NCAAB_FIRST80_P5)
RUNNABLE: only when backend template id is present
STRUCTURAL / DRAFT / UNAVAILABLE: remainder — never fake routes
```

### Analytics (Results → Analytics)

| Metric class | Classification |
|--------------|----------------|
| Sample size, proportions | AUTHORITATIVE / DERIVED FROM AUTHORITATIVE DATA |
| Wilson 95% CI | DERIVED FROM AUTHORITATIVE DATA |
| Path volatility / max adverse | NOT AVAILABLE |
| EV / Sharpe / P&L / Kelly | ASSUMPTION REQUIRED → Scenario Analysis only |
| Scenario EV calculator | USER-SUPPLIED SCENARIO (visually separated) |

### Export
- Spec JSON, Results JSON, Measurements CSV, Population summary CSV, Full report JSON

### Explicit non-goals still preserved

```text
No Phase 7
No new authoritative population route
No fabricated fills
No fabricated EV blended into empirical results
No execution / live trading system
```

## Key paths

- `frontend/roller-terminal/src/App.tsx` — V2 shell
- `frontend/roller-terminal/src/v2/**` — navigation, catalog, library, views
- `frontend/roller-terminal/src/styles.css` — V1 tokens + V2 layout / larger type
