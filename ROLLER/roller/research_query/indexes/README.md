# Observation indexes

These files are **facts**, not research answers.

- An observation index is not a research result.
- The query planner is not the semantic compiler.
- The index is not FIRST80 and never claims `warehouse_frozen_v1`.

Phase 1 detectors in `roller/research_query/operations.py` are the semantic authority.
Index builders persist tradable transitions, compact bars, as-of PBP, and Kalshi settlement.
They do not reimplement Cross, Bounce, Recovery, or extrema with a second formula.

```text
python -m roller.research_query.indexes build --league NBA --season 2025-2026
```

Output:

`ROLLER/data/{sport}/{season}/derived/research_query/indexes/rq_index_v1.0.0/{LEAGUE}/{tradable|last_trade}/`

ATP and WTA share `data/tennis/2025_2026` but write separate league leaves so they do not overwrite each other. LAST_TRADE_PRINT is never served from a tradable leaf.

Missing, corrupt, or stale indexes fail closed. Absence of an index falls back to full scan.
A present but unusable index does **not** silently full-scan a partial season.
