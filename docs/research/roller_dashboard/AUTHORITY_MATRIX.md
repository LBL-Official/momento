# ROLLER Terminal — Authority Matrix

**Date:** 2026-09-07  
**Status:** Phase 0 contract  
**Rule:** Conflicting implementations stay explicit. Missing capabilities = `ABSENT — MUST NOT INVENT`.  
**Architecture:** BBALL1 = universe. FIRST80 = one Research Object. Portfolio = Phase 7 consumer.

```text
Δ ≠ EDGE · Γ ≠ EDGE · Θ ≠ EDGE · BASIS ≠ EDGE
F_t ≠ TRUE PROBABILITY · MEASUREMENT ≠ EDGE
SURVIVE ≠ TERMINAL_YES · CANDLE PATH ≠ FILL
```

---

## How to read this table

| Column | Meaning |
|--------|---------|
| Dashboard may call? | `YES` = bind via `definition_versions`; `LATER` = Phase 7+; `NO` = do not expose as math |
| Also-ran / conflict | Parallel code that must not silently replace the SoT |

---

## 1. Point-in-time / observation (“What exists?”)

| Research concept | Authoritative path | Symbol | definition_version | Also-ran / conflict | Dashboard may call? |
|------------------|--------------------|--------|--------------------|---------------------|---------------------|
| Half-open I(t) | `ROLLER/roller/point_in_time/filters.py` | `public_filter` | `4.0.0-C` | — | YES |
| `as_of` / InformationSet | `ROLLER/roller/point_in_time/query.py` | `Roller.as_of` | `4.0.0-C` | — | YES |
| Dataset load (PIT) | same | `Roller.dataset` | `4.0.0-C` | Admin unrestricted loaders | YES |
| Observation O_t | `ROLLER/roller/state/observation.py` | `assemble_observation` | state `2.0.0` | Must not include labels/FIRST80/Greeks | YES |
| Clock snap | `ROLLER/roller/state/clock_snap.py` | `clock_snap` / `snap_events` | `4.1.0-R` | — | YES |
| Trajectory Γ_t on O_t | `ROLLER/roller/state/trajectory.py` | `trajectory_features` | state `2.0.0` | Not path-EV | YES |
| Generic research() | `query.py` | `Roller.research` | raises | — | NO (stub) |

---

## 2. Fundamental / Greeks (measurements ≠ edge)

| Research concept | Authoritative path | Symbol | definition_version | Also-ran / conflict | Dashboard may call? |
|------------------|--------------------|--------|--------------------|---------------------|---------------------|
| F_t prior-only | `ROLLER/roller/fundamental/estimator.py` | `estimate_fundamental` | `4.0.0-A` | Not truth / not edge | YES |
| F_t conditioning | `ROLLER/roller/fundamental/conditioning.py` | — | `core_v1` | — | YES |
| V4B empirical Greeks | `ROLLER/roller/v4b/measurements.py` | `compute_observed` / payload | `4.0.0-B` | Legacy `roller/greeks/*` stubs | YES |
| V4C taxonomy overlay | `ROLLER/roller/v4c/mapping.py` | `overlay_architecture` | `4.0.0-C` | Zero new numbers | YES |
| NOT_CONSTRUCTIBLE | `ROLLER/config/greek_v4c_registry.json` + `v4c/capability.py` | status enum | `4.0.0-C` | Never coerce to 0 | YES |
| V3 response Y_h | `ROLLER/roller/measurement/response.py` | `build_response` | measurement `3.0.0` | — | YES |
| V3 baseline E[Y\|C] | `ROLLER/roller/measurement/baseline.py` | `compute_baseline` | `3.0.0` | — | YES |
| V3 residual | `ROLLER/roller/greeks/residual.py` | `compute_residual` | `3.0.0` | — | YES |
| EDGE as Greek | — | — | — | **ABSENT — MUST NOT INVENT** | NO |

---

## 3. FIRST80 Research Object binding (one object, dual homes)

| Research concept | Authoritative path | Symbol | definition_version | Also-ran / conflict | Dashboard may call? |
|------------------|--------------------|--------|--------------------|---------------------|---------------------|
| HIT80 / HIT40 / spread | `ROLLER/roller/research/quality.py` | `HIT80=8000`, `HIT40=4000`, `MAX_SPREAD_E4=1000` | `frozen_v1` | Warehouse `HIT80`/`HIT40`/`MAX_SPREAD` same values | YES |
| Tradable quality | same + warehouse audit | `quality` | `frozen_v1` | Must stay identical | YES |
| Game window | `ROLLER/roller/research/game_window.py` | `game_window` | `frozen_v1` | WNBA may prefer `open_ts` in warehouse wrapper | YES + flag sport |
| FIRST80 + T40 scan (ROLLER) | `ROLLER/roller/research/first80.py` | `scan_ticker` | `roller_4.1.0-R` / `frozen_v1` | **CONFLICT HOME** vs warehouse | YES if binding declared |
| FIRST80 scan (warehouse) | `apps/nba-data/scripts/nba_80_40_execution_audit.py` | `scan`, `build_candidates` | `warehouse_frozen_v1` | WNBA/NCAAB wrappers | YES if binding declared |
| Frozen identity ledger | `…/derived/nba/first80_execution_audit/candidates.json` | — | `warehouse_frozen_v1` | N=1230 settled NBA | YES (population lock candidate) |
| Kalshi W | ROLLER `settled_yes` / warehouse `expiration_result_yes` | — | `frozen_v1` | Not box `home_win` | YES |
| Wick/low stop | warehouse `first_40_low_*` | secondary | `warehouse_frozen_v1` | Primary stop = close ≤40 | YES as secondary only |
| MLB FIRST01 sticky bid | `crates/research-replay` | — | MLB | **Different sport/semantics** | NO for BBALL1 |

