# ROLLER V4A pre-implementation audit

**Date:** 2026-09-06  
**Purpose:** Gate 1. Confirm V1/V2/V3 temporal contracts before any fundamental estimator.  
**Invariant (locked):** `visible(row, t)` iff `available_at < t`. Equality hidden.

V1/V2/V3 pytest, `scripts/validate_roller.py`, and `scripts/leakage_audit.py` were re-run as part of this gate. All passed. Do not treat planned V4A objects as implemented.

```text
F_t ≠ TRUTH    K_t ≠ F_t    K_t - F_t ≠ EDGE
observation() ≠ fundamental() ≠ labels()
LIVE EXECUTION = FALSE
```

## Required V4A conditions

| Component | Expected | Actual | Status | V4A Dependency | Recommended Action |
|-----------|----------|--------|--------|----------------|--------------------|
| PIT half-open | `available_at < cutoff` | [`timeutil.apply_as_of`](../roller/timeutil.py); [`filters.public_filter`](../roller/point_in_time/filters.py) | PASS | Required — do not switch to `<=` | Do not modify `timeutil.py`. |
| Equality hidden | `available_at == cutoff` invisible | `test_half_open_equality_still_hidden` + V3 two-clock tests | PASS | Outcome and state clocks must use `<` | Add fundamental two-clock + current-game tests. |
| Observation identity | Deterministic `OBS_{gid}_{compact}_V{state}` | [`observation_id.py`](../roller/state/observation_id.py) | PASS | `db.fundamental` keys off `observation_id` | Keep codec. Time from parsed id, not `InformationSet.cutoff`. |
| Observation firewall | No labels / Y / baseline / residual / F_t | [`assemble_observation`](../roller/state/observation.py); [`greek_leakage.audit_observation_clean`](../roller/validation/greek_leakage.py) | PASS | F_t must stay off `O_t` | Do not add a `FUNDAMENTAL` section. |
| Post-game `home_win` on `O_t` | V1 `mask_results` unmasks after `result_available_at < cutoff` | [`mask_unready_results`](../roller/point_in_time/filters.py); `GAME_STATE.game` may carry results after the game | PASS (V1 behavior) | Current-game exclusion must be by **identity**, not timestamps alone | Preserve V1. Document discrepancy. |
| Candle / PBP availability | `available_at` on each row | PBP `timeActual`; candles close = `available_at` | PASS | State clock for corpus rows | Use PBP `available_at` as `state_available_at`. |
| Derived V3 corpus | Not a public PIT dataset | `derived/v3_response_corpus.csv`; firewalled | PASS | Same pattern for V4A corpus | Do not list in `roller.json` datasets. |
| NBA period | Latest visible PBP `period`; OT ≥ 5 | [`game.py`](../roller/state/game.py) | REAL | `core_v1` identity dim | Config-driven; no hard-coded period map. |
| NBA clock | Remaining ISO `clock`; elapsed derived | [`clock.py`](../roller/state/clock.py): 720s regulation, 300s OT | REAL | Bucket **elapsed**, document remaining raw | Width/edges in `fundamental_conditioning.json`. |
| Score differential | `home − away` | `score_differential_home` from ingest | REAL | Subject = home | Do not invent subject-opponent flip. |
| Home/away identity | On `games.csv` | `home_team_id` / `away_team_id` | REAL | Not a default conditioning dim | Keep off `core_v1`. |
| Terminal winner | `games.home_win` + `result_available_at` | Last **scored** PBP wall time; also `game_state_features` `*_terminal`; `db.labels()` `label_available_only_after` | REAL (NBA ~1352/1362) | Outcome clock is `result_available_at`, **not** `games.available_at` | Ties: both win flags `"0"`; `Y=1` iff `home_win=="1"`. |
| Possession | NBA reconstruct REAL; others NOT_SUPPORTED | V2 possessions | PARTIAL / optional | Must not enter default F_t | Leave off `core_v1`. |
| Pre-game strength | `win_pct_pre` rolling priors | [`team_features`](../roller/features/team_features.py); not F_t | PARTIAL | Optional, off | Do not treat as fundamental probability. |
| Market close | Integer E4 `yes_bid_close` | `MARKET_STATE` | REAL as K | **Excluded** from F_t | K ≠ F. |
| PBP alignment | Latest PBP with `available_at < t` | [`latest_pbp`](../roller/canonical/align.py) | REAL | Corpus construction | Last event per clock bucket. |
| V3 APIs | observation / response / baseline / residual unchanged | [`query.py`](../roller/point_in_time/query.py) | PASS | Consume, do not mutate | Add `fundamental()` only. |
| `db.research` | Stub; no train/OOS | `ResearchNotImplementedError` (V4 wording) | PASS | Keep stub | Retarget text: V4A is `db.fundamental()`. |
| `state_schema_version` | 2.0.0 | `roller.json` | PASS | Do not bump | Add `fundamental_schema_version` separately. |
| `measurement_schema_version` | 3.0.0 | `roller.json` | PASS | Do not bump | Keep. |
| Prerequisite suite | pytest + validate + leakage | 81 passed; validate PASS; leakage PASS | PASS | Stop if this regresses | Proceed to Gate 2 metadata only. |

## Capability matrix (pre-implementation)

| Object | Current data capability | V4A status | Reason |
|--------|-------------------------|------------|--------|
| Period | REAL | usable input | PBP `period` |
| Clock | REAL (remaining ISO → elapsed) | usable input | Bucket elapsed only |
| Score differential | REAL (home − away) | usable input | Home subject |
| Home/Away | REAL | optional, **off** | Identity of Y, not a bucket |
| Terminal winner | REAL (NBA) | usable Y | `home_win` + `result_available_at` |
| Possession | NBA REAL; else NOT_SUPPORTED | optional, **off** | Parsimony |
| Pre-game strength | PARTIAL (`*_pre`) | optional, **off** | Not F_t |
| Market price | REAL (`yes_bid_close` E4) | **excluded** | K ≠ F |
| PBP alignment | REAL | usable | State clock |
| F_t estimator | NOT_YET_IMPLEMENTED | Gate 4 | No provider yet |
| Basis / L2 | SCHEMA_ONLY | out of V4A | Do not implement |

## Discrepancies V4A must record, not invent away

1. Score and Y are **home-oriented**, not generic subject-opponent.
2. Clock is stored as remaining ISO; buckets use elapsed (V2/V3).
3. After the game, `O_t` may contain unmasked `GAME_STATE.game.home_win` (V1). F_t still excludes current `game_id`.
4. Only one NBA season is in the warehouse — `minimum_unique_seasons` must be 1.
5. V3 `conditioning.json` includes market/vol/possession. Do not add dimensions there (would rewrite V3 `condition_id`). Use a separate fundamental config.
6. `db.labels()` terminal `home_win` is future information for the **current** game. F_t uses **other games'** outcomes only.
7. NCAAB terminal scores are sparse. V4A is NBA-only.
8. [`greeks/basis.py`](../roller/greeks/basis.py) remains `NOT_YET_IMPLEMENTED`. Historical win rate is still not a trading F_t / edge.

## Recommended Gate 1 actions

1. Keep V1/V2/V3 tests green.
2. Bump database/pipeline to `4.0.0-A`; keep `state_schema_version` 2.0.0 and `measurement_schema_version` 3.0.0; add `fundamental_schema_version` `4.0.0-A`.
3. Add fundamental registry, definitions, and parsimonious `core_v1` conditioning.
4. Reject `fundamental*` names from `dataset()` with `use db.fundamental()`.
5. Do not start the estimator until corpus eligibility and support tests pass.
