# CTO-W4 CONTRACTS

Owned by W4 (market reconstruction, not sync):

- `MarketCompleteness` (W4 enum; includes `UNOBSERVED`)
- `MarketObservationKind`
- `MarketPoint`
- `MarketPath`
- `CoupledMarketEpisode`
- `LifetimeCoverage`
- `W4CoverageReport` / reconstruction run / anomalies / blocker list

Consumed (not forked):

- W1: `ObservabilityKind`, `StartingPriceClass`, `LakeWriteGuard`, checksum helper, Data-Real COMPLETE manifests + `events.jsonl.gz` (read-only)
- DATA-INGEST: `W1CommitHandoff`, `GameMarketPair`, `IdentityMapping`, discovery envelopes
- W2/W3: identity only (pairs / mapping). W4 does not parse PBP.

Forbidden in this crate:

- `struct SynchronizedState`
- theta / Greeks
- Kalshi order submit
- Data-Real writes
- suffix-match identity
- official Kalshi mid
