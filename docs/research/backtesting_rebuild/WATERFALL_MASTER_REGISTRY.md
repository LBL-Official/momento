# WATERFALL_MASTER_REGISTRY.md

**Execution authority:** CTO W0–W11  
**Planning reference:** PLAN W0–W26 (not replaced)  
**As of:** 2026-08-27  
**Control agent:** CTO waterfall master (docs only; does not implement the engine)

Status vocabulary (only): `DRAFT | DESIGNED | BLOCKED | READY_FOR_CONTRACT_WORK | READY_FOR_IMPLEMENTATION | IMPLEMENTING | VALIDATING | COMPLETE | REJECTED | SUPERSEDED`

Vague phrases (“mostly done”) are forbidden.

---

## Program invariants

- Strategy proposes → Risk approves → Execution executes. Research does not bypass this.
- FIRST01 is a plugin, not the database.
- `StateTransition` atomic; `GameMarketEpisode` container.
- Data-Real is immutable.
- MLB first. Other sports: adapter traits only.
- Production UNTOUCHED until CTO-W11 **and** explicit CEO live-safety authorization.

---

## Authorization snapshot

| CTO-W | Status | Authorization |
|-------|--------|----------------|
| W0 | **COMPLETE** | Done. Do not rewrite recon. |
| W1 | **COMPLETE** | CEO ACCEPTED / CLOSED 2026-08-26. [W1_CEO_ACCEPTANCE.md](W1_CEO_ACCEPTANCE.md) |
| W2 | **COMPLETE** (engine, observed window) | Canonical MLB event/PBP engine. New raw landing remains DATA-INGEST. |
| DATA-INGEST | **IMPLEMENTING** | CODE READY / BACKFILL_PARTIAL / IMPLEMENTED_NOT_DEPLOYED. [ingest/WATERSTREAM_REPORT.md](ingest/WATERSTREAM_REPORT.md) |
| W3 | **COMPLETE** | CTO ACCEPTED / CLOSED 2026-08-26. [W3_CTO_ACCEPTANCE.md](W3_CTO_ACCEPTANCE.md). Kalshi markets → W4 |
| W4 | **COMPLETE** (price-path foundation) | 238 TRADES_ONLY paths; 8,190 metadata-only excluded. |
| W5 | **IMPLEMENTED** | Event↔market AS-OF join on PBP ∩ MATCHED trades. |
| W6 | **IMPLEMENTED** | Canonical MLB GameState / StateTransition engine. |
| W7 | **IMPLEMENTED** | EventMarketPath join of W5 observations onto W6 states. |
| W8 | **IMPLEMENTED** | FIRST01 observational replay over accepted W7 paths. W9 not started. |
| W9 | **DRAFT** | Not authorized |
| W10 | **DRAFT** | Not authorized |
| W11 | **DRAFT** | Not authorized; production wiring FORBIDDEN by default |

---

## CTO-W0 — Repository / Architecture Reconnaissance

| Field | Value |
|-------|--------|
| **Status** | COMPLETE |
| **Authorization** | Closed |
| **Objective** | Prove what exists; freeze FIRST01; define rewrite boundary and domain model |
| **Inputs** | Repository, Data-Real manifests, production/research crates |
| **Outputs** | Frozen recon package + governance baseline (PLAN-W0-A11) |
| **Dependencies** | None |
| **Blocking** | None remaining |
| **Acceptance** | Recon docs exist and match repo evidence; no engine impl; no production edits |
| **Owning agent** | W0 recon (complete) / control agent for pointers |
| **Exclusive files** | Frozen W0 recon markdown (see FILE_OWNERSHIP) |
| **Parallel** | N/A (done) |
| **Prohibited** | Rewriting recon; starting W1 from this document’s old “do not implement” line without CEO auth (**auth now granted separately**) |
| **Upstream** | — |
| **Downstream** | All |
| **Progress** | A1–A11 complete. Evidence: recon files + `docs/research/completions/W0-A11-S*.md` |
| **Evidence** | [W0/](W0/) · [REPOSITORY_RECONNAISSANCE.md](REPOSITORY_RECONNAISSANCE.md) |

