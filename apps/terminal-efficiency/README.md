# Terminal Efficiency Intelligence Layer

Isolated research package. Phases 0–6 only.

```text
TRAINING PIPELINE COMPLETE · PIT AUDIT PASS · MODEL SELECTION COMPLETE · MARKET EVALUATION NOT AUTHORIZED
```

Status: `docs/research/terminal_efficiency/CURRENT_STATE.md`.

```text
PHASE 7 OOS EVALUATION = NOT AUTHORIZED
LIVE TRADING = NOT AUTHORIZED
STRATEGY CONSTRUCTION = NOT AUTHORIZED
ROLLER FIVE-SCREEN / PRODUCER WIRING = NOT AUTHORIZED
```

Kalshi prices are never XIB/MCD features. Training works without candles.

## Commands

```text
python -m terminal_efficiency ingest --league NBA --season 2024-2025
python -m terminal_efficiency ingest --league NCAAB --season 2024-2025
python -m terminal_efficiency build-states --league NBA --season 2024-2025
python -m terminal_efficiency audit-leakage --league NBA --season 2024-2025
python -m terminal_efficiency train-xib --league NBA --freeze
python -m terminal_efficiency train-mcd --league NBA
python -m terminal_efficiency apply-candles --league NBA --season 2024-2025
python -m terminal_efficiency inspect-frozen --league NBA --season 2024-2025
```

`evaluate --season 2025-2026` exits not-authorized.

Outputs land under:

`Backtesting Suite/Data/{NBA,NCAAB}/{season}/warehouse/derived/terminal_efficiency/`

This package does not write to `ROLLER/` or change FIRST80.
