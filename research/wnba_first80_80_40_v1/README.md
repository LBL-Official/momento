# WNBA FIRST80 80→40 v1

Research-only observational backtest of the NBA FIRST80 close-path rule on
Kalshi `KXWNBAGAME`.

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
```

Definition is imported from `apps/nba-data/scripts/nba_80_40_execution_audit.py`.
It is not redefined.

## Data

Kalshi historic 1-minute top-of-book candles + trades for every settled
`KXWNBAGAME` market the public API returned (2025-05-22 through 2026-08-31).

Warehouse: `Backtesting Suite/Data/WNBA/2025-2026/warehouse/`

Ingest (resumable; skips COMPLETE ticker jobs):

```bash
cargo run -p momento-wnba-data --release -- discover \
  --data-dir "Backtesting Suite/Data"
cargo run -p momento-wnba-data --release -- download-all \
  --data-dir "Backtesting Suite/Data" --max-workers 1 --rps 1.5
```

Historical L2 is not available. Demo collector manifests are not used as candles.

## Backtest

```bash
/tmp/momento-first80-decomp/bin/python -m unittest discover \
  -s research/wnba_first80_80_40_v1/tests -v

/tmp/momento-first80-decomp/bin/python \
  apps/wnba-data/scripts/wnba_80_40_execution_audit.py
```

A priori splits (locked before results): TRAIN `game_date <= 2025-10-31`;
VALIDATION through `2026-07-15`; OOS after. Do not retune after seeing PnL.

**LIVE DEPLOYMENT: NOT AUTHORIZED**