---

## CTO-W1 — Immutable Raw Data + Canonical Data Foundation

| Field | Value |
|-------|--------|
| **Status** | **COMPLETE** (CEO ACCEPTED / CLOSED 2026-08-26) |
| **Authorization** | Closed. Evidence: [W1_ACCEPTANCE_PACKAGE.md](W1_ACCEPTANCE_PACKAGE.md) + [W1_CEO_ACCEPTANCE.md](W1_CEO_ACCEPTANCE.md) + [w1/CLIPPY_REMEDIATION.md](w1/CLIPPY_REMEDIATION.md) |
| **Objective** | Catalogue, provenance-complete, non-destructive lake foundation |
| **Inputs** | Data-Real, demo Data/, `crates/research-data` v1, W0 inventory |
| **Outputs** | `LakeCatalogV1`, coverage_v2, checksum register, envelope v2 spec/types, identity stub, PBP **source matrix** (no download), production fence, local derived artifacts |
| **Dependencies** | W0 COMPLETE |
| **Blocking COMPLETE** | CEO closeout recorded. Independent audit 9/10 + clippy remediation for criterion 7. |
| **Acceptance** | [W1_ACCEPTANCE_CRITERIA.md](W1_ACCEPTANCE_CRITERIA.md) |
| **Owning agent** | W1 implementation agent (closed) |
| **Exclusive files** | `crates/research-data/src/foundation/**`, `tests/w1_foundation.rs` |
| **Allowed parallel** | DATA-INGEST; W2 consume of committed artifacts |
| **Prohibited** | Overwrite Data-Real; Kalshi re-query (PLAN-W1-A8 DEFERRED); L2 fabrication; demo-as-real; production deps |
| **Upstream** | W0 |
| **Downstream** | DATA-INGEST, W2–W11 |
| **Progress** | Job `w1-d7e5d472e86268dc`. Clippy remediating. CEO ACCEPTED/CLOSED. |
| **Evidence** | [w1/](w1/) · Foundation artifacts · [W1_CEO_ACCEPTANCE.md](W1_CEO_ACCEPTANCE.md) |
| **Active step** | None (closed). Do not execute PLAN-W1-A8. Do not start W3 from W1 close. |
| **Google later** | coverage reports, catalog exports (aggregates). Not raw gzip |

### W1 meaningful steps (control plane — do not invent padding)

Use **PLAN-S** for CEO checkpoints. W1-LEDGER is implementation-internal.

| PLAN-S | Intent | Observed in code? |
|--------|--------|-------------------|
| PLAN-W1-A1-S1 | Specify lake_catalog_v1 schema + fixtures | Partial (types exist; dedicated schema doc/fixture still W0-level) |
| PLAN-W1-A1-S2 | Generator over Data-Real | `run_w1_foundation` |
| PLAN-W1-A1-S3 | Demo catalog DEMO flag | source inventory mentions demo |
| PLAN-W1-A1-S4 | Reproducible catalog | test `w1_job_is_idempotent_on_fixture_lake` |
| PLAN-W1-A2-* | coverage_v2 | `coverage.rs` |
| PLAN-W1-A3-* | checksum / non-overwrite | `integrity.rs`, `guard.rs` |
| PLAN-W1-A4-* | envelope v2 | `envelope_v2.rs` |
| PLAN-W1-A5-* | identity stub | `identity_stub.rs` |
| PLAN-W1-A6-* | PBP source matrix, no download | recovery queries in `availability.rs` only |
| PLAN-W1-A7-* | production fence / demo≠real | toml string test; demo notes |
| PLAN-W1-A8-* | Kalshi re-query | **DEFERRED — do not execute** (ledger A8 is **reporting**, FLAG-008) |

