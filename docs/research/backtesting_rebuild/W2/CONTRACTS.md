# CTO-W2 CONTRACTS

Owned by W2:

- `CanonicalMlbEvent` (PBPEvent)
- `MlbGameState`
- `MlbPbpTransition` (not W5 `StateTransition`)
- `EventTimeState` (no theta formula)
- `PbpSequence`
- `CanonicalGameId` / `GameIdentity` / `MlbMatchStatus`
- `MlbMarketReference` (identity aliases only; no reconstructed prices)
- `MlbTimestampKind` (PBP clock; maps to W1 `Unknown`)

Consumed from W1 (not forked):

- `RawArtifactRef` (`sport`: lake folder `String`)
- `RawMarketIdentity` (includes `starting_price_class`)
- `IdentityStubV1`
- `ObservabilityKind`, `StartingPriceClass`, `ProvenanceRecord`, `LakeWriteGuard`

Adapters: `EventStateAdapter`, `MlbEventAdapter`. NBA/NCAAB/NHL stubs only.

`PARTITION_COMPLETE_V1` is not PBP-complete, lifetime-complete, or L2-complete.

Canonical registry: [../WATERFALL_CONTRACT_REGISTRY.md](../WATERFALL_CONTRACT_REGISTRY.md).
