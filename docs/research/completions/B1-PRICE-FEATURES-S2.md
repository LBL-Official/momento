# Waterfall Step Completion Record

STEP ID: B1-PRICE-FEATURES-S2
TITLE: Complete price-dissection schema + A1 entry/exit target buckets
OBJECTIVE: Represent every framework field on the B1 snapshot (L2 as typed UNAVAILABLE), and use A1 entry/exit target buckets so research can ask when an 80–83 TRADE is descriptively different. Do not invent L2. Do not start W9. Do not change live FIRST01.

SCOPE: `crates/research-features` schema 1.1.0, A1 target module, analysis matrix, Foundation/B1 reports, architecture/research docs. W5/W6/W7/W8 read-only. No production trading trees.

INPUTS:
- Existing B1.1 extractors on W8 in-band entries
- Research-backtest A1 language: `entry_price_range` (default 80-83) and `exit_price_input` (FIRST01 / 50% / hard stops)

OUTPUTS:
- Snapshot fields for start sentiment, D80_trade, event history, ACCELERATING/DECELERATING, full L2 UNAVAILABLE slots, TRAIN-only TRADE z, A1 entry/exit outcomes
- `a1_bucket_report.json` (entry × exit × coarse condition; N_entries + N_unique_games)

CODE CHANGES: Feature schema 1.1.0; `a1_targets`; analysis lift/EV@80; no Risk/Execution/Kalshi deps.

DATA CHANGES: none to Data-Real; derived B1 only

SCHEMA CHANGES: `entry_snapshots` adds `start_sentiment`, `a1_entry_target` (B1.SCHEMA.1.1.0)

TESTS: sentiment buckets; A1 50% stop vs hold; event history causality; L2 still UNAVAILABLE; A1 matrix reports N_games.

VALIDATION: Bid/ask/mid/OBI/OFI/microprice remain UNAVAILABLE_SOURCE. Fair value reserved. Live 80/81/83/89 + 50% stop unchanged.

ARTIFACTS: Foundation/B1 reports + gitignored `features.sqlite`

GOOGLE DRIVE OUTPUT: none

GOOGLE SHEETS OUTPUT: none

KNOWN LIMITATIONS: Historical L2 UNAVAILABLE. A1 stop/horizon P&L is a TRADE-print path, not a fill. Full extract over W7 still required for a populated `a1_bucket_report.json`.

LOOKAHEAD / DATA LEAKAGE REVIEW: Features and event history use timestamp ≤ entry. A1 triggered exits require timestamp > entry. Settlement/hold is LABEL. z-scores fit on TRAIN only.

REPRODUCIBILITY: `snapshot_id` is sha256 of dataset version `B1.ENTRY_SNAPSHOT.2` + W8 opportunity id + entry observation id.

DEPENDENCIES CREATED: none new

DEPENDENCIES RESOLVED: same W6/W7/W8 stores as S1

NEXT STEP: STOP. Do not start B2, W9, ML classification, or live parameter changes. Run `momento-research-b1 --extract` when a populated report is needed.

FINAL STATUS: COMPLETE (feature layer 1.1.0). W9 not authorized and not started.
