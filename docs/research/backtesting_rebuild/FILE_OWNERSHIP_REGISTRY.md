# FILE_OWNERSHIP_REGISTRY.md

**Rule:** every implementation file has exactly one owner.  
**Inspected:** 2026-08-26 workspace.  
**If conflict:** do not guess — mark BLOCKED (see [CTO_REVIEW_FLAGS.md](CTO_REVIEW_FLAGS.md)).

Ownership is **execution ownership** (who may edit). LEGACY files may be *read* by later waterfalls.

---

## UNTOUCHED — no research agent

| Path | Reason |
|------|--------|
| `strategies/mlb/**` | Live FIRST01 |
| `strategies/wnba/**` | Live |
| `crates/risk/**` | Risk Decision Engine |
| `crates/execution/**` | Order lifecycle |
| `crates/positions/**` | Fill-authoritative tracker |
| `crates/pnl/**` | Realized P&L |
| `apps/trading-engine/**` | Live/paper host |
| `config/live.toml`, `config/paper.toml` | Live gates |
| `deploy/momento-live.service`, `momento-paper.service`, `m10-fetch-secret.sh`, `m9-prod-auth-validate.sh`, `user-data.sh` | Ops |
| `crates/kalshi/src/{production,venue,transport,auth,ws,sandbox,secret,http}.rs` | Trading/auth transport |
| `apps/prod-auth-validate/**`, `apps/sandbox-validate/**` | Milestone auth |
| `crates/core/src/{money,order,fill,intent,config}.rs` and `can_attempt_entry` / 80/81 meaning | Financial/live semantics |

Default: treat **all of `crates/core/**`** as UNTOUCHED unless the control plane assigns an additive module.

---

## IMMUTABLE — no agent writes

| Path | Reason |
|------|--------|
| `Backtesting Suite/Data-Real/**` | Raw historical lake (gzip, parquet, manifests) |
| SHA-256 inside v1 manifests | Reproducibility |

Derived W1 outputs go to `Backtesting Suite/Foundation/W1/` (or equivalent **outside** the lake). That directory is **W1-owned** and mutable as a derived artifact tree.

---

## LEGACY_V1 — do not extend as the platform

Owner: **none for new-engine work**. Preserve for regression. Do not add reconstruction types here.

| Path | Notes |
|------|-------|
| `crates/research-data/src/{catalog,checksum,collector,discovery,export,identity,manifest,normalize,orderbook,paths,raw,replay,schedule,schema,sport,validate}.rs` | v1 lake I/O. W1 **wraps**; does not rewrite meaning of `CompletenessStatus::Complete` |
| `crates/research-data/tests/infrastructure.rs` | Keep green |
| `crates/research-strategies/**` | FIRST01 copy |
| `crates/research-execution/**` | CONSERVATIVE_MAKER; candle refusal |
| `crates/research-backtest/**` | Sheets + validate-mlb |
| `apps/backtest-runner/**` | LEGACY runner |
| `apps/replay-engine/**` | Stub; not live |

**Wrap exception (W1 only):** additive `crates/research-data/src/foundation/**` and `pub mod foundation` in `lib.rs`.

---

## CTO-W0 — documentation only (COMPLETE)

Owner: control agent for new control-plane files; W0 recon files are **frozen**.

| Path | Status |
|------|--------|
| `docs/research/backtesting_rebuild/REPOSITORY_RECONNAISSANCE.md` | FROZEN |
| `docs/research/backtesting_rebuild/CURRENT_ARCHITECTURE_MAP.md` | FROZEN |
| `docs/research/backtesting_rebuild/DATA_INVENTORY.md` | FROZEN |
| `docs/research/backtesting_rebuild/FIRST01_BASELINE_SEMANTICS.md` | FROZEN |
| `docs/research/backtesting_rebuild/REWRITE_BOUNDARY.md` | FROZEN |
| `docs/research/backtesting_rebuild/PROPOSED_CANONICAL_DOMAIN_MODEL.md` | FROZEN |
| `docs/research/backtesting_rebuild/MLB_DATA_RECONSTRUCTION_REQUIREMENTS.md` | FROZEN |
| `docs/research/backtesting_rebuild/KALSHI_DATA_OBSERVABILITY_MATRIX.md` | FROZEN |
| `docs/research/backtesting_rebuild/GOOGLE_REPORTING_ARCHITECTURE.md` | FROZEN |
| `docs/research/backtesting_rebuild/WATERFALL_NEXT_STEP.md` | FROZEN (historical W1 spec) |
| `docs/research/backtesting_rebuild/W0/**` | W0 package (pointers) |
| `docs/research/completions/W0-*.md` | FROZEN |
| `docs/research/architecture-decisions/ADR-*.md` | W0; later ADRs by owning W + control agent |

