STEP ID: PLAN-W1-A2-S1
TITLE: Define coverage_v2 vocabulary
OBJECTIVE: Define coverage_v2 vocabulary

SCOPE: CTO-W1 only. Do not redefine v1 COMPLETE. No production/strategy/risk/execution edits. No Data-Real overwrite. No PLAN-W1-A8 re-query. No W2 files.

INPUTS: Data-Real (read-only), demo Data/, W0 recon, research-data v1.

OUTPUTS: coverage.rs; COVERAGE.md; LIFETIME_UNVERIFIED as lifetime_path dimension

CODE CHANGES: crates/research-data/src/foundation/** ; tests/w1_foundation.rs ; collector w1-foundation command only.

DATA CHANGES: Derived Backtesting Suite/Foundation/W1 only. Data-Real hashes UNCHANGED.

SCHEMA CHANGES: Additive LakeCatalogV1 / RawEnvelopeV2 / IdentityStubV1 / coverage_v2. v1 CompletenessStatus unmodified.

TESTS: cargo test complete_v1_is_not_lifetime_complete empty_probe_is_not_fabricated_2025

VALIDATION: Independent of W1-LEDGER auto-complete. Real run w1-d7e5d472e86268dc; cargo test -p momento-research-data --offline (31 tests: 4 lib envelope + 13 infrastructure + 14 w1_foundation).

ARTIFACTS: docs/research/backtesting_rebuild/W1/ ; Foundation/W1/ ; this record.

GOOGLE DRIVE OUTPUT: Folder created 1K3EBXFRPqteRLccRZH99Tv4Ql1CJwV0n. Canonical truth remains local. Full Drive/Sheets engine is CTO-W11.

GOOGLE SHEETS OUTPUT: Local sheets_w1_index.csv. Sheets MCP needsAuth.

PERFORMANCE: Real catalog job ~109s. Tests <3s.

KNOWN LIMITATIONS: No historical L2; no PBP; no proven market-open prices; 2025 MLB empty probes; candle batch gzip lines do not invent a single join timestamp.

LOOKAHEAD / DATA LEAKAGE REVIEW: Catalog does not invent 2025 games. Starting price not inferred from first candle.

REPRODUCIBILITY: lake_content_digest d7e5d472e86268dc17a7f8d4d62c3c22ddb6fe9089e9b4097ff9b3c5eafd8f95; canonical_catalog_body.json stable.

DEPENDENCIES CREATED: W1 catalog + coverage + envelope v2 + identity stub for CTO-W2 to *read*.

DEPENDENCIES RESOLVED: PLAN-W1-A1 through this step as listed.

NEXT STEP: PLAN-W1-A2-S2

FINAL STATUS: COMPLETE
