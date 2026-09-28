# Cross-waterfall issues (W1)

W1 does not independently redefine W2 domain contracts.

| ID | Issue | Proposed resolution | Status |
|----|--------|---------------------|--------|
| XW-1 | Sport identity: W1 lake dirs are `MLB`/`WNBA` strings. W2 may introduce an official sport/game PK model. | Keep W1 `RawArtifactRef.sport` as folder labels. Do not merge enums without CTO. | **REQUIRES_CTO_DECISION** only if W2 needs a shared `Sport` type in `momento-core` now. W1 proceeds with strings. |
| XW-2 | `GameId` today is SHA-256(Kalshi `event_ticker`). W2 MLB pk mapping. | W1 `IdentityStubV1.mlb_game_pk = null`. Mapping is W2/identity waterfall. | W1 complete; mapping out of scope |
| XW-3 | Envelope v2 lives in Foundation, not replacing v1 gzip. | W2 reads v1 raw via catalog; v2 sample is illustrative. | Resolved locally |
| XW-4 | Historical L2 | `L2_HISTORICAL_UNAVAILABLE`. Prospective WS is a **new** artifact later. | Resolved locally |
| XW-5 | PLAN-W1-A\* vs W1-LEDGER-A\* ID collision (FLAG-001) | Namespaced ledger IDs; PLAN completions separate; alias table `REGISTRY_ID_MAPPING.md`. Do not copy ledger COMPLETE into PLAN CSV. | Resolved locally |
| XW-6 | FLAG-003 CandleEnd empty timestamp | `end_period_ts` copied; CandleEnd never lacks `source_timestamp`. Batch gzip line uses **last** period-end as envelope clock; per-bar clocks stay in payload. | Resolved locally |
| FLAG-004 | Envelope `observability=OBSERVED` for PIT payload presence | Consumers must use `source_timestamp_kind=IngestOnly` for game-time L2. Not a W1 COMPLETE blocker per control REVIEW. | Open REVIEW; not BLOCK |

No W2 implementation files were modified.
