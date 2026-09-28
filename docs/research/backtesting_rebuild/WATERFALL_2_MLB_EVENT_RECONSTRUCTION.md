# Waterfall 2 — MLB Event / PBP Reconstruction

W2 COMPLETE AS AN EVENT/PBP ENGINE; HISTORICAL MLB PBP REMAINS
MISSING_HISTORICAL_SOURCE.

**Does not start W3.**  
**Does not modify W1 implementation files.**

Closeout: [W2_COMPLETION_REPORT.md](W2_COMPLETION_REPORT.md).

## What W2 is

W2 builds the **EVENT domain** so later waterfalls can answer:

> What was the exact baseball game state at historical time t?

Pipeline owned here:

```text
MLB RAW PBP (immutable)
    → Canonical Events
    → Game State Machine
    → Event State Timeline
    → Event Time / Θ foundation (inputs only)
    → PBP Sequence History
```

W3 (market reconstruction) and W4 (synchronization) are **not** implemented.

## What was built

Crate: `momento-research-event` (`crates/research-event`).

| Section | Implementation |
|---------|----------------|
| W2-A Source contract | `src/source.rs` |
| W2-B Identity | `src/identity.rs` |
| W2-C Ingest | `src/ingest.rs` |
| W2-D Canonical events | `src/event.rs` |
| W2-E State machine | `src/state.rs` |
| W2-F Event time | `src/event_time.rs` |
| W2-G Sequence | `src/sequence.rs` |
| W2-H Replay/validation | `src/replay.rs` |
| W2-I Coverage | `src/coverage.rs` |
| W2-J Ledger/docs/runner | `src/ledger.rs`, `src/runner.rs`, this folder |

## Honesty

- **No local historical MLB PBP exists.** Coverage rows are `MISSING_HISTORICAL_SOURCE`.
- **2025 is not reconstructed.** Empty Kalshi probes are not 2025 baseball.
- Test games are labeled `SYNTHETIC_TEST_FIXTURE`.
- Kalshi `KXMLBGAME` tickers are **aliases** (`IdentityStubV1` UNMAPPED). Team abbreviations in tickers are **not** split into official MLB teams.
- Event Theta is **not computed**. Foundation fields only.

## W1

Consumed (exported): `ObservabilityKind`, `IdentityStubV1`, `ProvenanceRecord`, `DailyManifest`, `LakeWriteGuard`.

See `W2_CTO_DECISIONS.md` for unpublished W1 `w2_contract.rs` and timestamp-kind gap.

## Next

W3 prerequisites are listed in `W2_COMPLETION_REPORT.md`. Do not start W3 in this waterfall.