---

## CTO-W2 — MLB Event / PBP Reconstruction

| Field | Value |
|-------|--------|
| **Status** | READY_FOR_CONTRACT_WORK |
| **Authorization** | Parallel **contracts, interfaces, synthetic fixtures, docs**. Not real PBP ingest |
| **Objective** | EVENT domain: identity graph + `GameState` + PBP transitions when source exists; otherwise explicit UNAVAILABLE |
| **PLAN alias** | PLAN-W2 + PLAN-W4 + PLAN-W5 |
| **Inputs** | W1 catalog/handoff types; authorized PBP **when** approved |
| **Outputs** | `Game`, `GameState`, `PBPEvent` schemas; MLB adapters; UNMAPPED bulk if no official ids; FIXTURE streams |
| **Dependencies** | W1 types readable. Historical reconstruction depends on PBP **not** present |
| **Blocking reconstruction** | PBP UNAVAILABLE; license/ToS not approved |
| **Acceptance (contract phase)** | No invented pk; fixtures labeled; PARTITION_COMPLETE_V1 not treated as event-complete; no eventual winner on replay view |
| **Owning agent** | W2 implementation agent |
| **Exclusive files** | Reserved `crates/research-event/**`; `W2/` docs. Not `foundation/**` |
| **Allowed parallel** | With W1 impl under PARALLEL_RULES |
| **Prohibited** | Editing W1 foundation; Data-Real writes; scraping PBP; claiming 2025/L2; defining `SynchronizedState` (W4); defining canonical `GameMarketEpisode` (W5) |
| **Upstream** | W1 |
| **Downstream** | W4, W5, W8 |
| **Progress** | No W2 crate. Handoff types exist in W1 `w2_contract.rs` (W1-owned) |
| **Evidence** | [W2/](W2/) |
| **Google later** | event coverage, UNMAPPED report, PBP integrity (when real) |

### W2 steps (meaningful)

| ID | Intent | State |
|----|--------|-------|
| CTO-W2-A1-S1 | `GameState` / `PBPEvent` schema + FIXTURE | authorized |
| CTO-W2-A1-S2 | Adapter traits (`SportAdapter`, `GameStateAdapter`, `PBPAdapter`) | authorized |
| CTO-W2-A2-S1 | Identity graph spec (tickers as aliases; pk optional) | authorized |
| CTO-W2-A2-S2 | Map official pks **or** bulk UNMATCHED | BLOCKED without source |
| CTO-W2-A3-S1 | PBP source/license gate | BLOCKED on CEO+license |
| CTO-W2-A4-S1 | Reconstruct GameState from authorized PBP | BLOCKED on data |
| CTO-W2-A5-S1 | Event-state UNAVAILABLE path for Kalshi-only games | authorized (design/impl of **labeling**, not fake state) |

---

## CTO-W3 — MLB Game / PBP Reconstruction (2026-08-26 grant)

| Field | Value |
|-------|--------|
| **Status** | COMPLETE (CTO ACCEPTED / CLOSED 2026-08-26) |
| **Authorization** | Granted 2026-08-26. Kalshi **market** reconstruction is **W4** under this grant. |
| **Objective** | Deterministic game/PBP timeline from committed checksum-verified artifacts |
| **Inputs** | W2 engine; DATA-INGEST handoff or verified W2 collect manifest |
| **Outputs** | `Backtesting Suite/Foundation/W3/`; crate `momento-research-reconstruction` |
| **Prohibited** | Data-Real writes; downloaders; MarketState; theta values; production |
| **Evidence** | [W3/](W3/) · [W3_COMPLETION_REPORT.md](W3_COMPLETION_REPORT.md) · [W3_CTO_ACCEPTANCE.md](W3_CTO_ACCEPTANCE.md) |

