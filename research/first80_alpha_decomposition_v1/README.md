# FIRST80 alpha decomposition v1

Research-only experiment. **Does not change live trading, FIRST01, Risk, or Execution.**

```
LIVE EXECUTION = FALSE
HISTORICAL CANDLE PATH ≠ ACTUAL FILL
```

## Run

```bash
/tmp/momento-first80-decomp/bin/python research/first80_alpha_decomposition_v1/src/discover_data.py
/tmp/momento-first80-decomp/bin/python research/first80_alpha_decomposition_v1/src/run_experiment.py
/tmp/momento-first80-decomp/bin/python -m pytest research/first80_alpha_decomposition_v1/tests -q
```

`scipy` and `matplotlib` are used only for exact tests, Clopper–Pearson intervals, and figures.

## Layout

| Path | Role |
|------|------|
| `EXPERIMENT_DATA_AUDIT.md` | Warehouse audit (write first) |
| `src/` | Modules A–D, persistence, robustness |
| `data/` | Derived parquet (not raw candles) |
| `results/` | CSV/JSON tables |
| `figures/` | PNG |
| `reports/` | Module + final markdown |
| Frozen FIRST80 | `warehouse/derived/nba/first80_execution_audit/` (read-only) |

## Classification

Exactly one of A / B / C / D as defined in `SPECIFICATION_LOCKS.json`.

Independent path-survival requires an **OOS interval on FIRST80−FIRST75 that excludes 0**. A raw point-estimate gap is not sufficient.

Regenerate reports without a candle rescan:

```bash
/tmp/momento-first80-decomp/bin/python research/first80_alpha_decomposition_v1/src/run_experiment.py --from-artifacts
```

**LIVE DEPLOYMENT: NOT AUTHORIZED**
