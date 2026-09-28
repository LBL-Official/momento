# Google Sheets Backtest Control Plane

> **Platform note (2026-08-26):** This control plane is **LEGACY_V1** for candle-era
> FIRST01 runs. It will evolve into Waterfalls 20–22 reporting for the new
> historical engine ([plan](HISTORICAL_ENGINE_DEVELOPMENT_PLAN.md)). Do not treat
> Sheets P&L rows as MLB research completion.

Research-only. Does **not** modify live trading.

## Architecture

```
Google Sheet (Backtesting Input)
        ↓ export/sync → local CSV
momento-backtest-runner process
        ↓ validate + ExperimentOverrides
FIRST01 EntryEngine / ExitEngine (immutable)
        ↓ ReplayDataset (COMPLETE manifests only)
Runs/FIRST01/YYYY/MM/YYYY-MM-DD_<run_id>/
        ↓ summary
Google Sheet (Backtesting Results)
```

**Strategy = WHAT** (`FIRST01` v1)  
**Parameters = HOW THIS EXPERIMENT RUNS IT** (sheet overrides)  
**Signals ≠ fills** — this runner reports signal counts only.

## Drive layout

Folder: [Momento Backtesting Suite](https://drive.google.com/drive/folders/1WKopI1xCPIHQ7yuPs3X10M5EFVhvvZlL)

| Asset | ID / URL |
|-------|----------|
| Backtesting Input | https://docs.google.com/spreadsheets/d/1l9t6SCUlg-ns_GvuOvRpci-AwymIalMKQoP-zP4i5Iw/edit |
| Backtesting Results | https://docs.google.com/spreadsheets/d/1ld4GqSgtjhYm9w5ejoOAutZKzDAjKL2wfzx--bGDo5A/edit |
| Control Plane README | https://docs.google.com/document/d/187zi0G66jk3vcC7LDGwzKO3oJ5bpotqqSRGdB0uei5o/edit |
| FIRST01 Runs (Drive) | https://drive.google.com/drive/folders/1HgdyVCZftvHMzdCdlpldyPBhFzpHXZTs |

Local mirrors:

```
Backtesting Suite/
  Data/                 # research Parquet (MOMENTO_RESEARCH_DATA_DIR)
  Strategies/FIRST01/
  Runs/FIRST01/...
  Google Sheets/
    Backtesting Input.csv
    Backtesting Results.csv
```

## Input columns (A–N)

Run ID · Ticker · Season · Time Frame · Entry Condition - Price Range ·
Entry Condition - Model · Exit Condition - Price Range · Exit Condition - Model ·
Status · Submitted At · Started At · Completed At · Result Spreadsheet · Error

Example:

| Ticker | Season | Time Frame | Entry Range | Entry Model | Exit Range | Exit Model | Status |
|--------|--------|------------|-------------|-------------|------------|------------|--------|
| KXMLBGAME, KXWNBAGAME | 25-26 | 5/1-5/15 | 80-83 | FIRST01 | FIRST01 | FIRST01 | QUEUED |

- `25-26` → season `2025-2026`
- `5/1-5/15` → `2026-05-01` … `2026-05-15` (Aug–Dec → start year; Jan–Jul → end year)
- Entry `60-63` overrides thresholds only; FIRST01.v1 defaults stay 80/81/83
- Exit `FIRST01` = native 50% VWAP loss; `40%` = supported fraction override

## CLI

```bash
cargo run -p momento-backtest-runner -- init-sheets
cargo run -p momento-backtest-runner -- process
cargo run -p momento-backtest-runner -- sheet-ids
```

Status machine: `QUEUED → VALIDATING → RUNNING → COMPLETE` (or `INVALID` / `ERROR`).  
COMPLETE rows are never re-run (Run ID idempotency).

## Drive sync workflow (no Sheets cell OAuth required)

Google Drive MCP can **read** Input/Results (CSV export) and **write** results by
creating/replacing spreadsheet files. Cell-level Sheets MCP OAuth is optional.

```bash
# 1) Agent/Drive: export Backtesting Input → local CSV
# 2) Optional demo data (synthetic COMPLETE partitions):
cargo run -p momento-backtest-runner -- seed-demo
# 3) Run QUEUED rows:
cargo run -p momento-backtest-runner -- process
# 4) Agent/Drive: upload Results CSV + Runs/FIRST01/<run_id>/ artifacts
```

Proven e2e (demo fixtures):

- Run ID `d8d84daf-4391-4ffa-91c2-68b9555aabd7`
- Status `COMPLETE`
- Entry signals: `1` (FIRST01 80→81 maker-eligible)
- Exit signals: `0` (signal-only; no fill simulation)
- Drive Results: https://docs.google.com/spreadsheets/d/1ld4GqSgtjhYm9w5ejoOAutZKzDAjKL2wfzx--bGDo5A/edit
- Drive run folder: https://drive.google.com/drive/folders/1Dg0FLbRjMzcSer8kw-rUunaUN20sGRIa


## Safety

- Depends only on `research-data` + `research-strategies` (+ core types).
- No `momento-execution`, `momento-risk`, or trading-engine imports.
- PRODUCTION ORDERS = 0 by construction.
