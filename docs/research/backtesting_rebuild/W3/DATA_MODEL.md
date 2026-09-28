# W3 data model

Reuse W2 types. W3 adds run/coverage wrappers.

| Concept | Type | Owner |
|---------|------|--------|
| MLBGame | `OfficialMlbGameRef` + lifecycle | W2 + W3 lifecycle |
| PBPEvent | `CanonicalMlbEvent` | W2 |
| GameState | `MlbGameState` | W2 |
| PBPSequence | `PbpSequence` | W2 |
| GameIdentity | `GameIdentity` / `MlbMatchStatus` | W2 |
| GameCoverage | `W3CoverageReport` | W3 |
| ReconstructionRun | `W3RunResult` | W3 |
| ReconstructionAnomaly | `ReconstructionAnomaly` | W3 |
| ProvenanceReference | `EventProvenance` + artifact SHA-256 | W1/W2 |

SQL sketch: `crates/research-reconstruction/src/schema_sql.rs`
