# ADR-0015 — Google Sheets architecture

# Decision

Google Sheets is the **human research index**, not the database and not the
experiment write-ahead log. LEGACY_V1 Input/Results remain valid for candle
FIRST01 jobs. The new engine uses new tabs or a new spreadsheet.

# Context

Existing sheets: Backtesting Input, Backtesting Results. Local CSV mirrors
under `Backtesting Suite/Google Sheets/`. Cell-level Sheets OAuth has been
`needsAuth` in this workspace; Drive file upload is the documented path.

# Problem

Mixing reconstruction metrics into candle P&L columns would corrupt both
meanings. Treating Sheets as source of truth would invite silent edits.

# Alternatives Considered

1. Sheets as canonical store.
2. Abandon Sheets.
3. Sheets as indexed visibility into versioned artifacts.

# Decision Made

Alternative 3. Sheets should index:

- datasets, runs, validation
- opportunities, trades, classifications
- model experiments, metrics, errors
- data coverage, synchronization quality
- model versions, deployment candidates

New engine must **not** mix candle P&L with reconstruction metrics.
Sheets is **not optional** after Waterfall 21. Implementation is deferred
until then.

# Rationale

Executives and researchers need indexed visibility without making a spreadsheet
the ledger.

# Consequences

LEGACY columns A–N stay for old jobs. Env overrides remain
`MOMENTO_BACKTEST_*`. No service-account JSON in git.

# Data/Model Implications

Sheet rows are views. Re-runs must be reproducible from lake + run_id, not from
edited cells.

# Testing Implications

LEGACY control-plane tests remain for FIRST01 candle runner. New contract tests
in W21.

# Future Compatibility

Index can point at Drive folders and lake URIs.

# Status

ACCEPTED (implementation deferred to Waterfall 21)

# Date

2026-08-26
