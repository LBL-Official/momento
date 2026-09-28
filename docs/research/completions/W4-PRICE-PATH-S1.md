# Waterfall Step Completion Record

STEP ID: W4-PRICE-PATH-S1
TITLE: Bounded TRADES_ONLY reconstruction and W8–W11 readiness funnel
OBJECTIVE: Reconstruct observation-bearing markets without inventing L2; measure 80% observability; expose a fail-closed price-path API; complete W4 as a price-path foundation. Do not start W5.

SCOPE: `crates/research-market` price_path/readiness/price_paths; CLI `--reconstruct-price-paths`; docs

INPUTS: ingest `ingest-20260826T095038Z-2bc3d10b5833`; W4-UNIVERSE-S1 inventory (accepted sub-step)

OUTPUTS:
- `Backtesting Suite/Foundation/W4/price_path_readiness.json`
- `price_path_market_rows.json`, `price_path_coupled.json`, compact JSONL (gitignored)
- `docs/research/backtesting_rebuild/W4/RECONSTRUCTION.md`

CODE CHANGES: provenance on MarketPoint; price-path API; readiness funnel; bounded reconstruct runner

DATA CHANGES: none to Data-Real; no 8,190-path vanity dump

SCHEMA CHANGES: MarketPoint source/retrieval fields; MarketPath observed_start/end; ARTIFACT_VERSION W4.1.0

TESTS: 12 unit + 34 integration on `momento-research-market`; workspace tests + clippy as reported in the closeout

VALIDATION: 238 TRADES_ONLY paths; 137 with 80% print; 0 L2; 0 MATCHED in reconstruct; no W5; no production

KNOWN LIMITATIONS: MATCHED catalog still metadata-only → GameId-linked 80% denominator 0/2377; settlement absent on envelopes
NEXT STEP: STOP. Do not start W5.
STATUS: COMPLETE
