# BACKTEST_ENGINE_WATERFALL.md

**Authoritative engineering roadmap** for the MLB-first Historical Market/Game
State Backtesting & Research Engine.

**Status:** ACTIVE GOVERNANCE BASELINE  
**Date:** 2026-08-26  
**Current W/A/S:** W0 COMPLETE. W1 **ACCEPTED / CLOSED**. W3 **ACCEPTED / CLOSED**.
W4/W5/W6/W7 **IMPLEMENTED**. W8 FIRST01 replay **IMPLEMENTED**. DATA-INGEST identity
rejoin **INGEST.2.1.2** (`rejoin-20260827T114739Z`). W9 not authorized.

This file must not go stale relative to the code. Every completed S-step updates
this document, the registry, current-state, and a completion record.

| Companion | Path |
|-----------|------|
| System specification (CEO/CTO contract) | [`BACKTEST_ENGINE_SYSTEM_SPECIFICATION.md`](BACKTEST_ENGINE_SYSTEM_SPECIFICATION.md) |
| W/A/S registry | [`BACKTEST_ENGINE_WATERFALL_REGISTRY.csv`](BACKTEST_ENGINE_WATERFALL_REGISTRY.csv) |
| Current state | [`BACKTEST_ENGINE_CURRENT_STATE.md`](BACKTEST_ENGINE_CURRENT_STATE.md) |
| Gap analysis (W0-A11 audit) | [`BACKTEST_ENGINE_GAP_ANALYSIS.md`](BACKTEST_ENGINE_GAP_ANALYSIS.md) |
| ADRs | [`architecture-decisions/`](architecture-decisions/) |
| Step completion template | [`templates/WATERFALL_STEP_COMPLETION.md`](templates/WATERFALL_STEP_COMPLETION.md) |
| Step completion records | [`completions/`](completions/) |
| Full technical blueprint | [`HISTORICAL_ENGINE_DEVELOPMENT_PLAN.md`](HISTORICAL_ENGINE_DEVELOPMENT_PLAN.md) |
| Reset notice | [`BACKTESTING_ENGINE_RESET.md`](BACKTESTING_ENGINE_RESET.md) |
| Waterfall 0 recon | [`backtesting_rebuild/`](backtesting_rebuild/) |
| Waterfall 1 spec (do not code yet) | [`backtesting_rebuild/WATERFALL_NEXT_STEP.md`](backtesting_rebuild/WATERFALL_NEXT_STEP.md) |

---

## A. Program mission

Build a deterministic historical engine that can answer, for any MLB game time `t`:

> What was happening in the game, what had happened immediately beforehand, what
> was happening in the Kalshi market/order book, how the market arrived at that
> state, what event-derived state implied, what FIRST01 would have done, what
> happened afterward, and what historical information could have predicted the
> outcome?

MLB is the reference implementation. NBA, WNBA, NHL, and NCAAB are future
adapters — **not** current implementation targets.

FIRST01 is the first **strategy plugin**, not the database.

Primary objects: `StateTransition` (atomic) inside `GameMarketEpisode` (container).
A trade is downstream.

Research never automatically changes live trading.

---

## B. System architecture

```text
RAW HISTORICAL DATA
        ↓
NORMALIZATION                          (versioned)
        ↓
GAME / PBP STATE RECONSTRUCTION        (EVENT domain)
        ↓
KALSHI MARKET STATE RECONSTRUCTION     (MARKET domain)
        ↓
EVENT ↔ MARKET SYNCHRONIZATION
        ↓
STATE TRANSITION DATABASE
        ↓
COMPLETE PATH ENGINE                   (both contracts; not 80% snapshot only)
        ↓
FIRST01 REPLAY                         (plugin)
        ↓
80% TRANSITION INTELLIGENCE
        ↓
LOSER CLASSIFICATION
        ↓
EVENT / MARKET GREEKS                  (empirical, versioned)
        ↓
ORDERBOOK INTELLIGENCE                 (or UNAVAILABLE)
        ↓
FEATURE ENGINE
        ↓
ML / XGBOOST / MONTE CARLO
        ↓
HYPERPARAMETERIZATION                  (supervised; FIRST01 v1 remains control)
        ↓
EXECUTION MODEL                        (MODELED when not OBSERVED)
        ↓
PREDICTION ENGINE
        ↓
RISK DECISION ENGINE                   (production; later bridge only)
        ↓
ALGORITHMIC EXECUTION                  (production; later bridge only)
```

Continuous loop (does not auto-promote models):

