# Google Reporting Architecture (design only)

**Do not implement Drive/Sheets integration in this step.**  
**Canonical machine truth:** the research lake / future research DB — never a spreadsheet.

---

## 1. What already exists

### Identifiers (`crates/research-backtest/src/config.rs`)

| Asset | ID |
|-------|----|
| Suite folder | `1WKopI1xCPIHQ7yuPs3X10M5EFVhvvZlL` |
| Backtesting Input | `1l9t6SCUlg-ns_GvuOvRpci-AwymIalMKQoP-zP4i5Iw` |
| Backtesting Results | `1ld4GqSgtjhYm9w5ejoOAutZKzDAjKL2wfzx--bGDo5A` |
| FIRST01 Runs folder | `1HgdyVCZftvHMzdCdlpldyPBhFzpHXZTs` (docs) |
| Control Plane README (Doc) | `187zi0G66jk3vcC7LDGwzKO3oJ5bpotqqSRGdB0uei5o` |

Env overrides: `MOMENTO_BACKTEST_INPUT_SHEET_ID`, `MOMENTO_BACKTEST_RESULTS_SHEET_ID`, `MOMENTO_BACKTEST_DRIVE_FOLDER_ID`.

### Local mirrors

```text
Backtesting Suite/Google Sheets/
  Backtesting Input.csv
  Backtesting Results.csv
  frequency_reconcile_results_row.csv
```

Code: `sheets_csv.rs`, `sheets_workspace.rs`, `sheet_contract.rs`.  
CLI: `momento-backtest-runner` `process` / `init-sheets` / `sheet-ids`.

### Credentials / MCP

- Drive MCP (`plugin-google-drive-google-drive`) is the documented write path (upload CSV/spreadsheet files).
- Sheets cell-level MCP (`user-google-sheets`) is optional and has been `needsAuth` in this workspace.
- **No secrets in repo.** Do not add service-account JSON to git.

This control plane is **LEGACY_V1**: Input row → FIRST01 candle run → Results row. It is not MLB reconstruction completion.

---

## 2. Folder conventions today

```text
Drive: Momento Backtesting Suite
  Backtesting Input (Sheet)
  Backtesting Results (Sheet)
  FIRST01 Runs / YYYY / MM / <run_id>/   (artifacts)
Local: Backtesting Suite/Runs/FIRST01/YYYY/MM/YYYY-MM-DD_<run_id>/
```

Runs include `manifest.json`, `summary.json`, trades JSONL, diagnostics CSVs, validation markdown.

---

## 3. Target role of Google (Waterfalls 20–22, not now)

```text
Lake / research DB  ──machine──►  versioned artifacts (parquet, json)
                                └──human──►  Google Drive archive
                                              ├── Sheets (summary tables)
                                              └── Docs / folders (reports)
```

Drive is the **human-readable research archive**. Spreadsheets must not become the write-ahead log for historical truth.

---

## 4. Eventual report types (requirements list)

Each research run should eventually be able to publish:

| Report | Why |
|--------|-----|
| Run summary | Identity, versions, git/data checksums |
| Data coverage | Days, games, markets, PBP %, L2 % |
| Synchronization quality | Confidence histogram, unmatched games |
| Threshold statistics | First-touch counts 20–95, especially 80 |
| State transition statistics | Trigger mix, path completeness |
| Loser / winner classifications | After labels exist |
| PBP cohorts | Inning/outs/score buckets |
| Event-theta / market-theta cohorts | After those layers exist |
| Orderbook analysis | Only where observability allows |
| Model / hyperparameter / validation | Later waterfalls |
| Artifacts + provenance index | Links back to lake paths |

LEGACY Sheets columns (A–N Input) stay valid for **old** FIRST01 jobs. New engine should use **new** Sheets/tabs or a new spreadsheet so candle P&L is not mixed with reconstruction metrics.

---

## 5. Proposed Drive tree (implement later)

```text
Momento Research Archive/
  _index.md
  lake_catalog/                 # coverage exports, not raw ticks
  mlb/
    2025-2026/
      coverage/
      episodes/                 # summaries only
      runs/<engine_version>/<run_id>/
        README.md
        coverage.csv
        first_touch_80.csv
        sync_quality.csv
        provenance.json
  legacy_v1_first01/            # existing FIRST01 Runs — keep
```

Raw gzip/parquet stay on the machine lake (and later object storage). Drive gets **aggregates**.

---

## 6. Safety

- Reporting pipeline must not call Kalshi order APIs.
- Must not overwrite Data-Real.
- Must label LEGACY_V1 vs new-engine artifacts in every file name/header.
- PRODUCTION ORDERS from reporting = 0 by construction (same as today’s backtest-runner).
