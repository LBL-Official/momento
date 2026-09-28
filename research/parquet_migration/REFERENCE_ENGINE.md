# Reference engine

`roller.research_query.reference_engine.execute_reference` is the full-scan oracle.

It calls the same `operations.py` / `entry_engine` / `path_engine` detectors as Confirm & Run.
It never opens `rq_index_v1.0.0`. It never routes FIRST80 (`ReferenceEngineError`).

Optimized path: `execute_question` → planner → indexed bars → same detectors.

Invariant: `identities(reference) == identities(optimized)` and N matches goldens.

Tests: `ROLLER/tests/test_reference_vs_optimized.py`.
If they fail, stop. Do not rewrite goldens. Do not "fix" by changing Cross.
