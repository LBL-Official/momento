# W2 Completion Report

**Waterfall:** 2 — MLB Event / PBP Reconstruction  
**Date:** 2026-08-26  
**Crate:** `momento-research-event` (`crates/research-event`)  
**Artifact version:** `W2.2.0`

W2-E GameState reconstruction is COMPLETE for collected StatsAPI games
(2026-06-18..30, 174 Final). W2-B official identity + unique Kalshi crosswalk
is COMPLETE (168 MAPPED, 4 UNMATCHED, 2 AMBIGUOUS). W2-F event-time inputs are
populated from that PBP. Event Theta **value** remains UNAVAILABLE
(ADR-0010 / Waterfall 9). 2025 PBP remains MISSING_HISTORICAL_SOURCE.

W3 was not started. Data-Real was not written.

---

## Historical PBP collection (CEO-authorized free API)

**Source:** public MLB StatsAPI (`statsapi.mlb.com` schedule + `feed/live`)  
**Window:** 2026-06-18 .. 2026-06-30 (Kalshi COMPLETE market days)  
**Store:** `Backtesting Suite/Foundation/W2/raw/statsapi/` (gitignored; not Data-Real)  
**Manifest:** `Backtesting Suite/Foundation/W2/statsapi_collect_manifest.json`

| Metric | Count |
|--------|-------|
| Schedule games | 178 (174 Final, 4 Postponed skipped) |
| Envelopes collected | 174 |
| Ingest OK | 174 |
| GameState reconstruction VALID | 174 |
| Fail-closed reconstruction failures | 0 |
| Kalshi MAPPED (unique date+abbrev suffix) | 168 |
| Kalshi UNMATCHED (no ticker that day) | 4 |
| Kalshi AMBIGUOUS (CHC–NYM doubleheader 2026-06-24) | 2 |

`gamePk` is OBSERVED from StatsAPI. It is never invented from a ticker.
AMBIGUOUS doubleheaders are left unmapped rather than guessed.

---

## Event Theta (W2-F)

ADR-0010: no closed-form theta in W2.

Every reconstructed game has `EventThetaInputs` (54-out remaining opportunity,
information-rate proxy = opportunity delta). `theta_value` is UNAVAILABLE;
status `ESTIMATOR_DEFERRED_W9`. All 174 rows: `theta_value_unavailable=true`.

---


## What this waterfall is

W2 is the EVENT/PBP engine:

```text
raw PBP envelope
  → canonical MLB events
  → fail-closed GameState transitions (MlbPbpTransition)
  → event-time foundation (no Event Theta)
  → deterministic replay
  → sequences
  → honest coverage reporting
```

It is **not** Kalshi market reconstruction, **not** event↔market sync, **not** FIRST01 replay, and **not** a claim that historical PBP exists.

---

## W1 contract resolution (critical)

W1 now **exports** `foundation::w2_contract` (`RawArtifactRef`, `RawMarketIdentity`, `W2_HANDOFF_NOTES`).

W2 **does not fork** those structs. `crates/research-event/src/w1_bridge.rs` re-exports the W1 types and contains only:

- constructors that always set `starting_price_class = StartingPriceUnverified`
- explicit `IdentityStubV1` ↔ `RawMarketIdentity` adapters (lossy fields documented)
- local `MlbTimestampKind` because W1 `SourceTimestampKind` has no PBP variant

Field comparison (authoritative W1 vs former W2 mirror):

| Type | W1 (authoritative) | Former W2 mirror | Resolution |
|------|--------------------|------------------|------------|
| `RawArtifactRef.sport` | `String` (lake folder, e.g. `"MLB"`) | `SportCode` enum | Consume W1. No fork. |
| `RawMarketIdentity.starting_price_class` | required `StartingPriceClass` | missing | Consume W1. W2 sets `StartingPriceUnverified` only. |
| `IdentityStubV1.open_time` | optional venue metadata | n/a | **Dropped** in stub→identity adapter. Never becomes `MarketOpenPrice`. |
| `IdentityStubV1.match_status` | `UNMAPPED` only | n/a | Not a `RawMarketIdentity` field. W2 local `MlbMatchStatus` is the richer graph. |
| `SourceTimestampKind` | TradeCreated, CandleEnd, VenueMetadata, IngestOnly, Unknown | n/a | **No PBP variant.** W2 `MlbTimestampKind::PbpOfficial` maps to W1 `Unknown`. Not a W1 patch. |

W1 foundation files were **not** modified.

No W1 contract change is required to close W2. Optional later W1 schema version: `SourceTimestampKind::PbpOfficial` — deferred, not blocking.

---

## W5 naming (no stolen ownership)

W2 emits **`MlbPbpTransition`** (PBP-triggered before/after `MlbGameState`).

W5 retains canonical **`StateTransition`** and **`GameMarketEpisode`**. W2 does not define those types.

SQL: `mlb_pbp_transitions` (not a W5 `StateTransition` table).

---

## Acceptance gate

