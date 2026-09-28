# Waterfall Step Completion Record

STEP ID: B1-PRICE-FEATURES-S1
TITLE: Price dissection and trade-classification feature engine
OBJECTIVE: Build deterministic, anti-lookahead feature snapshots around W8 observational 80–83 TRADE entries so later research can condition outcomes on baseball state, starting TRADE belief, and TRADE-price path. Do not invent L2. Do not start W9. Do not change live FIRST01.

SCOPE: `crates/research-features`, `apps/research-b1`, Foundation/B1 artifacts, architecture/research docs. W5/W6/W7/W8 read-only. No production trading trees. No Kalshi network.

INPUTS:
- W8 `first01_opportunities` with in-band entry (current run `w8-20260829T074403Z`)
- W7 `path.sqlite` TRADE observations
- W6 `state.sqlite` states/transitions/finals
- Optional observed StatsAPI envelopes for home/away identity

OUTPUTS:
- `Backtesting Suite/Foundation/B1/` reports + gitignored `features.sqlite`
- `docs/research/backtesting_rebuild/B1_PRICE_FEATURES.md`
- `docs/architecture/b1-price-features.md`

CODE CHANGES: Feature schema; extractors; TRADE-only microstructure provider; W6 settlement labels; chronological split metadata; conditional EV helpers. No Risk/Execution/Kalshi deps.

DATA CHANGES: none to Data-Real; derived B1 only

SCHEMA CHANGES: `feature_runs`, `entry_snapshots` (B1.SCHEMA.1.0.0)

TESTS: `crates/research-features/tests/b1_features.rs` plus module tests (side-aware lead, no future state, no future TRADE in features, L2 unavailable, deterministic IDs, one-per-game, settlement from W6, late-lead filter definition).

VALIDATION: W8 entries reconcile 1:1 into B1 primary snapshots. Duplicate game_id fails. Lookahead fails closed. Bid/ask/mid remain UNAVAILABLE_SOURCE.

ARTIFACTS: Foundation/B1 reports + gitignored `features.sqlite`

GOOGLE DRIVE OUTPUT: none

GOOGLE SHEETS OUTPUT: none

KNOWN LIMITATIONS: Historical L2 UNAVAILABLE. Identity requires observed envelopes; without them bound-side lead and settlement stay UNAVAILABLE. TRADE print is not a maker fill. Fair value reserved (not fit from settlement).

LOOKAHEAD / DATA LEAKAGE REVIEW: Features use observations and W6 states with timestamp ≤ entry. Outcomes require timestamp > entry. Settlement is labeled as LABEL. Fair value not computed.

REPRODUCIBILITY: `snapshot_id` is sha256 of dataset version + W8 opportunity id + entry observation id. `generated_at` is manifest-only.

DEPENDENCIES CREATED: `momento-research-features`, `momento-research-b1`

DEPENDENCIES RESOLVED: W6 StateStore::open_existing / load_states / load_transitions; W7 PathStore::open_existing / path_for_game; W8 first01_opportunities read-only

NEXT STEP: STOP. Do not start B2, W9, ML classification, or live parameter changes.

FINAL STATUS: COMPLETE (feature layer). W9 not authorized and not started.
