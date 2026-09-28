# Query acceleration — completion report

1. **Baseline recorded.** Increment 2 warehouse timings remain the named bottleneck (45 341 ms CSV load; 10–23 s entry; 3–14 s path; 60–75 s cold RUN; frozen FIRST80 109 ms / N=290). Script: `ROLLER/scripts/benchmark_query_engine.py`.
2. **Bake-off measured.** Synthetic `79,80,80,80,79,80` has two upward 80 touches. A=5 transitions (0.018 ms), B=91-grid (0.053 ms), C=6 bars (0.017 ms). Recommendation A + compact bars.
3. **Indexes are facts.** Transitions, bars, as-of PBP, Kalshi settlement, universe partition, versioned manifest with checksums.
4. **CLI.** `python -m roller.research_query.indexes build --league NBA --season 2025-2026`.
5. **Fail closed.** Missing checksum, stale `dataset_version`, or out-of-coverage dates → `DATA_REQUIRED`. Absent index → full scan. Present-but-bad index does not silently scan.
6. **Planner.** `GENERIC_QUERY` only. Decides what to read. Envelope: `execution_mode`, `index_version`, `rows_scanned`.
7. **Same detectors.** Indexed path calls Phase 1 `observe_entry` on compact bars. No second Cross/Recovery formula.
8. **Result cache.** Keyed by `question_hash + dataset_version + index_version + code_version + operation_semantics_version`. Never `cache["FIRST80"]`.
9. **Reconciliation tests.** `tests/test_research_query_indexes.py` — raw crossings vs transitions; scan vs indexed population; stale/corrupt fail closed.
10. **Increment goldens.** Touch hashes omit unset `operation` / `direction` / `outcome`. Untagged `path_true` unchanged.
11. **FIRST80 unchanged.** Frozen executor path untouched. Generic provenance cannot claim `warehouse_frozen_v1`.
12. **No L2 / fills / settlement invention.** Empty markets stay `terminal_missing`.
13. **No Terminal Efficiency / XIB / MCD / W9.** Live trading and Risk were not modified.
14. **Docs.** `QUERY_ACCELERATION.md` (12 sections), `indexes/README.md`.
