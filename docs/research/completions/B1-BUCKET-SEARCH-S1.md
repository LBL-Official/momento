# Waterfall Step Completion Record

STEP ID: B1-BUCKET-SEARCH-S1
TITLE: Exhaustive 80–83 / A1 exit cohort search
OBJECTIVE: Rank TRADE-print modeled A1 entry×exit×feature cohorts with chronological OOS, game-level independence, BH FDR, and W8 recon. Not a trading rule. Do not change live FIRST01.

SCOPE: `crates/research-features` search/recon, `momento-research-b1 --extract/--search`, Foundation/B1 reports. W5/W6/W7/W8 read-only. No production trees.

INPUTS: W8 `w8-20260829T074403Z` (2884 in-band entries); W7/W6 stores; B1 feature extract 2884 snapshots.

OUTPUTS: `Backtesting Suite/Foundation/B1/b1_*.json`, `b1_research_report.md`, `b1_search_summary.md`.

CODE CHANGES: Search engine, recon, CLI `--search`. No Risk/Execution/Kalshi.

DATA CHANGES: derived B1 only. Data-Real untouched.

VALIDATION: first80 late-lead2 hold n=254 / +$33.88 matches published full-universe audit. Prior 110-row keys were not persisted. Extract gate COMPLETE 2884/2884. 8894 candidates. BH q=0.10.

KNOWN LIMITATIONS: TRADE_PRINT_MODELED. L2 UNAVAILABLE. No fees. Horizon findings are not settlement findings.

NEXT STEP: STOP. No B2, W9, or live change.

FINAL STATUS: COMPLETE (research analysis). Live FIRST01 unchanged.
