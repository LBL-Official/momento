# DRE V7 — Repository Audit

**Program:** `MOMENTO_DYNAMIC_RISK_ENGINE_V7`  
**Schema:** `1.0.0`  
**Date:** 2026-09-03  
**Live execution:** FALSE

Audit completed **before** V7 scientific tables. Paths confirmed on disk. No path invented. No V7 VAL/OOS outcome table was produced during this audit.

```
LIVE EXECUTION = FALSE
Δα_state ≠ EDGE
CONDITIONAL INFORMATION ≠ EXECUTION
REPEATED POSSESSIONS ≠ INDEPENDENT OUTCOMES
LIVE DEPLOYMENT: NOT AUTHORIZED
```

**Prominent statement:**

> An observed state is not necessarily a well-supported state; a well-populated state is not necessarily independently supported; and an exactly scored state is not necessarily supported by a robust empirical distribution.

```
UNIQUE_TRADE_SUPPORT ≠ STATISTICAL_INDEPENDENCE
N_EFF_TRADE = OCCUPANCY CONCENTRATION MEASURE ≠ INDEPENDENT SAMPLE SIZE
```

V7 does **not** write to PADE, DRE V2–V6, FIRST01, Risk, live config, frozen FIRST-80 `candidates.json`, hedges, or `fee_models.py`.

V5 Verdict B is historical. V6 `UNCLASSIFIED_PRE_REGISTERED_OUTCOME` is historical. V7 does not reopen either.

---

## Occupied frontend ports (verified)

| Port | App |
|-----:|-----|
| 5173–5188 | prior research dashboards (DRE V6 = 5188) |

**DRE V7 dashboard port:** `5189`.

---

## 1. Exact source of each V7 input

| Input | Source | Role |
|-------|--------|------|
| Possession rows | PADE `03_possessions.parquet` | V5 `build_priors` only |
| Trade–possession panel | PADE `05_trade_possession_panel.parquet` | V5 `build_panel` (internal) and priors join |
| Frozen maps | V6 `02_train_frozen_m0_m1.json` | Sole scoring map |
| V6 trade SIR | V6 `04_trade_sir.parquet` | Optional identity cross-check |
| V6 state SIR | V6 `05_state_sir.parquet` | Incomplete (no bins); not a support source |
| V6 decile edges | V6 `03_train_decile_edges.json` | Gate J only |
| V5 / V6 locks | predecessor JSON | Gate A |
| Splits | PADE `dataset_split` via V5 panel | inherited; not rebuilt |

---

## 2. Can V7 consume persisted V6 maps directly?

**Yes.** File exists. Schema:

- `m0`: keys `"{price:.1f}"` → TRAIN trade-balanced cell mean of `pi_terminal`
- `m1`: keys `"price|score|clock|nhat"` via `dre_v6.maps.m1_key`
- `global_mean`: 0.7157057654075547
- `n_m0`: 20, `n_m1`: 584
- `identity.observed` matches published V5 MAE exactly
- Fallback: missing M1 → M0(price) → global mean

Import `dre_v6.maps.load_persisted`, `predict_m0`, `predict_m1`, `m1_key`, `price_key`. Do not copy-modify V6.

---

## 3. Was the V6 state-level scored panel persisted?

**Partially.** `05_state_sir.parquet` was written with only:

`trade_id, event_id, dataset_split, possession_index, alpha_m0, alpha_m1, da_state, r_t, pi_terminal`

**No bin columns.** Cell support cannot be computed from it.

---

## 4. Reconstruction path

V7 rebuilds the panel **in memory** with unchanged V5 functions:

```
build_priors(poss, pade_panel) -> (priors, pace_audit)
build_panel(priors) -> df   # 139,966 rows expected
```

Then scores **only** from persisted V6 maps. **`m0_m1()` is not called.**

### Reconstruction provenance (Rule 3)

`build_priors` (`dre_v5/possession_remaining.py`):

- One `03_possessions` row = one offensive possession.
- Team pace for game G uses only games whose terminal completion (`max wall_end_ts`) is **strictly before** G began (`min wall_start_ts`). Same-day games excluded unless that inequality holds.
- Never uses `actual_remaining_possessions`.
- League-mean fallback is the **TRAIN** team-possession mean (V5 frozen). VAL/OOS games do not refit that mean.

`build_panel` (`dre_v5/state_panel.py`):