**Terminal rule:** every FIRST80 run must set `definition_versions.FIRST80` to exactly one of `warehouse_frozen_v1` or `roller_4.1.0-R`. Reconciliation tests detect divergence; do not auto-normalize.

---

## 4. Clock / population structure (BBALL1)

| Research concept | Authoritative path | Symbol | definition_version | Also-ran / conflict | Dashboard may call? |
|------------------|--------------------|--------|--------------------|---------------------|---------------------|
| ASKED_SIX | `ROLLER/roller/state/clock.py` | `ASKED_SIX = {Q2,Q3,H1_2,H2_1}` | `4.1.0-R` | first75 asked-six tables | YES |
| NBA/WNBA periods | clock_snap / entry_slice | Q1–Q4 | — | — | YES |
| NCAAB half slices | `ncaab_pbp_align.entry_bucket` / ROLLER clock | H1_1…H2_2 | — | — | YES |
| P5∩P5 filter | `ncaab_pbp_espn_ingest.P5_CODES` + barrier `load_frozen_p5_first80` | — | P5 freeze | Full NCAAB FIRST80 (~thousands) | YES; default P5 for BBALL1 |

---

## 5. Path / barrier / EV (empirical → economic)

| Research concept | Authoritative path | Symbol | definition_version | Also-ran / conflict | Dashboard may call? |
|------------------|--------------------|--------|--------------------|---------------------|---------------------|
| Nested barriers 60/50/40 | `apps/*/scripts/first80_*barrier_survival.py` | `first_close_touches`, `ev_*_gross` | `barrier_survival_v1` | Triplicated per sport | YES (sport-specific OUT) |
| Gross path EV (+20/−40 style) | barrier scripts | `ev_stop_gross`, `ev_hold_gross` | `barrier_survival_v1` | Often fee=0 — must label | YES with caveat |
| Fee estimate | `nba_80_40_execution_audit.quadratic_fee_e6` | `quadratic_fee_e6` | `quadratic_fee_e6_v1` | `fee_models.py` cents-unit fork; production ZeroFeeModel | YES research only |
| Slippage mix EV | `first80_q23_40_loser_slip20_ev.py` | — | research-day | — | YES if bound |
| Generic path DSL / arbitrary barriers | — | — | — | **ABSENT — MUST NOT INVENT** (beyond bindings) | NO until versioned engine |
| Production KalshiFeeModel | `crates/risk/src/fees.rs` | ZeroFeeModel | production | Not research SoT | NO for research math |

---

## 6. Sample splits / portfolio (downstream)

| Research concept | Authoritative path | Symbol | definition_version | Also-ran / conflict | Dashboard may call? |
|------------------|--------------------|--------|--------------------|---------------------|---------------------|
| NBA/NCAAB dataset_split | `nba_80_40_execution_audit.dataset_split` | IN_SAMPLE / VALIDATION / OOS | `warehouse_frozen_v1` | WNBA overwrites dates | YES; sport-specific |
| WNBA dataset_split | `wnba_80_40_execution_audit` | — | WNBA freeze | Conflict with NBA dates | YES; do not unify silently |
| Q23 portfolio sim | `first80_q23_novapr_portfolio_sim.py` | — | `q23_portfolio_v1` | GPE/DRE portfolios | **LATER (Phase 7)** |
| Dual-sport portfolio | `first80_dual_sport_novapr_portfolio_sim.py` | — | `dual_sport_portfolio_v1` | — | **LATER (Phase 7)** |
| Portfolio return as edge | — | — | — | **ABSENT as edge claim** | NO |

---

## 7. Terminal runtime (contracts only in Phase 0)

| Research concept | Authoritative path | Symbol | definition_version | Also-ran / conflict | Dashboard may call? |
|------------------|--------------------|--------|--------------------|---------------------|---------------------|
| Research Object schema | `docs/research/roller_dashboard/research_spec.schema.json` | — | `research_spec_v0` | — | YES (contract) |
| Vocabulary registry | `research_vocabulary_v0.json` | — | `vocab_v0` | Not a dropdown substitute for math | YES (semantic layer) |
| Adapter validation/hash | `ROLLER/roller/dashboard_adapter/` | — | Phase 0 | No math | YES |
| HTTP Research API | — | — | — | MLB `apps/research-api` is unrelated | **ABSENT — MUST NOT INVENT** beyond draft |
| Vocabulary compiler runtime | — | — | — | — | **ABSENT — MUST NOT INVENT** (Phase 3) |
| NL as permanent query format | — | — | — | Forbidden | NO |

---

## 8. Explicit non-equivalences (UI must not collapse)

| Must not display as | Equals |
|---------------------|--------|
| EDGE | Δ, Γ, Θ, BASIS, F_t, residual, path EV, portfolio return |
| TERMINAL_YES / W | SURVIVE / ¬T40 |
| FILL / executable | Candle first touch / low wick |
| TRUE PROBABILITY | F_t |
| 0 | NOT_CONSTRUCTIBLE / null measurement |

---

## 9. Acceptance

Phase 0 authority is satisfied when every terminal-visible concept either:

1. binds to a row above with `definition_version`, or  
2. is labeled `ABSENT — MUST NOT INVENT`, or  
3. is marked `LATER` with phase ownership.