Kalshi `MarketState` work previously stubbed here is **W4** under the 2026-08-26 grant (bounded window VALIDATING).

---

## CTO-W4 — Kalshi market reconstruction (2026-08-26 grant)

| Field | Value |
|-------|--------|
| **Status** | COMPLETE (price-path foundation) |
| **Authorization** | Granted. Bounded window 2026-06-18 first. |
| **PLAN alias** | PLAN-W6 + PLAN-W7 |
| **Objective** | Per-contract `MarketPath` from committed artifacts; honest completeness |
| **Inputs** | Ingest Kalshi envelopes + W1 lake COMPLETE (read-only) + identity (read-only) |
| **Outputs** | `Backtesting Suite/Foundation/W4/`; crate `momento-research-market` |
| **Prohibited** | `SynchronizedState`; L2/mid invention; Data-Real writes; 8k-ticker vanity run |
| **Files** | [W4/](W4/) |

Stale “W4 = sync” text is **superseded**. Sync is W5.

---

## CTO-W5 — Event ↔ Market Synchronization

| Field | Value |
|-------|--------|
| **Status** | DESIGNED |
| **Authorization** | Not to implement |
| **PLAN alias** | PLAN-W3 (**inversion**) |
| **Objective** | Join with confidence; never drop a domain because join failed |
| **Inputs** | W3 event stream (or UNAVAILABLE) + **W4 market path** (or UNAVAILABLE) |
| **Outputs** | Sync meta + quality report; path-aware `S(t)` **specified** not coded |
| **Dependencies** | W3 + W4 |
| **Blocking** | W4 MarketPath; EXACT without a clock contract; historical L2 still UNAVAILABLE |
| **Acceptance** | ADR-0003 confidence enum; unmatched retained |
| **Owner** | W5 |
| **Files** | [W5/S_OF_T_FIELD_CONTRACT.md](W5/S_OF_T_FIELD_CONTRACT.md) |
| **Prohibited** | Inventing PBP times from trades; candle/PIT as L2; merging W6/W7 impl into W5 |
| **Upstream** | W3, W4 |
| **Downstream** | later `StateTransition` / `GameMarketEpisode` |
| **Google later** | sync_quality.csv |

---

## Downstream of W5 — Canonical State / StateTransition (not grant-W5)

Grant **W5 is sync**. This row is the old “W5 StateTransition” objective (PLAN-W8/W11/W12). It is **not** authorized and must not be coded as W5.

| Field | Value |
|-------|--------|
| **Status** | READY_FOR_CONTRACT_WORK |
| **Authorization** | Schemas/fixtures only; **after** W4 MarketPath + W5 sync |
| **PLAN alias** | PLAN-W8 + PLAN-W11 + PLAN-W12 |
| **Objective** | Atomic `StateTransition` inside `GameMarketEpisode`; full path not 80% snapshot |
| **Inputs** | W5-synchronized (or one-sided UNAVAILABLE) streams |
| **Prohibited** | Skipping W4; inventing L2; FIRST01 retune |
| **See** | [W5/S_OF_T_FIELD_CONTRACT.md](W5/S_OF_T_FIELD_CONTRACT.md) |

---

## CTO-W6 — Canonical MLB State Engine

| Field | Value |
|-------|--------|
| **Status** | **IMPLEMENTED** |
| **Authorization** | Implementation grant 2026-08-26 |
| **Objective** | Canonical replayable `GameState` / `StateTransition` from W3 PBP |
| **Inputs** | StatsAPI landing envelopes; W2 GameId; W3 replay |
| **Outputs** | Foundation/W6 sqlite + manifests; `state_at_or_before(T)` |
| **Owner** | W6 |
| **Prohibited** | Attaching prices to GameState; FIRST01 replay; invented L2 |
| **See** | [W6_STATE_ENGINE.md](W6_STATE_ENGINE.md) |

PLAN-W13 FIRST01 replay is **not** this waterfall and is not started.