---

## CTO-W1 — exclusive implementation

| Path | Role |
|------|------|
| `crates/research-data/src/foundation/mod.rs` | Module root |
| `crates/research-data/src/foundation/availability.rs` | 2025/2026 audit |
| `crates/research-data/src/foundation/catalog.rs` | `LakeCatalogV1` |
| `crates/research-data/src/foundation/coverage.rs` | coverage_v2 vocabulary |
| `crates/research-data/src/foundation/envelope_v2.rs` | additive envelope |
| `crates/research-data/src/foundation/guard.rs` | non-overwrite |
| `crates/research-data/src/foundation/identity_stub.rs` | UNMAPPED pk |
| `crates/research-data/src/foundation/integrity.rs` | checksum/gzip/parquet |
| `crates/research-data/src/foundation/ledger.rs` | W1-internal step list |
| `crates/research-data/src/foundation/observability.rs` | field contract |
| `crates/research-data/src/foundation/provenance.rs` | clocks |
| `crates/research-data/src/foundation/reporting.rs` | local artifacts |
| `crates/research-data/src/foundation/runner.rs` | `run_w1_foundation` |
| `crates/research-data/src/foundation/starting_price.rs` | STARTING_PRICE_UNVERIFIED evidence |
| `crates/research-data/src/foundation/w2_contract.rs` | **W1-owned handoff**. W2 reads; W2 does not edit |
| `crates/research-data/tests/w1_foundation.rs` | W1 tests |
| `apps/research-collector/src/main.rs` | **COORDINATED_SHARED** — W1 owns `w1-foundation` command only |
| `docs/research/backtesting_rebuild/w1/**` (Darwin: same as `W1/`) | **W1 agent docs** (`ARCHITECTURE.md`, `LEDGER.md`, `W2_HANDOFF.md`, …) plus **control six-pack** overlaid (FLAG-016). W1 owns agent reports. Control agent owns SPEC/DEPENDENCIES/CONTRACTS/ACCEPTANCE/PROGRESS templates. |
| `Backtesting Suite/Foundation/W1/**` | Derived artifacts (create as needed) |

W1 may **read** LEGACY `schema.rs` / `manifest.rs` / `raw.rs`. W1 may **not** change v1 `SCHEMA_VERSION` meaning or overwrite published v1 files.

---

## DATA-INGEST — reserved exclusive (cross-cutting; not W3)

| Path | Role |
|------|------|
| `crates/research-ingest/**` | Orchestrator, landing, commit gate, W2 consume gate |
| `apps/research-ingest/**` | CLI (`schedule-info`, `run`, `replay`) |
| `docs/research/backtesting_rebuild/ingest/**` | Plane docs |
| `Backtesting Suite/Foundation/Ingest/**` | Landing + run audits (not Data-Real) |

Ingest **must not** edit `foundation/**`, overwrite `Foundation/W2/raw/**`, or write Data-Real. W2 `collect.rs` is not the writer of new landing.

---

## CTO-W2 — MLB event / PBP reconstruction

Do not place these types in `foundation/`.

| Path | Status |
|------|--------|
| `crates/research-event/` | **EXISTS.** W2 exclusive. Consumes committed ingest/W1 artifacts; does not write Data-Real. |
| `docs/research/backtesting_rebuild/W2/**` | W2 docs |
| `Backtesting Suite/Foundation/W2/raw/**` | Frozen W2-E landing. Ingest must not overwrite. |

**W2 must not own:** `foundation/w2_contract.rs` (W1 handoff), Data-Real, production sports crate `crates/sports/src/mlb.rs` (stub; changing it is a shared/core risk — leave UNTOUCHED; put MLB research state in the W2 crate).

---

## CTO-W3 — MLB game/PBP reconstruction layer (2026-08-26)

| Path | Role |
|------|------|
| `crates/research-reconstruction/**` | W3 exclusive |
| `apps/research-w3/**` | CLI |
| `docs/research/backtesting_rebuild/W3/**` | W3 docs |
| `Backtesting Suite/Foundation/W3/**` | Derived reconstruction artifacts |

Must not write Data-Real, fork W1 foundation types, or implement Kalshi `MarketState` (W4).

---

## CTO-W4 — Kalshi market reconstruction (under 2026-08-26 grant)

Reserved: `kalshi_market_reconstruction.rs`, `market_state.rs`. **Not authorized in the W3 grant.**

---

## CTO-W5 — Event ↔ market synchronization

`synchronization.rs`, `sync_meta.rs`, `docs/research/backtesting_rebuild/W4/**` historically named; new grant places sync at W5. `docs/research/backtesting_rebuild/W5/**`

