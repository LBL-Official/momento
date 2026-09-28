# NBA 80→40 reverse feature engineering

Research desk for one question: why NBA Q2 FIRST80 80→40 differs from Q3.

This is not Choosin Texas. There is no page, no book, and no new trading rule.

```text
LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
feature-store universe = locked asked-six NBA Q2∪Q3 N=604
280 / 314 / 290 / IN-VAL-OOS = slices, not stores
```

## Run

From `ROLLER/`:

```text
python -m roller.nba_8040_reverse_features
```

The run is fail-closed. It stops on `LOCK_MISMATCH`, `DATA_REQUIRED`, or
`LEAKAGE`.

## Artifacts

- `FEATURE_CONTRACT.md` — population, instance, timing, leakage
- `FEATURE_CLASSES.md` — A–P
- `features/pre80.parquet` — all 604, no outcome selection
- `labels/outcomes.parquet` — isolated targets
- `reports/event_path.parquet` — inspection only; future columns marked
- `reports/analysis.json` — measured tables
- `NBA_8040_REVERSE_ENGINEERING.md` — structural label

## Dependencies

pandas / numpy / pyarrow already in `ROLLER/pyproject.toml`.
PCA is `numpy.linalg.svd`. KNN is pairwise distances. No sklearn.
matplotlib is not a dependency; figures are static SVG.

## Absolute

- Do not edit `first80.py`
- Do not edit Confirm & Run `execute` / `compiler` / `load_dataset`
- Do not edit `research/choosin_texas/library/nba_2q_regular_8040_1lot_2026_27/book.json`
- Do not change live FIRST01 / 80/81/83/89
- Do not start W9 or warehouse Phase 21
- Do not treat PCA/KNN as a signal
