# Target architecture — Momento Research Engine v1

Migration plan from [current-state.md](current-state.md). Research only.
Does not authorize W9, invented L2, or live FIRST01 / 80/81/83/89 / stop /
risk changes.

---

## 1. What we are building

A **research operating system**, not a static B1 script library.

Central objects:

`DATASET` → `STRATEGY` → `EXPERIMENT` → `HYPOTHESIS` → `RESULT` → `CANDIDATE` → `PROMOTION`

B1 is the first **research family**. The platform is not hard-coded to B1.

React is the **Momento Research Console**. It is not the engine.

```text
CLI (momento-research-b1)
        ↘
         Research Engine  → FeatureStore / W6–W8 / artifacts
        ↗
React  → Research API
```

Do not duplicate B1 eval, FDR, or extract in the frontend.

---

## 2. Planes (v1 vs later)

| Plane | v1 | Later |
|---|---|---|
| **Data** | Register existing W6–W8 + B1 extracts; capability profile; quality report from data | Continuous ingest, new venues |
| **Research** | Experiment definition, grid search, BH FDR, TRAIN/VAL/TEST lock, lineage | Walk-forward, Bayesian (only if justified) |
| **Trading** | Interfaces only. No live POST from this work. | Paper/live through existing Risk → Execution |
| **Portfolio** | Simulated HOLD_TO_SETTLEMENT P&L using existing B1 metrics | Shared live accounting |
| **Control** | Local SQLite registry, jobs, promotion gate, auth token | Managed Postgres, SSO |

v1 is a **modular monolith**. No Kubernetes, Kafka, or microservice sprawl.

---

## 3. Repository shape (adapted, not forced)

Existing crates stay. New surface:

```text
crates/research-engine/     dataset registry, experiments, jobs, import
apps/research-api/          HTTP + in-process worker
frontend/research-console/  React control plane
artifacts/research-engine/  experiment artifacts (gitignored)
docs/architecture/          current-state + this file
```

B1 implementation remains in `crates/research-features`. The engine **calls**
it. It does not rewrite `pick_first_83`, `eval`, or exhaustive classification.

CLI flags `--search-83-exhaustive` and `--first-exact-83` stay.

---

## 4. Data contracts

### Capabilities

Each dataset version has an explicit profile. B1 first-83:

| Capability | Status |
|---|---|
| trade | available |
| game_state | available (W6 at-or-before) |
| timestamps | available |
| l1 / l2 / order_events / queue | **unavailable** — do not compute |

Never reconstruct missing L2 and label it observed.

### Provenance

Dataset version records: source paths, schema/engine versions, universe
definition, event definition, split defaults, fill status, quality metrics
**computed from data**.

### Versioning

`B1_FIRST83_v1` is the registered name for the locked 2,906-game extract.
New extracts create `v2+`. Experiments pin a version. Do not overwrite
`B1/features.sqlite` or `B1/first83/` in place to “refresh” research.

---

## 5. Official split (immutable inside a completed experiment)

Default B1 cuts (configurable on **new** drafts only):

- TRAIN: `date < 2025-10-07`
- VAL: `2025-10-07 ≤ date < 2026-05-03`
- TEST: `date ≥ 2026-05-03` (observed through `2026-06-27`)

Selection score and parameter cuts use TRAIN (and VAL for selection).
TEST is a pass/fail gate after freeze. The API warns if a draft would
use TEST for selection. It does not silently allow it.

---

## 6. Experiment and search

`ExperimentDefinition` includes: name, dataset version, strategy, feature
set, parameters / ranges, split dates, execution model (`TRADE_PRINT_MODELED`
for B1), fees/slippage (explicit; default 0 and labeled), sizing
(`qty = 625 // 83`), seed, search method (`single` \| `grid`), FDR method
(BH), parent experiment id.

Grid search = Cartesian product of listed parameter values. Report
hypothesis counts (total / ok / failed / excluded).

FDR is computed **inside that experiment’s search space**. A one-cell
re-run of `start_price_band=40_49` will not reproduce q=0.17 from 6,128
tests. The canonical q=0.17 lives on the **imported exhaustive experiment**.
The UI must always show `number_of_tests`.

---

## 7. Classification and promotion

Research-cell labels (B1 hold search, unchanged rules):

`REJECTED` · `EXPLORATORY` · `OVERFIT` · `CANDIDATE` ·
`CANDIDATE_THIN_VALIDATION` · `ROBUST`

Platform lifecycle (orthogonal; never auto-advanced):

`DRAFT` → `RUNNING` → `COMPLETED` | `FAILED`

Then, by explicit action only:

`HYPOTHESIS` → `CANDIDATE` → `ROBUST_CANDIDATE` → `PAPER` → `SHADOW` →
`APPROVED` → `PRODUCTION`

`RETIRED` / `REJECTED` are terminal-ish (reopen is a new object).

**Forbidden:** `CANDIDATE` → `PRODUCTION` in one step.

Imported B1 results: 40–49 and inning-7/PEAK_AT are **CANDIDATE /
HYPOTHESIS**. Production count is 0.

---

## 8. Jobs

```text
POST /api/experiments  → persist DRAFT
POST /api/experiments/{id}/run → QUEUED job
worker thread → configured B1 search → artifacts + COMPLETED
GET  /api/jobs/{id}  (progress, logs)
```

HTTP never blocks on the full search. Local in-process queue is enough.

---

## 9. Console (internal)

Host separately from `momentosystems.com`. Local default:
`http://127.0.0.1:5173` → API `http://127.0.0.1:8787`.

Bearer token from `MOMENTO_RESEARCH_TOKEN` (local default documented).
No venue credentials in the frontend bundle.

Pages: Dashboard, Experiments, New Backtest, Run, Results, Compare,
Datasets, Strategies, Models, Candidates, Data Quality, Jobs, System.

The console submits specs and renders stored results. No stats in React.

---

## 10. Migration stages

| Stage | Work | B1 behavior |
|---|---|---|
| 1 | This audit | unchanged |
| 2 | Characterization tests (universe, splits, leakage) | unchanged |
| 3 | Shared official-split module; public eval wrappers | same dates / same eval |
| 4 | Dataset registry + import `B1_FIRST83_v1` | read-only register |
| 5 | Dataset builder = existing `run_first83_extract` | already exists |
| 6–8 | Configured search + FDR + classify via existing functions | wrap, don’t rewrite |
| 9 | Research API | — |
| 10 | React console | — |
| 11 | Experiment persistence + artifact dir | do not overwrite first83/ |
| 12 | Model lifecycle records (stubs + promotion gate) | no live promote |
| 13 | Orchestration interfaces (manual/scheduled hook) | no auto-trade |
| 14 | Execution traits (sim only) | no Kalshi POST |

At each stage: tests, no silent methodology change.

---

## 11. Acceptance

1. Reconstruct / load `B1_FIRST83_v1` → N=2,906, first exact 83¢ TRADE,
   official split, unconditional metrics ≈ locked table.
2. 40–49 benchmark visible with n/EV and imported FDR q≈0.17, status
   CANDIDATE.
3. Custom grid from the console (no Rust edit) → persist → progress →
   TRAIN/VAL/TEST + FDR + hypotheses.

Differences from rounding or imported vs re-run FDR search-space must be
**documented**. Silent definition changes are not acceptable.

---

## 12. Non-goals (v1)

- W9, Greeks, live P&L, FIRST01 retune
- Invented L2
- Bayesian optimization
- Production promotion of any B1 cell
- Hosting the console on the public website
- Replacing `momento-research-b1`
- Extending the legacy candle backtester as this platform