---

## CTO-W5 — reserved (contract design allowed)

`state_transition.rs`, `game_market_episode.rs`, `threshold_touch.rs`, `docs/research/backtesting_rebuild/W5/**`

W2 may emit **event-triggered** before/after game states (PLAN-W5). W5 owns the **canonical** `StateTransition` + `GameMarketEpisode` container. If both need the same type file: **BLOCKED** until control assigns. Current assignment: **canonical types → W5**; W2 defines `GameState`/`PBPEvent` only.

---

## CTO-W6 — Canonical MLB state (grant remap)

`crates/research-state/**`, `apps/research-w6/**`, `docs/research/backtesting_rebuild/W6/**`, `docs/research/backtesting_rebuild/W6_STATE_ENGINE.md`. PLAN-W13 FIRST01 replay is not this owner.

---

## CTO-W7 — EventMarketPath (grant remap)

`crates/research-path/**`, `apps/research-w7/**`, `docs/research/backtesting_rebuild/W7_EVENT_MARKET_PATH.md`, `docs/architecture/w7-event-market-path.md`. PLAN-W15 outcome labels are not this owner.

---

## CTO-W8 — FIRST01 observational replay (grant remap)

Older W8 docs described Greeks (PLAN-W9). This grant implemented FIRST01 replay.

| Path | Role |
|------|------|
| `crates/research-replay/**` | W8 exclusive. Reads W7 `PathStore`; does not write Data-Real. |
| `apps/research-w8/**` | CLI (`--replay`) |
| `docs/research/backtesting_rebuild/W8_FIRST01_REPLAY.md` | Canonical W8 architecture |
| `docs/architecture/w8-first01-replay.md` | Short pointer |
| `Backtesting Suite/Foundation/W8/**` | Derived replay artifacts (`replay.sqlite` gitignored) |

Must not write Data-Real, call live `MlbStrategy`, invent bid/ask, simulate fills, compute P&L, or start W9 outcome labeling. Production `strategies/mlb/**` remains UNTOUCHED.

---

## CTO-W9 … CTO-W11 — reserved stubs only

See each `W#/README.md`. Do not implement W9+ except under a new grant.

---

## Control plane (CTO control agent)

| Path | Owner |
|------|-------|
| `docs/research/backtesting_rebuild/README.md` | Control (index) |
| `docs/research/backtesting_rebuild/WATERFALL_MASTER_REGISTRY.md` | Control |
| `docs/research/backtesting_rebuild/WATERFALL_DEPENDENCY_GRAPH.md` | Control |
| `docs/research/backtesting_rebuild/WATERFALL_CONTRACT_REGISTRY.md` | Control |
| `docs/research/backtesting_rebuild/PARALLEL_RULES.md` | Control |
| `docs/research/backtesting_rebuild/AGENT_HANDOFF_PROTOCOL.md` | Control |
| `docs/research/backtesting_rebuild/WATERFALL_ALIAS_CROSSWALK.md` | Control |
| `docs/research/backtesting_rebuild/FILE_OWNERSHIP_REGISTRY.md` | Control |
| `docs/research/backtesting_rebuild/CTO_REVIEW_FLAGS.md` | Control |
| `docs/research/backtesting_rebuild/PROGRESS_LEDGER.md` | Control |

---

## Conflicts recorded (not guessed away)

| ID | Files | Issue | State |
|----|-------|-------|-------|
| OWN-001 | `crates/research-data/src/lib.rs` | W1 already edits; W2 will need a module | COORDINATED_SHARED — W2 uses new crate |
| OWN-002 | `apps/research-collector/src/main.rs` | W1 added `w1-foundation` | COORDINATED_SHARED — W2 no edits |
| OWN-003 | `crates/research-data/src/catalog.rs` vs `foundation/catalog.rs` | Two catalogs | NOT a collision: LEGACY `ResearchCatalog` vs W1 `LakeCatalogV1`. Do not merge. |
| OWN-004 | `foundation/w2_contract.rs` | Named W2, lives in W1 | Assigned **W1**. W2 consumes. |
| OWN-005 | `crates/sports/src/mlb.rs` | Empty stub; tempting for W2 | UNTOUCHED. W2 crate owns research GameState. |
| OWN-006 | PLAN CSV `W1-A1-S1` vs `ledger.rs` `W1-A1-S1` | Same ID, different work | See FLAG-001. Not a file ownership clash; **identifier clash**. |
| OWN-007 | `docs/.../W1/` vs `w1/` | Case-insensitive FS collision | FLAG-016. Combined index; do not create a second folder |

No remaining file pair is left as “both W1 and W2 own this implementation file.”