```text
LIVE OBSERVATIONS → HISTORICAL DATA → RESEARCH → VALIDATION
  → SUPERVISED MODEL PROMOTION → RISK / EXECUTION
```

**Hierarchy (inviolable):** Strategy proposes. Risk approves. Execution executes.
Research does not bypass this. Production crates remain UNTOUCHED until a later
waterfall is explicitly authorized.

Rewrite boundary: [`backtesting_rebuild/REWRITE_BOUNDARY.md`](backtesting_rebuild/REWRITE_BOUNDARY.md).

---

## C. Waterfall definitions

| W | Name | Intent |
|---|------|--------|
| W0 | Architectural foundation | Contracts, recon, governance docs |
| W1 | Immutable raw data lake | Catalog, provenance, non-destructive foundation |
| W2 | Canonical identity engine | GameId ↔ Kalshi ↔ MLB pk ↔ Team A/B |
| W3 | Time synchronization | Event time ↔ market time + confidence |
| W4 | MLB event state engine | Canonical `GameState` |
| W5 | PBP state transition engine | `State(t-1) → Event → State(t)` |
| W6 | Kalshi market state engine | Per-contract `MarketState` + observability |
| W7 | Team A/B coupled market | Both contracts, starting states |
| W8 | Complete path engine | START → observation; not snapshot-only |
| W9 | Event Greeks | Empirical ΘE, ΔE, … versioned |
| W10 | Market Greeks | Empirical ΘM, … versioned |
| W11 | Threshold transition engine | First-touch 20–95 including FIRST_80 |
| W12 | First-80 state vector | Canonical 80% transition signature |
| W13 | FIRST01 strategy plugin | Replay frozen baseline; do not retune |
| W14 | Execution simulation | Signal → fill; MODELED when unprovable |
| W15 | Outcome / label engine | Future labels only |
| W16 | Loser classification | Temporal/event/price/market/combined |
| W17 | ML / XGBoost / Monte Carlo | After deterministic dataset is trustworthy |
| W18 | Hyperparameterization | Versioned experiments; baseline is control |
| W19 | Validation / anti-overfitting | OOS, walk-forward, leakage detection |
| W20 | Google Drive reporting | Human archive; not raw warehouse |
| W21 | Google Sheets reporting | Index, not database |
| W22 | Deep research artifacts | Machine + human per run |
| W23 | Research dashboard | Episode drill-down |
| W24 | Model registry / governance | RESEARCH → … → PRODUCTION |
| W25 | Future production bridge | Same state schema live ↔ historical |
| W26 | Live → research feedback | Archive live; no auto model rewrite |

**Absolute waterfall rule:** do not silently jump W-to-W. Complete
IMPLEMENT → TEST → VALIDATE → DOCUMENT → ARTIFACT → CHECKPOINT before advancing.
If a step reveals a later dependency: document it and STOP.

---

## D. W/A/S hierarchy

```text
W#  →  A#  →  S#
```

- **W** = waterfall phase
- **A** = architecture / workstream within that waterfall
- **S** = atomic implementation step (independently testable)

S-count is whatever the A-block needs. Do not pad to ten.

The operational list of every step is
[`BACKTEST_ENGINE_WATERFALL_REGISTRY.csv`](BACKTEST_ENGINE_WATERFALL_REGISTRY.csv).

### Summary (architecture blocks)

**W0 Architectural foundation** — COMPLETE as documentation after W0-A11.

| A | Title | Status |
|---|-------|--------|
| W0-A1 | Repository reconnaissance | COMPLETE |
| W0-A2 | Current architecture map | COMPLETE |
| W0-A3 | Data inventory | COMPLETE |
| W0-A4 | FIRST01 baseline freeze | COMPLETE |
| W0-A5 | Rewrite boundary | COMPLETE |
| W0-A6 | Canonical domain model (design) | COMPLETE |
| W0-A7 | MLB reconstruction requirements | COMPLETE |
| W0-A8 | Kalshi observability matrix | COMPLETE |
| W0-A9 | Google reporting architecture (design) | COMPLETE |
| W0-A10 | Waterfall 1 specification | COMPLETE |
| W0-A11 | Governance documentation baseline | COMPLETE (this delivery) |

**W1 Immutable raw / canonical data foundation** — NOT_STARTED (CEO auth required).