- Reads PADE `05` internally. `n_hat` L1 tertiles computed from **TRAIN** `n_hat_remaining_prior` only and stored on `df.attrs`.
- `dataset_split` inherited. No split reassignment.

V7 documents this frozen process. It does **not** claim a newly cleaned causal pipeline. `Reproduce V5 exactly ≠ quietly improve V5.`

---

## 5. Exact bin definitions

From `dre_v5/state_panel.py` (not redesigned):

| Bin | Rule |
|-----|------|
| `price_bin_5` | `floor(price_cents / 5) * 5` |
| `score_bin_l1` | `ge_p10 \| p5_9 \| p1_4 \| zero \| m1_4 \| le_m5` from A1 score differential |
| `clock_bin_l1` | `Q1_Q2 \| Q3 \| Q4_GT6 \| Q4_2_6 \| Q4_LT2 \| OT` |
| `n_hat_bin_l1` | TRAIN tertiles → `low \| mid \| high`; missing → None |

M1 cell: `(price_bin_5, score_bin_l1, clock_bin_l1, n_hat_bin_l1)`.

---

## 6. Identifiers

| Field | Meaning |
|-------|---------|
| `trade_id` | One FIRST-80 logical position |
| `event_id` | Game-level split-isolation key |
| `nba_game_id` | NBA game id on the PADE panel |

---

## 7–8. Rows, trades, games

- Possession row ≠ independent terminal outcome.
- On this panel: **one trade per game** (TRAIN 503 / VAL 481 / OOS 237).
- One trade per game is a **support unit**, not proof of statistical independence.

---

## 9. Predecessor output trees

**V5** `.../dynamic_risk_engine_v5/`: locks, protocol, surfaces, hazard, greeks, universe, manifest (`headline=B`), dashboard JSON, reports. No panel parquet.

**V6** `.../dynamic_risk_engine_v6/`: locks, protocol, `02_train_frozen_m0_m1.json`, `03_train_decile_edges.json`, SIR parquets, measurement JSON, halt manifest `UNCLASSIFIED_PRE_REGISTERED_OUTCOME`.

---

## 10. Hash snapshots

V7 Gate B snapshots the **complete** V5 and V6 trees before the run and compares after (Gate G). Also hashes `dre_v5/possession_remaining.py`, `dre_v5/state_panel.py`, `dre_v5/surfaces.py`, `dre_v6/maps.py`.

---

## Gate J — V6 decile edges (verified in this audit)

File: `03_train_decile_edges.json`

| Item | Recorded value |
|------|----------------|
| source variable | `TRAIN mean_SIR_i` |
| unit of observation | **trade** (one `mean_SIR_i` per `trade_id`) |
| transformation | `pandas.qcut` 10 bins |
| edge semantics | `CLIP_TO_TRAIN_EXTREMA`; `pd.cut include_lowest=True right=True` after clip |

V7 Relationship C `mean_da_i` is the same object as V6 `mean_SIR_i` (trade-level mean of `da_state`). High-versus-low **may** apply these edges **after** run-time re-verification of the four fields. Possession-level `da_state` must not receive these edges as if they were state-level cuts.

If a future artifact disagrees: `NOT_APPLICABLE` / `INCONCLUSIVE`. No conversion. No new quantiles.

---

## Four fields that must never collapse

| Field | Meaning |
|-------|---------|
| `EXACT_CELL_EXISTS` | Frozen M1 key present in persisted map |
| `TRAIN_UNIQUE_TRADE_SUPPORT` | Unique TRAIN trades in that cell |
| `N_EFF_TRADE` | Occupancy-concentration effective trade count |
| `SCORING_PATH` | `M1_EXACT` / `M0_FALLBACK` / `GLOBAL_FALLBACK` |

---

## Exact import paths V7 may use (read-only)

```
dre_v5.possession_remaining.build_priors
dre_v5.state_panel.build_panel, panel_counts
dre_v5.splits.audit_splits
dre_v6.maps.load_persisted, predict_m0, predict_m1, m1_key, price_key
```

V7 writes only to:

- `apps/nba-data/scripts/dre_v7/`
- `apps/nba-data/scripts/dre_v7.py`
- `.../dynamic_risk_engine_v7/`
- `docs/research/DRE_V7_*.md`, `MOMENTO_DYNAMIC_RISK_ENGINE_V7.md`
- `frontend/dre-v7/`

**LIVE DEPLOYMENT: NOT AUTHORIZED**
