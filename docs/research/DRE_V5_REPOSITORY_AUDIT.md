# DRE V5 — Repository Audit

**Program:** `MOMENTO_DYNAMIC_RISK_ENGINE_V5`  
**Schema:** `1.0.0`  
**Date:** 2026-09-03  
**Live execution:** FALSE

Audit completed before implementation. Paths below were confirmed on disk. No path was invented.

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
FORWARD DISTRIBUTION ≠ TRADABLE EDGE
CONDITIONAL ALPHA ≠ EXECUTABLE ACTION
100-CONTRACT LEDGER ≠ $50 PRODUCTION SIZE
LIVE DEPLOYMENT: NOT AUTHORIZED
```

V5 does **not** write to PADE V1, DRE V2–V4, FIRST01, Risk, live config, frozen FIRST-80 `candidates.json`, hedges, or `fee_models.py`.

---

## Occupied frontend ports (verified)

| Port | App |
|-----:|-----|
| 5173 | research-console |
| 5174 | nba-research-engine-v2 |
| 5176 | first80-hedge-frontier-v2 |
| 5177 | first80-hedge-execution-v3 |
| 5178 | first80-entry-quality-audit-v1 |
| 5179 | first80-unanswered-questions-audit-v2 |
| 5180 | first80-realistic-exit-fee-audit-v1 |
| 5181 | execution-integrity |
| 5182 | first80-multidimensional-exit-hedge-fee-v2 |
| 5183 | pade-v1 |
| 5184 | dre-v2 |
| 5185 | dre-v3 |
| 5186 | dre-v4 |

**DRE V5 dashboard port:** `5187` (next free port).

---

## Frozen FIRST-80

| Item | Path |
|------|------|
| Loader | `apps/ncaab-data/scripts/first80_realistic_exit_fee_audit_v1.py` (`load_frozen("nba")`, `reproduce_path`) |
| Candidates | `Backtesting Suite/Data/NBA/2025-2026/warehouse/derived/nba/first80_execution_audit/candidates.json` |

Expected / last reproduced: **1230 / 910 / 320 / 0**.

Entry remains the frozen 80¢ **candle-path proxy**, not a proven maker fill (`CANDLE_PATH_PROXY_NOT_PROVEN_FILL`).

Unresolved **9 / 1230** stay in universe accounting (never silently dropped). Source: DRE V2 `14_diagnostics/unresolved.json` (`6ce310d8caee86fe`).

---

## PADE V1 (read-only) — Gate B

Root: `Backtesting Suite/Data/NBA/2025-2026/warehouse/derived/nba/possession_adjusted_deterioration_engine_v1/`

| Artifact | sha256[:16] |
|----------|-------------|
| `05_trade_possession_panel.parquet` | `90358b686356cec9` |
| `06_state_features.parquet` | `3faea9b4bb24b5a5` |
| `07_forward_labels.parquet` | `4074b3dace253866` |
| `12_data_leakage_audit.parquet` | `0d0d6f92b355542e` |
| `14_manifest.json` | `4cfa0845821f5e66` |
| `03_possessions.parquet` | `5682d436fa2e2396` |

Panel: **139,966** rows / **1,221** trades / **1,221** games. Splits: TRAIN 503 / VALIDATION 481 / OOS 237 games.

`A2_yes_bid` is present on the PADE panel and is **never null** (0 / 139,966). DRE V4 did not keep A2 on its written panel. V5 reads A2 from PADE.

`current_price` ≡ `A1_yes_bid` (cents). `game_seconds_remaining` increases in **58 / 1,221** trades. Clock bins use **period + elapsed_game_seconds** as the primary constructor; remaining clock is stored but is not the pace constructor.

---

## Lock 6 — Possession grain and prior-pace chronology

### Does one row of `03_possessions.parquet` equal one offensive possession?

**Yes.** Confirmed on disk:

- **252,138** rows / **1,223** `nba_game_id` values.
- `possession_id` unique (0 duplicates).
- `(nba_game_id, possession_index)` unique (0 duplicates).
- `offensive_team` never null.
- Results are possession-ending events: made FG, defensive rebound, turnover, made last FT, period end (5 `period_boundary` rows are flagged `ambiguous_possession_flag`).
- Mean possessions per game: **206.16** (median 206). Mean offensive possessions per team-game: **103.08**.

Therefore the matchup identity is locked:

\[
R_x=\widehat{\mathrm{pace}}_{A1}+\widehat{\mathrm{pace}}_{A2}
\]

where each team pace is that team’s **offensive possessions per completed prior game**. Do not silently switch to a mean of combined-game totals.

`03_possessions.parquet` does **not** carry `game_date`. Game date is joined from the PADE panel / frozen FIRST-80 crosswalk via `nba_game_id`. Sorting a dataframe by `game_date` is **not** the chronology constructor.

### Completed-before-G-start timestamp (audited)

Every possession row has `wall_start_ts` and `wall_end_ts` with `wall_*_source = timeActual` (252,138 / 252,138). Zero null walls.

Locked fields:

| Quantity | Definition |
|----------|------------|
| Game start | `min(wall_start_ts)` over possessions of `nba_game_id` |
| Game completion | `max(wall_end_ts)` over possessions of `nba_game_id` |
| Eligible prior game | `completion_ts < G.start_ts` |

Same calendar day is **not** an automatic include. A same-day game is eligible **only if** its audited `completion_ts` is strictly earlier than `G.start_ts`. If that inequality cannot be proven, the game is excluded.

Observed (panel-dated games): 190 multi-game dates; 2,681 same-day wall-overlap pairs; 1,181 same-day pairs with a strictly earlier completion. Overlapping same-day games are excluded from each other’s pace windows.

`actual_remaining_possessions` is a **label only**. It is never a feature and never a pace input.

Column name for the estimator: `n_hat_remaining_prior`. Never `actual_remaining` or `possessions_remaining`. Language: **prior-informed expected remaining possessions**, not “the number of remaining possessions.”

K=10, min_games=3; else TRAIN league mean of team offensive possessions per game. 352 is an identity illustration, not a hardcoded pace. Empirical combined \(R_x\) is expected near ~206, not 352.

---

## Candle join (Workstream 1b)

| Item | Path / rule |
|------|-------------|
| Candle files | `Backtesting Suite/Data/NBA/2025-2026/warehouse/normalized/nba/candles_1m/*.parquet` (2,724 files) |
| Wall field | `end_period_ts` |
| Bid fields | `yes_bid_*_e4` / 100 → cents (`e4_to_cents`) |
| Loader | `load_ticker_quotes` in `first80_realistic_exit_fee_audit_v1.py` |
| As-of PBP | latest possession with `wall_start_ts` (`timeActual`) **≤** candle `end_period_ts` |
| Window | `first_80_timestamp ≤ ts ≤ game_completion_ts` (in-game post-entry path) |

Never attach a future PBP event. Labels (`future_*`, settle) are stored separately from features.

---

## DRE V4 (read-only) — Gate C predecessor freeze

Root: `.../dynamic_risk_engine_v4/`

| Artifact | sha256[:16] |
|----------|-------------|
| `03_state_panel.parquet` | `2e09b7219e7c9b74` |
| `15_discovery_verdict.json` | `54c8af4bc77acf3f` |
| `01_run_manifest.json` | `eb66b13f519d4606` |
| `NO_OOS_TUNING_AUDIT.json` | `b9f6f71ce9ac8481` |
| `04_universe_accounting.json` | `8cf80641d54aa958` |
| `07_leakage_audit.json` | `fafe5e785497568e` |
| `08_split_audit.json` | `5a587ef816373ea4` |

V2 / V3 hashes remain the V4-era prefixes (untouched):

| Artifact | sha256[:16] |
|----------|-------------|
| V2 `09_predictions/state_predictions.parquet` | `90423de3c8f60d51` |
| V2 `run_manifest.json` | `0dfcb4f13a64dbf6` |
| V3 `04_state_panel.parquet` | `cba09b9410f3ab12` |
| V3 `19_oos_results.json` | `ccdb87f081e0a38a` |
| V3 `20_run_manifest.json` | `b4423b41f720f1ef` |

---

## Forbidden write paths

```
apps/nba-data/scripts/pade_v1.py
apps/nba-data/scripts/pade_v1/
apps/nba-data/scripts/dre_v2.py
apps/nba-data/scripts/dre_v2/
apps/nba-data/scripts/dre_v3.py
apps/nba-data/scripts/dre_v3/
apps/nba-data/scripts/dre_v4.py
apps/nba-data/scripts/dre_v4/
apps/ncaab-data/scripts/first80_realistic_exit_fee_audit_v1.py
apps/nba-data/scripts/first80_multidimensional_exit_hedge_fee_v2.py
apps/nba-data/scripts/nba_80_40_execution_audit.py
apps/nba-data/scripts/capture_program_v1/fee_models.py
.../possession_adjusted_deterioration_engine_v1/
.../dynamic_risk_engine_v2/
.../dynamic_risk_engine_v3/
.../dynamic_risk_engine_v4/
.../first80_execution_audit/
```

---

## Planned output root

```
Backtesting Suite/Data/NBA/2025-2026/warehouse/derived/nba/dynamic_risk_engine_v5/
```

Engine: `apps/nba-data/scripts/dre_v5.py` + `apps/nba-data/scripts/dre_v5/`  
Dashboard: `frontend/dre-v5/` port **5187**  
Reports: `docs/research/MOMENTO_DYNAMIC_RISK_ENGINE_V5.md` and sibling `DRE_V5_*.md`

---

## Six specification locks (written before the first production run)

1. **Weighting.** Primary discovery surface is `TRADE_BALANCED`. Secondary is `STATE_OCCUPANCY_WEIGHTED`. No unlabeled row-weighted mean may be presented as the economic surface.
2. **OOS replication.** Written once before OOS tables. Sign agreement; report `OOS/TRAIN`; ROBUST ratio **[0.5, 2.0]**; game-clustered bootstrap 5–95 compatible with TRAIN direction; VAL confirmation if adequate; INCONCLUSIVE if thin; FAIL if adequate directional reversal. Not “p < 0.05 twice.”
3. **Lambda source.** Scientific OOS \(\Lambda^{\mathrm{path}}= -(\alpha_{\mathrm{TRAIN}}(X_{t+1})-\alpha_{\mathrm{TRAIN}}(X_t))\). Descriptive OOS Lambda uses \(\alpha_{\mathrm{OOS}}\) and is never the scientific verdict.
4. **Binary \(\Pi\).** \(\alpha_{\mathrm{frozen}}=100\,P(Y=1\mid X)-80\). Realized values are only \(\{+20,-80\}\). Quantiles are empirical; **P50 is never hardcoded to 0.** Store `p_settle_yes`.
5. **Verdict B.** M0 (`α ~ P_A1`) vs M1 (`α ~ P_A1 + score + clock + N̂`). Price dominance = no sufficient **reproducible** increment beyond price, not “basketball is irrelevant.”
6. **Pace chronology.** Completed-before-G-start via `wall_end_ts` / `wall_start_ts` (`timeActual`). \(R_x=\widehat{\mathrm{pace}}_{A1}+\widehat{\mathrm{pace}}_{A2}\).

---

## Pre-registered surface spec (before OOS inspection)

| Item | Value |
|------|--------|
| Primary \(\Pi\) | \(100Y-80\) (winner +20 / loser −80). No fees. |
| Secondary \(\Pi\) | \(100Y-P_t\) |
| Diagnostic | 80→40 candle-path framework (`CANDLE_PATH_PROXY`) |
| Primary weighting | TRADE_BALANCED |
| Secondary weighting | STATE_OCCUPANCY_WEIGHTED |
| Display minimum | 50 rows **and** 15 unique trades (not robustness) |
| L1 clock | Q1–Q2 / Q3 / Q4>6 / Q4 2–6 / Q4<2 / OT |
| L1 score | ≥+10, +5–9, +1–4, 0, −1–4, ≤−5 |
| L1 \(\widehat N\) | TRAIN tertiles only |
| L1 A1 | 5¢ bins |
| L2 coarsened | clock {early, late, OT}, score {lead, tie/trail}, \(\widehat N\) {high, low} (TRAIN median), A1 10¢ |
| L2 clock map | EARLY = Q1+Q2+Q3; LATE = Q4; OT separately flagged (not folded into LATE) |
| L3 | \(E[\Pi\mid P_{A1},\mathrm{clock}]\), \(E[\Pi\mid P_{A1},\mathrm{score}]\), \(E[\Pi\mid P_{A1},\widehat N]\) |
| Primary L3 contrasts | `[60,65)` ¢ early vs late (OT excluded); lead vs trail; high vs low \(\widehat N\) |
| M0 / M1 | TRAIN cell means; trade-level \(\hat\alpha_i=\mathrm{mean}_t\hat\alpha_{\mathrm{TRAIN}}(X_{it})\); occupancy MAE is diagnostic |
| M1 beats M0 | \(\Delta\mathrm{MAE}\ge 0.5\)¢ **and** bootstrap interval of \(\Delta\mathrm{MAE}\) entirely above 0 |
| OOS ROBUST ratio | \([0.5, 2.0]\) — frozen; do not change after seeing results |
| Bootstrap | 200 game-clustered resamples, seed 42 |
| Hazard at-risk | running min so far \(> 40\) cents |
| Inventory | Q=100, \(V^{\mathrm{mtm}}_{\mathrm{cents}}=100\times P_{A1,\mathrm{cents}}\), \(\Delta^{\mathrm{inv}}=100\). Not possessions. |
| Market columns | `A1_yes_bid_cents`, `A2_yes_bid_cents`, `current_price_cents`, `entry_price_cents`, `V_mtm_cents` |
| 40-framework | Diagnostic `CANDLE_PATH_PROXY` only. Forbidden in headline \(\alpha\), scientific Lambda, primary gradient, M0/M1, verdict. |

---

## Checkpoint freeze (before Greeks / runner / dashboard)

Applied so `surfaces.py` cannot silently redefine the estimand:

1. \(V^{\mathrm{mtm}}_{\mathrm{cents}}=100\times P_{A1,\mathrm{cents}}\). \(\Delta^{\mathrm{inv}}=100\).
2. Quantiles of \(\Pi_{\mathrm{terminal}}\) are empirical. A realized 0 never occurs.
3. All market coordinates are **cents per contract** on \([0,100]\). Threshold is \(P\le 40\) cents.
4. OOS protocol is the single object in `config.OOS_REPLICATION_PROTOCOL`. Ratio band **[0.5, 2.0]**. M1 rule: \(\Delta\mathrm{MAE}\ge 0.5\)¢ and bootstrap interval of \(\Delta\mathrm{MAE}\) entirely above 0.
5. Primary M0/M1 MAE is trade-balanced: \(\hat\alpha_i=\frac{1}{T_i}\sum_t\hat\alpha_{\mathrm{TRAIN}}(X_{it})\). Occupancy MAE is labeled diagnostic.
6. Scientific OOS Lambda uses TRAIN-frozen \(\alpha\) only.
7. L2 clock: EARLY = Q1+Q2+Q3; LATE = Q4; OT flagged separately.
8. `n_hat_remaining_prior=\max(0,R_x-\mathrm{possession\_index})` is not a predicted possession index.

Claims require Level 2 or 3 **OOS** persistence. TRAIN interestingness is not a discovery.

---

## Library availability

`pandas` / `pyarrow` / `numpy`. `sklearn` is **not** required for V5 (no ML). Game-clustered bootstrap is implemented in-engine.

---

## First frozen run (2026-09-03, one shot)

Sequence observed: SPECIFICATION_LOCKS + OOS_REPLICATION_PROTOCOL + NO_OOS_TUNING_AUDIT written at **21:53:25Z**, then TRAIN → VAL → OOS → verdict. Manifest `created_utc` **21:56:06Z**. Elapsed **161.1s**. `protocol_written_before_oos=true`.

Gates **A–I = PASS**. Predecessor PADE / V2 / V3 / V4 hashes unchanged after the run.

| Protocol object | OOS result |
|-----------------|------------|
| `L3_clock_early_late_60` | **FAIL** (sign reversal; adequate) |
| `L3_score_lead_trail_60` | **PARTIAL** (sign match; ratio 0.271 outside [0.5, 2.0]) |
| `L3_nhat_high_low_60` | **FAIL** (sign reversal; adequate) |
| M1 beats M0 | **False** (ΔMAE 0.429¢ < 0.5¢; bootstrap 5–95 of ΔMAE is (0.210, 0.695), entirely above 0, but the material threshold fails) |

Headline **B** (price dominates). Flag D is also true (no ROBUST L2/L3 contrast). Priority A > C > B > D therefore reports **B**. Scientific OOS Lambda (TRAIN-frozen α, OOS paths) trade-balanced mean **−0.218**. Descriptive OOS Lambda is not a verdict input.

This addendum records the frozen first inspection. It does **not** authorize retuning bins, contrasts, the ratio band, the 0.5¢ M1 threshold, weighting, the primary payoff, or the Lambda lookup hierarchy.

**LIVE DEPLOYMENT: NOT AUTHORIZED**