| A | Title |
|---|-------|
| W1-A1 | Lake catalog v1 |
| W1-A2 | Coverage vocabulary v2 |
| W1-A3 | Checksum / immutability guards |
| W1-A4 | Raw envelope v2 (additive) |
| W1-A5 | Identity stub v1 |
| W1-A6 | PBP source matrix (catalog only, no download) |
| W1-A7 | Production fence / demo≠real |
| W1-A8 | Optional Kalshi re-query | DEFERRED until separately authorized |

**W2–W26** architecture blocks are registered in the CSV. Do not start them.

---

## E. Current status

| Item | Value |
|------|-------|
| Waterfall | W0 COMPLETE |
| Architecture | W0-A11 COMPLETE |
| Next S-step | **W1-A1-S1** Specify `lake_catalog_v1` schema (docs + fixtures) |
| Authorization | W1 implementation **not** authorized by this document |
| Production orders from this program | 0 |
| FIRST01 live behavior changes | 0 |
| Rust types `GameMarketEpisode` / `StateTransition` | **Do not exist yet** |
| MLB PBP locally | **None** |
| Historical L2 | **UNAVAILABLE** (Kalshi does not sell it retrospectively) |

---

## F. Completed work

- Waterfall 0 recon package (`docs/research/backtesting_rebuild/*`).
- Reset + full development plan (`BACKTESTING_ENGINE_RESET.md`,
  `HISTORICAL_ENGINE_DEVELOPMENT_PLAN.md`).
- FIRST01 live/research audits (plugin control baseline).
- LEGACY_V1 Kalshi collector, lake schema 1.0.0, candle FIRST01 runner,
  Sheets control plane — **preserved, not the new platform**.
- Local Data-Real inventory: 13 COMPLETE MLB days (2026-06-18 … 2026-06-30),
  172 games, 344 contracts, ~3.4M trades, 1-minute candles.
- Governance baseline (this file, system spec, registry, ADRs, templates,
  current-state, gap analysis).

---

## G. Blocked work

| Item | Blocker |
|------|---------|
| W1 implementation | CEO authorization |
| W1-A8 Kalshi re-query | Separate authorization; official docs re-read at implementation |
| PBP acquisition | Source/license not approved; W1-A6 catalogs only |
| FIRST01 replay on reconstructed state | Requires W1–W12 |
| FIRST01 retune | Forbidden until path/state truth + explicit experiment approval |
| NBA/WNBA/NHL/NCAAB adapters | MLB must complete the full waterfall first |
| Drive/Sheets new-engine reporting | Waterfalls 20–21 |
| Production bridge | Waterfall 25 + explicit live-safety approval |

---

## H. Dependencies

```text
W0  (docs) ──► W1 (raw catalog/provenance)
W1 ──► W2 (identity; needs catalogued tickers)
W2 ──► W3 (sync; needs identity + timestamps)
W1 ──► W6 (market state; needs raw)
W2 + PBP source ──► W4 / W5 (event state; PBP not present locally)
W3 + W4 + W6 ──► W7 / W8 (coupled paths)
W8 ──► W9 / W10 / W11 / W12
W12 ──► W13 (FIRST01 plugin)
W13 ──► W14 … W19
W8+ ──► W20 / W21 / W22 (reporting consumes artifacts)
W19 + W24 ──► W25 (production bridge)
W25 ──► W26 (feedback loop)
```

If an S-step discovers a later-W dependency: record it here and STOP.

---

## I. Acceptance criteria (program-level)

MLB is not “done” when a P&L table exists. See completion gates in
`HISTORICAL_ENGINE_DEVELOPMENT_PLAN.md` (Data, Reconstruction, Market, Event,
Market↔event, FIRST01 plugin, Research, ML, Reporting, Reproducibility).

Each S-step has additional criteria in the registry.

**This delivery (W0-A11) is accepted when:**

1. Master waterfall, system spec, registry, ADR system, completion template,
   and current-state exist.
2. Repository audit + gap analysis exist.
3. No historical-engine implementation was started.
4. Production trading surfaces were not modified.

---

## J. Test requirements (program-level)

Every S-step lists tests in the registry. Categories where applicable:

- unit, integration, data integrity
- timestamp, state-machine, invariant
- regression, no-lookahead, reproducibility, performance

A passing compiler is **not** completion. Do not delete failing production
tests to make research work pass.

W1 test list (preview): checksum replay, v1 round-trip, no_synthetic_rows,
demo≠real, envelope v2, non-overwrite fail-closed, observability enum,
production fence, no invented 2025 games.

---

## K. Artifact requirements

Machine-readable artifacts live on the lake / future object storage.
Human-readable reports go to Drive **after W20**. Sheets index **after W21**.