| ID | Criterion | Result | Evidence | Test | Implementation | Remaining |
|----|-----------|--------|----------|------|----------------|-----------|
| W2-A | Source contract | **PASS** | `source.rs`, `source_contract.json` | `source_contract_no_auto_sub`, `local_pbp_discovery_empty` | `crates/research-event/src/source.rs` | Hierarchy forbids auto-substitution. Inventory found zero historical PBP files. |
| W2-B | Identity mapping | **PASS** (engine) / **BLOCKED** (real official pk map) | `identity.rs` | `identity_no_invented_map`, `kalshi_unmapped_id_is_never_rewritten_to_fake_mlb_pk` | `crates/research-event/src/identity.rs` | `W2-A2-S7` BLOCKED: no licensed official source. `kalshi:` prefix preserved. No invented `mlb_game_pk`. |
| W2-C | Ingest boundary | **PASS** | `ingest.rs` | `statsapi_parser`, `malformed_pbp`, `ingest_duplicate_source_event_is_recorded_not_replayed_twice` | `crates/research-event/src/ingest.rs` | Parser proven on `SYNTHETIC_TEST_FIXTURE`. Real historical ingest impossible until files exist. |
| W2-D | Canonical event model | **PASS** | `event.rs` | `serialize_round_trip`, `fixtures_are_labeled_synthetic` | `crates/research-event/src/event.rs` | Fixtures labeled. No magic sentinels. |
| W2-E | Fail-closed state machine | **PASS** | `state.rs` | `invalid_transitions_fail_loud`, `amendment_allows_outs_decrease`, `walkoff_apply` | `crates/research-event/src/state.rs` | Synthetic only. Historical GameState from real PBP: **BLOCKED** on data (CTO-W2-A4-S1). |
| W2-F | Event-time foundation | **PASS** | `event_time.rs` | `event_time_no_theta_formula`, `in_progress_state_does_not_know_actual_remaining_outs_or_settlement` | `crates/research-event/src/event_time.rs` | Event Theta `NOT_COMPUTED`. Actual remaining outs UNAVAILABLE while in progress. |
| W2-G | Sequence views | **PASS** | `sequence.rs` | `sequence_views` | `crates/research-event/src/sequence.rs` | None. |
| W2-H | Deterministic replay / validation | **PASS** | `replay.rs` | `determinism`, `no_future_leakage`, `state_restore`, `validation_summary` | `crates/research-event/src/replay.rs` | Lookahead boundary enforced on `MlbGameState`. |
| W2-I | Honest coverage reporting | **PASS** | `coverage.rs`, `w2_coverage.csv` | `coverage_does_not_claim_2025_pbp` | `crates/research-event/src/coverage.rs` | 2025 = `MISSING_HISTORICAL_SOURCE`. 13 Kalshi COMPLETE days are **market** coverage, not PBP. |
| W2-J | Documentation + ledger | **PASS** | this report, `ledger.json` | `runner_writes_outside_lake` | `docs/research/backtesting_rebuild/W2*.md`, `ledger.rs` | Sheets cell API `GOOGLE_PUBLISH_PENDING` (not faked). Local artifacts written. |

**BLOCKED (external data/license only):**

- Official `mlb_game_pk` mapping from a real source (`W2-A2-S7` / CTO-W2-A2-S2)
- Licensed historical PBP acquisition (CTO-W2-A3-S1)
- Reconstructing GameState from authorized **historical** PBP files (CTO-W2-A4-S1) — engine exists; files do not

BLOCKED was not converted into PASS.

---

## Tests recorded

```text
cargo fmt -p momento-research-event
cargo check -p momento-research-event
cargo test -p momento-research-event
cargo clippy -p momento-research-event --all-targets --no-deps -- -D warnings
```

Result: **fmt clean; check ok; 13 lib + 31 integration tests passed; clippy `-D warnings` clean.**

Covered: deterministic replay, no lookahead, unmapped identity, missing PBP, duplicate/amendment/invalid transitions, timestamp `PbpOfficial` ≠ `TradeCreated`, fixture provenance, no fabricated historical state, W1 type consumption (no struct fork).

---

## Data honesty (frozen)

| Asset | Status |
|-------|--------|
| Official MLB PBP | `MISSING_HISTORICAL_SOURCE` |
| Historical L2 | `UNAVAILABLE` |
| Proven market-open price | `UNAVAILABLE` / W1 `STARTING_PRICE_UNVERIFIED` |
| Kalshi-only games | `UNMAPPED`, `kalshi:` canonical prefix, `mlb_game_pk = None` |
| Event Theta | `NOT_COMPUTED` |
| Actual outs remaining (in-progress) | `UNAVAILABLE` |
| Event↔market sync | not in W2 |
| Kalshi Data-Real 2026-06-18..30 (13 COMPLETE PT days) | **MARKET** coverage only, not EVENT/PBP |
| 2025 Kalshi | empty / missing |
| Synthetic fixtures | `SYNTHETIC_TEST_FIXTURE` — not history |

---

## What W3 may assume (when authorized)

- Frozen W2 types: `CanonicalMlbEvent`, `MlbGameState`, `MlbPbpTransition`, `EventTimeState`, `PbpSequence`, `CanonicalGameId`, `MlbMatchStatus`
- W1 `RawArtifactRef` / `RawMarketIdentity` consumed, not forked
- Identity-only market aliases (`MlbMarketReference`) with `starting_price_class = StartingPriceUnverified` and `reconstruction_status = UNAVAILABLE`
- Coverage vocabulary that labels missing PBP honestly

## What W3 may not assume

- That historical PBP exists
- That `PARTITION_COMPLETE_V1` means event-complete
- That first local candle is market open
- That `kalshi:` ids are official MLB pks
- That W2 reconstructed Team A/B price paths (it did not)
- That W2 defined `StateTransition` / `GameMarketEpisode` / `SynchronizedState`

---

## Google reporting

- **Local:** `Backtesting Suite/Foundation/W2/` (ledger, coverage CSV, sheets index CSV, dictionary)
- **Sheets MCP:** `GOOGLE_PUBLISH_PENDING` (`user-google-sheets` needsAuth). Not faked.
- **Drive:** prior archive may exist from an earlier run; this closeout’s source of truth is the local tree until republish is authorized.

---

## Production impact

**None.** No strategy, risk, execution, live config, FIRST01, or Data-Real writes.

---

## Stop

W2 closeout is complete for the authorized EVENT/PBP engine scope.

Do not start W3 without CTO authorization.