---

## CTO-W7 — Canonical Event / Market Path

| Field | Value |
|-------|--------|
| **Status** | **IMPLEMENTED** |
| **Authorization** | Implementation grant 2026-08-26 |
| **PLAN alias** | Grant remaps away from PLAN-W15 outcome labels. This W7 is EventMarketPath. |
| **Objective** | Point-in-time EVENT ↔ MARKET path: W5 TRADE observations + W6 state references + causal descriptors |
| **Inputs** | Foundation/W5 `sync.sqlite`; Foundation/W6 `state.sqlite` |
| **Outputs** | Foundation/W7 `path.sqlite` + coverage/validation/examples |
| **Owner** | W7 (`momento-research-path`) |
| **Prohibited** | FIRST01 replay (now W8); outcome labels; invented L2; inferred bid/ask/mid/open/close; lookahead |
| **See** | [W7_EVENT_MARKET_PATH.md](W7_EVENT_MARKET_PATH.md) |

PLAN-W15 80% transition / outcome classification is **not** this waterfall and is not started.

---

## CTO-W8 — FIRST01 observational replay

| Field | Value |
|-------|--------|
| **Status** | **IMPLEMENTED** |
| **Authorization** | Implementation grant 2026-08-27 |
| **PLAN alias** | Grant remaps away from PLAN-W9 Greeks. This W8 is FIRST01 replay. |
| **Objective** | Deterministic observational FIRST01 replay over accepted W7 EventMarketPath |
| **Inputs** | Foundation/W7 `path.sqlite` |
| **Outputs** | Foundation/W8 `replay.sqlite` + coverage/validation/examples |
| **Owner** | W8 (`momento-research-replay`) |
| **Prohibited** | Fills; P&L; outcome labels; invented bid/ask; live `MlbStrategy`; W9 |
| **See** | [W8_FIRST01_REPLAY.md](W8_FIRST01_REPLAY.md) |

PLAN-W9 Greeks / grant-W9 outcome classification are **not** this waterfall and are not started.

---

## CTO-W9 — Orderbook / Market Microstructure Research

| Field | Value |
|-------|--------|
| **Status** | DRAFT |
| **Authorization** | None |
| **Objective** | Research on OBSERVED book only; document UNAVAILABLE historically |
| **Dependencies** | W3 observability; historical L2 UNAVAILABLE |
| **Prohibited** | Interpolating L2 from candles/trades |
| **Google later** | orderbook analysis **only where observability allows** |

---

## CTO-W10 — ML / XGB / Monte Carlo / Hyperparameter Research

| Field | Value |
|-------|--------|
| **Status** | DRAFT |
| **Authorization** | None |
| **PLAN alias** | PLAN-W17 + PLAN-W18 + PLAN-W19 |
| **Objective** | Models after trustworthy dataset; FIRST01 v1 remains control |
| **Prohibited** | Auto-deploy; skip validation; leakage |
| **Google later** | model_results, validation_report, experiment index |

---

## CTO-W11 — Production Research-to-Execution Integration

| Field | Value |
|-------|--------|
| **Status** | DRAFT |
| **Authorization** | None. Production wiring **FORBIDDEN by default** |
| **PLAN alias** | PLAN-W20 … PLAN-W26 |
| **Objective** | Drive archive, Sheets index, artifact packs, dashboard, model registry, optional live bridge, live→research capture |
| **Prohibited** | Research agent modifying live/risk/execution/config |
| **Google** | This waterfall **implements** Drive/Sheets; earlier W only define publish **payloads** locally |

---

## Cross-cutting prohibited work (all agents)

- Production strategy/risk/execution/live/deploy
- Data-Real overwrite/repair/delete
- Fabricating PBP, L2, 2025 games, mids, market-open from first candle
- Upgrading observability
- Using unprefixed W# in handoffs
- Marking COMPLETE without evidence
