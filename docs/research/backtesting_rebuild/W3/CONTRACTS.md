# CTO-W3 CONTRACTS

Owned by W3 (layer, not a W2 fork):

- `MlbGameLifecycle` (SCHEDULED/POSTPONED/CANCELLED/SUSPENDED/FINAL/LIVE/UNKNOWN)
- `CommittedSet` / reconstruction run / window coverage / anomalies
- W3 ledger `CTO-W3-A#-S#` (evidence-only, not auto-complete)

Consumed (not forked):

- W2: `CanonicalMlbEvent`, `MlbGameState`, `PbpSequence`, `OfficialMlbGameRef`, `ingest_path`, `replay`
- W1: `LakeWriteGuard`, checksum helper, `ProvenanceRecord` on events via W2 provenance
- DATA-INGEST: `W1CommitHandoff` (COMMITTED + SHA-256)

Forbidden: `MarketState`, `SynchronizedState`, `GameMarketEpisode`, theta values.