W0 artifacts: this documentation set + recon package. No parquet writers added.

---

## L. Google Drive reporting requirements

See ADR-0014 and `backtesting_rebuild/GOOGLE_REPORTING_ARCHITECTURE.md`.

- Drive is not the raw warehouse.
- After W20: every major phase produces reports organized
  SPORT → YEAR → DATASET → RUN → WATERFALL → EXPERIMENT.
- Include methodology, assumptions, limitations, experiment/dataset/model versions.
- LEGACY FIRST01 Runs folder is preserved; new engine uses a separate tree.

**W0–W19:** `drive_reporting_required = NO` (design only).

---

## M. Google Sheets reporting requirements

See ADR-0015.

- Sheets is an index, not the database.
- New engine must not mix reconstruction metrics into LEGACY candle P&L columns.
- After W21: indexed visibility into datasets, runs, validation, opportunities,
  trades, classifications, experiments, metrics, errors, coverage, sync quality,
  model versions, deployment candidates.

**W0–W20:** `sheets_reporting_required = NO` except LEGACY_V1 candle jobs.

---

## N. Architecture decisions

Canonical ADRs: [`architecture-decisions/`](architecture-decisions/).

Seeded ACCEPTED decisions: raw immutability, timestamp authority, PBP sync,
event time, MLB 54-out remaining-opportunity, first-80, Team A/B, orderbook
honesty, market/event theta (formulas deferred), feature availability,
no-lookahead, model promotion, Drive, Sheets, primary objects, FIRST01 plugin,
GameId canonical, W/A/S methodology, observability honesty.

---

## O. Known risks

1. Kalshi historical API may never return pre-2026-06-18 `KXMLBGAME` markets.
2. Close/settled PT-day partitions omit lifetime starting prices.
3. No historical L2; maker fills unprovable on candles.
4. No PBP locally; event domain blocked until a licensed source is authorized.
5. `orderbook.parquet` naming invites candle-as-L2 misuse.
6. Default `MOMENTO_RESEARCH_DATA_DIR` points at demo `Data/`, not Data-Real.
7. `RawMarketEvent.received_at` is collector clock, not exchange time.
8. Shared `momento-core` edits can accidentally change production.
9. FIRST01_live_entry_state_machine.md still contains an obsolete “new
   opportunity after complete” sentence (later audits are canonical).
10. No git metadata in this workspace copy — commit hashes cannot be recorded here.

---

## P. Open questions

1. Official MLB PBP vendor / StatsAPI / licensed feed — **not chosen**.
2. Default research root confirmation: Data-Real vs env (W1 prerequisite).
3. New crate name (`momento-research-lake` vs additive `research-data` modules).
4. Cloud object-storage target (local lake first).
5. Whether W1-A8 re-query is in the same CEO authorization as W1-A1–A7.
6. Walk-off remaining-outs definition v1 details (ADR-0005; encoded in W4).
7. Live vs research same-quote 81-confirm clock for the W13 plugin tests.

---

## Q. Change history

| Date | Change |
|------|--------|
| 2026-08-26 | Reset: candle FIRST01 runner is LEGACY_V1; new platform declared. |
| 2026-08-26 | Waterfall 0 recon package delivered (`backtesting_rebuild/`). |
| 2026-08-26 | **W0-A11:** governance baseline — master waterfall, system spec, registry, ADRs, templates, current-state, gap analysis. No engine implementation. |

---

## Checkpoint rule (every S-step)

1. Run required tests.
2. Validate output.
3. Inspect for regressions.
4. Update this file.
5. Update the registry CSV.
6. Write the step completion record.
7. Create/update ADRs if a decision was made.
8. Update `BACKTEST_ENGINE_CURRENT_STATE.md`.
9. Record artifacts.
10. Record Drive/Sheets reporting status.
11. Identify the next W/A/S.
12. **STOP** (unless the execution instruction explicitly authorizes the next S-step).

---

## Cursor execution behavior (implementation prompts)

When given a specific W/A/S:

1. Read governing documents.
2. Inspect existing code.
3. Determine dependencies.
4. Implement **only** authorized scope.
5. Do not rewrite unrelated systems or live production unless instructed.
6. Run tests; validate; document; update waterfall records.
7. Report files changed, tests run, artifacts created, unresolved issues.
8. Identify next W/A/S.
9. STOP.

---

```text
IMPLEMENTATION OF WATERFALL 1: NOT STARTED
PRODUCTION ORDERS TRANSMITTED: 0
FIRST01 BEHAVIOR CHANGES: 0
```
