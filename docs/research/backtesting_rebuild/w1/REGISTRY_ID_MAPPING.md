# W1-LEDGER ↔ PLAN-S ID mapping

Canonical PLAN IDs live in `docs/research/BACKTEST_ENGINE_WATERFALL_REGISTRY.csv`.  
W1-LEDGER IDs are **implementation-internal** (FLAG-001). They are not PLAN completeness.

| W1-LEDGER (job) | PLAN-S (CEO checkpoint) | Notes |
|-----------------|-------------------------|-------|
| W1-LEDGER-A1-S1…S4 | PLAN-W1-A1-S1…S4 | Ledger = inventory; PLAN-S1 = schema+fixtures |
| W1-LEDGER-A2-* | PLAN-W1-A4-* | Ledger provenance/envelope vs PLAN envelope v2 |
| W1-LEDGER-A3-* | PLAN-W1-A3-* | Integrity / checksum (ledger has extra gzip/parquet/pairing steps) |
| W1-LEDGER-A4-* | PLAN-W1-A2-* | Ledger coverage vs PLAN coverage_v2 |
| W1-LEDGER-A5-* | (availability audit) | Extra vs PLAN; not a PLAN ID |
| W1-LEDGER-A6-* | PLAN-W1-A1-S2 + catalog | Canonical manifest |
| W1-LEDGER-A7-* | PLAN-W1-A4-S3 observability | Observability tags |
| W1-LEDGER-A8-* | **not** PLAN-W1-A8 | Ledger A8 = local reports. PLAN-W1-A8 = Kalshi re-query **DEFERRED** |
| W1-LEDGER-A9-* | PLAN-W1-A3-S2 + A1-S4 | Guard + digest |
| W1-LEDGER-A10-* | PLAN-W1-A7-* | Fence / acceptance |

Do not copy W1-LEDGER COMPLETE into the PLAN CSV (FLAG-001).
