# CTO-W2 SPEC

**Name:** MLB Event / PBP Reconstruction  
**Status:** EVENT/PBP ENGINE COMPLETE; historical PBP `MISSING_HISTORICAL_SOURCE`

## Objective

EVENT domain: identity graph, `MlbGameState`, canonical PBP events, MLB adapters. Label UNAVAILABLE / `MISSING_HISTORICAL_SOURCE` when PBP is missing. Do not invent plays.

Pipeline: raw envelope → canonical events → fail-closed transitions → event-time foundation → deterministic replay → sequences → honest coverage.

## Inputs

W1 exported types (`RawArtifactRef`, `RawMarketIdentity`, `IdentityStubV1`, `ObservabilityKind`, `StartingPriceClass`) — read-only. Official/licensed PBP only when approved (none present).

## Outputs

- Crate `momento-research-event`
- Synthetic FIXTURE streams labeled `SYNTHETIC_TEST_FIXTURE`
- UNMAPPED `kalshi:` identity rows
- Local artifacts under `Backtesting Suite/Foundation/W2/`
- Not a fake PBP lake

## Google Drive / Sheets

Local artifacts required. Sheets cell API: `GOOGLE_PUBLISH_PENDING` until MCP auth. Do not fake publish.

## MLB-first

Implement MLB only. Adapter traits may be named for future sports; NBA/NHL/NCAAB/NFL are stubs.
