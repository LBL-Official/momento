# DRE V4 — Repository Audit

**Program:** `MOMENTO_DYNAMIC_RISK_ENGINE_V4`  
**Date:** 2026-09-03  
**Live execution:** FALSE

Audit completed before implementation. Paths below were confirmed on disk. No path was invented.

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
FORWARD DISTRIBUTION ≠ TRADABLE EDGE
```

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
| 5180 | first80-realistic-exit-fee-audit-v1 (a1-hybrid-hedge also declares 5180) |
| 5181 | execution-integrity |
| 5182 | first80-multidimensional-exit-hedge-fee-v2 |
| 5183 | pade-v1 |
| 5184 | dre-v2 |
| 5185 | dre-v3 |

**DRE V4 dashboard port:** `5186` (next free port).

---

## Frozen FIRST-80

| Item | Path |
|------|------|
| Loader | `apps/ncaab-data/scripts/first80_realistic_exit_fee_audit_v1.py` (`load_frozen("nba")`, `reproduce_path`) |
| Candidates | `Backtesting Suite/Data/NBA/2025-2026/warehouse/derived/nba/first80_execution_audit/candidates.json` |

Expected / last reproduced: **1230 / 910 / 320 / 0**.

---

## PADE V1 (read-only)

Root: `Backtesting Suite/Data/NBA/2025-2026/warehouse/derived/nba/possession_adjusted_deterioration_engine_v1/`

| Artifact | sha256[:16] |
|----------|-------------|
| `05_trade_possession_panel.parquet` | `90358b686356cec9` |
| `06_state_features.parquet` | `3faea9b4bb24b5a5` |
| `07_forward_labels.parquet` | `4074b3dace253866` |
| `12_data_leakage_audit.parquet` | `0d0d6f92b355542e` |
| `14_manifest.json` | `4cfa0845821f5e66` |

Panel: **139,966** rows / **1,221** trades. Alignment on panel: HIGH 139,625 / MEDIUM 341. `current_price` ≡ `A1_yes_bid` (cents). `A1_yes_ask` present, never null on panel.

**Reused as-of fields:** trade/event ids, `dataset_split`, `game_date`, three clocks (`market_observation_timestamp` / `position_age_wall_s`, `game_clock` / `game_seconds_remaining` / `elapsed_game_seconds`, `possession_index` / `possessions_since_entry`), score, offense flag, market age, alignment, unique market observations, velocity / acceleration / volatility, estimated remaining possessions (R1–R3), bid/ask, deterioration, existing forward min/max/recovery/deterioration/jump labels.

**Not reused as features:** `actual_remaining_possessions`, any `future_*`, any `y_*`, `terminal_pnl_hold`.

**Clock-horizon note:** `game_seconds_remaining` *increases* in 58/1221 trades (OT / period encoding). `elapsed_game_seconds` is monotonic (0 decreases). Clock-horizon labels will be built from **elapsed game seconds**, not remaining clock. Documented, not invented remaining-clock paths.

---

## DRE V2 (read-only)

Root: `.../dynamic_risk_engine_v2/`

| Artifact | sha256[:16] |
|----------|-------------|
| `03_state_panel/dre_state_panel.parquet` | `de42b6593ac6dbb0` |
| `09_predictions/state_predictions.parquet` | `90423de3c8f60d51` |
| `08_models/model_metrics.parquet` | `395360a2cf53a91f` |
| `run_manifest.json` | `0dfcb4f13a64dbf6` |
| `11_exposure_surfaces/oos_policy_score.json` | `d872ef25c61aa149` |

**Reused:** `p_settle_M3` / `p_rec10_k5_M3` / `p_det10_end_M3` as *comparison probabilities only*; `real_time_timestamp`; unique-observation / spread fields; unresolved list.

**Explicitly not reused as V4 targets:** `target_delta_*`, `ev_hold_*`, regime clusters as optimization labels.

Unresolved (preserved): **9 / 1230** — 7 unmatched, 2 matched-but-no-panel (`KXNBAGAME-25DEC04LALTOR`, `KXNBAGAME-26JAN24BOSCHI`).

---

## DRE V3 (read-only)

Root: `.../dynamic_risk_engine_v3/`

| Artifact | sha256[:16] |
|----------|-------------|
| `04_state_panel.parquet` | `cba09b9410f3ab12` |
| `19_oos_results.json` | `ccdb87f081e0a38a` |
| `20_run_manifest.json` | `b4423b41f720f1ef` |
| `13_interior_solution_analysis.json` | *(integrity existence + hash at run)* |

**Context only:** V3 negative result (narrow ~8% interior `h*`; same-price settlement asymmetry did not become exposure asymmetry).

**Not reused as dependent variables:** `h_N1`–`h_N4`, utility parameters, CRRA/CARA, objective grids.

---

## Forbidden write paths

```
apps/nba-data/scripts/pade_v1.py
apps/nba-data/scripts/pade_v1/
apps/nba-data/scripts/dre_v2.py
apps/nba-data/scripts/dre_v2/
apps/nba-data/scripts/dre_v3.py
apps/nba-data/scripts/dre_v3/
apps/ncaab-data/scripts/first80_realistic_exit_fee_audit_v1.py
apps/nba-data/scripts/first80_multidimensional_exit_hedge_fee_v2.py
apps/nba-data/scripts/nba_80_40_execution_audit.py
apps/nba-data/scripts/capture_program_v1/fee_models.py
.../possession_adjusted_deterioration_engine_v1/
.../dynamic_risk_engine_v2/
.../dynamic_risk_engine_v3/
.../first80_execution_audit/
```

---

## Planned output root

```
Backtesting Suite/Data/NBA/2025-2026/warehouse/derived/nba/dynamic_risk_engine_v4/
```

Engine: `apps/nba-data/scripts/dre_v4.py` + `apps/nba-data/scripts/dre_v4/`  
Dashboard: `frontend/dre-v4/` port **5186**  
Reports: `docs/research/MOMENTO_DYNAMIC_RISK_ENGINE_V4.md` and sibling DRE_V4_*.md

---

## Pre-registered primary specification (before OOS inspection)

| Item | Value |
|------|--------|
| Price matching | 5¢ bins, `floor(price/5)*5` |
| Primary band | `[60, 65)` |
| Primary slice | early (`period<=2` or `elapsed<1440`) vs late (`period>=4` and `game_seconds_remaining<=360`) |
| Primary horizon | 5 possessions |
| Primary objects | DD, UE, P(rec≥10), P(det≥10), P(settle), path class |
| Min sample | 50 rows and 15 unique trades |
| Robustness widths | 2¢, 10¢, nearest-neighbor ±1¢ |
| Nested models | B0→B1→B2→M3→M4→M5; TRAIN fit; no OOS selection |
| Negative control | `y_min_le_40_k5` (price-saturated short-horizon) |

---

## Library availability

`scipy 1.18.1` (Wasserstein, KS, energy distance). `sklearn` logistic / multinomial / `HistGradientBoostingRegressor` quantile loss.
