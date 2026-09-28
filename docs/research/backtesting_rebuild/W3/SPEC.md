# CTO-W3 SPEC

**Name:** MLB Game / PBP Reconstruction  
**Status:** IMPLEMENTING (not ACCEPTED)

## Objective

Turn **committed, checksum-verified** MLB PBP into a deterministic, provenance-preserving, replayable game timeline. Fail closed. Never invent UNAVAILABLE fields.

## Inputs

- DATA-INGEST `W1CommitHandoff` (preferred going forward)
- Verified W2 collect manifest + envelopes (legacy committed set for 2026-06-18..30)
- W2 parser + state machine (`ingest_path`, `replay`)

## Outputs

Foundation/W3: reconstruction summary, coverage windows, skipped lifecycle games, anomalies, evidence ledger, schema sketch.

## Not this waterfall

Kalshi MarketState (W4), event↔market sync (W5), canonical cross-domain state (W6), theta/Greeks (W10), FIRST01, production.
