# Phase 16 — Parquet sole source for new warehouse-backed execution

Measured: **2026-09-13**. Audit + fail-closed tests. Not a Confirm & Run rewrite.

```text
PARQUET IS NOW THE SOLE SOURCE FOR NEW WAREHOUSE-BACKED RESEARCH EXECUTION
```

Confirm & Run remains CSV + `rq_index` + FIRST80 as an **explicit legacy
boundary**. `execute.py`, `compiler.py`, `load_dataset`, `planner.py`, and
`official_settlement.py` were not edited.

---

## Audit (`ROLLER/roller/warehouse/*.py`)

| Surface | CSV / Suite / FIRST80 / rq_index |
| --- | --- |
| `query_context.get_research_context` | Phase 8 parquet only. No `read_csv`, `load_dataset`, `rq_index`, FIRST80. |
| `coverage.get_catalog` | Phase 8 parquet + `manifest.json` + orderbook `capability.json`. |
| `research_compiler.compile_research` | Catalog + question. No row scan. No CSV. |
| `conditional_backtest` | Executes a `ResearchContext` already loaded from parquet. |
| `identity` / `observations` / `pbp_events` / `market_link` / `settlement` | Build-time CSV / Suite reads (ingest publishers). Not the new query path. |
| `catalog.catalog()` | Confirm & Run CSV inventory. New path uses `coverage.get_catalog`. |
| `loader.load_canonical_csv` | Wraps `admin.load_dataset`. Unused by `get_research_context`. |
| `gap_audit` / `validate_cmd` | Inventory / validation. Not query execution. |

No ticker-body guess, no hidden discovery, no FIRST80 shortcut on the new path.

Live warehouse `manifest.json` (read 2026-09-13, not rewritten):

```text
updated_at: 2026-09-13T06:28:48Z
observation_basis: TRADABLE_YES_BID
observation_rows: 6165183
pbp_rows: 780137
games: 1362
markets: 2724
links: 2724
settlements: 2724
pbp_pit_aligned_to_candles: false
tick_data_available: false
orderbook_data_available: false
candle_pit_field: available_at
```

SHA-256 of published files (bytes on disk; measured, not invented):

```text
manifest.json                 b9f02c7b88bd1680729d6552ed3cafeb94fe36624c8f205ebb34ab5981d9f231
games/games.parquet           a272362759bf1124ec9529e6b8ca3afc086c341259af1450c6ded57bdcf837cb
markets/markets.parquet       37168d0110c444162c75e0156c81b2ee10fc890d6145d5f7ad443a2f0680f7df
game_market_links/links.parquet 637afdb47169bb60b319a8360b81575ab2e0304aa60bdb8d9561e7105abeecdd
settlements/settlements.parquet 439b2e989cfd1c8099de7efe5142e9d51373409681004b8036a93fb2c99616e5
```

Confirm & Run files were not edited in this pass. Isolation AST checks on
`execute.py`, `compiler.py`, `admin.py`, `planner.py`,
`official_settlement.py`, and `first80.py` forbid imports of
`query_context` / `conditional_backtest` / `auto_ingest`. `load_dataset`
source still has no `read_parquet`.

---

## Tests

`ROLLER/tests/test_parquet_execution.py`:

- Warehouse-backed `ResearchQuestion` still compiles + loads + runs when
  `load_dataset`, CSV `catalog()`, and FIRST80 are monkeypatched to raise.
  Live CSV was **not** deleted.
- Live 2025-10-10 Q2: `plan_hash`
  `4547787d8dfdb8c40717d7321e399179e868a67f0b069cadabc3f7964f9ffa67`,
  Reference ≡ Optimized, population 0, `result_hash`
  `1b0ce3dc4fb863a2c9b7517669ca1e5936a02d07dab4905d896ab2dc8894a0f6`.
- `get_research_context` source has no `read_csv` / `load_dataset` / `rq_index`.
- Isolation: `test_load_dataset_still_csv` and
  `test_live_execute_paths_do_not_import_entities` (also kept on
  `test_warehouse_entities.py`).

---

## Boundary (locked)

```text
new path:  compile_research / get_research_context / run_conditional_backtest
           → Phase 8 parquet

legacy:    Confirm & Run execute / load_dataset / rq_index / FIRST80
           → CSV (unchanged)
```

Phase 16 complete. Next authorized phase is **17**. Do not start it from this report.
