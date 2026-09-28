# DRE V6 — Repository Audit

**Program:** `MOMENTO_DYNAMIC_RISK_ENGINE_V6`  
**Schema:** `1.0.0`  
**Date:** 2026-09-03  
**Live execution:** FALSE

Audit completed **before** V6 implementation and **before** any V6 OOS table. Paths confirmed on disk. No path invented. No V6 OOS result was inspected (none exists yet).

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
FORWARD DISTRIBUTION ≠ TRADABLE EDGE
CONDITIONAL ALPHA ≠ EXECUTABLE ACTION
Δα_state ≠ EDGE
100-CONTRACT LEDGER ≠ $50 PRODUCTION SIZE
LIVE DEPLOYMENT: NOT AUTHORIZED
```

V6 does **not** write to PADE V1, DRE V2–V5, FIRST01, Risk, live config, frozen FIRST-80 `candidates.json`, hedges, or `fee_models.py`.

V5 Verdict B is historical and immutable.

```
V5 RESULT = UNTOUCHED
V6 = NEW QUESTION
THE IMPLEMENTATION IS NOT PERMITTED TO DISCOVER ITS OWN SCIENCE
ONLY verdict.py CLASSIFIES A/B/C/D
```

---

## Occupied frontend ports (verified)

| Port | App |
|-----:|-----|
| 5173–5186 | prior research dashboards |
| 5187 | dre-v5 |

**DRE V6 dashboard port:** `5188`.

---

## 1. Exact V5 source paths

| Object | Path |
|--------|------|
| Package | `apps/nba-data/scripts/dre_v5/` |
| Entrypoint | `apps/nba-data/scripts/dre_v5.py` → `dre_v5/run.py` |
| Config | `apps/nba-data/scripts/dre_v5/config.py` |
| Surfaces / `m0_m1` | `apps/nba-data/scripts/dre_v5/surfaces.py` |
| Panel | `apps/nba-data/scripts/dre_v5/state_panel.py` |
| Priors | `apps/nba-data/scripts/dre_v5/possession_remaining.py` |
| Candles | `apps/nba-data/scripts/dre_v5/candle_ledger.py` |
| Splits | `apps/nba-data/scripts/dre_v5/splits.py` |
| Universe | `apps/nba-data/scripts/dre_v5/frozen_universe.py` |
| Integrity | `apps/nba-data/scripts/dre_v5/integrity.py` |
| V5 output | `Backtesting Suite/Data/NBA/2025-2026/warehouse/derived/nba/dynamic_risk_engine_v5/` |
| PADE | `.../possession_adjusted_deterioration_engine_v1/` |
| FIRST-80 loader | `apps/ncaab-data/scripts/first80_realistic_exit_fee_audit_v1.py` |

---

## 2. `build_priors` signature

File: `apps/nba-data/scripts/dre_v5/possession_remaining.py`

```
def build_priors(poss: pd.DataFrame, panel: pd.DataFrame) -> tuple[pd.DataFrame, dict]
```

- `poss`: `03_possessions.parquet` (one row = one offensive possession).
- `panel`: PADE `05_trade_possession_panel.parquet` columns `trade_id, nba_game_id, dataset_split, game_date, A1_team, A2_team`.
- Returns `(priors_df, pace_audit)`.
- Chronology: `COMPLETED_BEFORE_G_START_WALL_END_TS`. \(R_x=\widehat{\mathrm{pace}}_{A1}+\widehat{\mathrm{pace}}_{A2}\).
- Helper: `attach_n_hat(panel, priors) -> DataFrame`.

---

## 3. `build_panel` signature

File: `apps/nba-data/scripts/dre_v5/state_panel.py`

```
def build_panel(priors: pd.DataFrame) -> pd.DataFrame
```

Reads PADE `05_trade_possession_panel.parquet` internally (`PADE_KEEP`). Attaches `n_hat_remaining_prior` via `attach_n_hat`. Constructs cents prices, \(\Pi_{\mathrm{terminal}}=100Y-80\), L1/L2 bins. **TRAIN tertiles** of `n_hat_remaining_prior` are computed from `dataset_split==TRAIN` only and stored on `df.attrs["n_hat_tertiles_train"]`. Expected **139,966** rows.

Related: `panel_counts(df)`, `universe_accounting(df, gate_a)`.

---

## 4. `m0_m1` signature and returned structure

File: `apps/nba-data/scripts/dre_v5/surfaces.py`

```
def m0_m1(df: pd.DataFrame) -> dict
```

Fits **TRAIN only**:

- `m0[price_bin_5] = TRADE_BALANCED mean(pi_terminal)`
- `m1[(price_bin_5, score_bin_l1, clock_bin_l1, n_hat_bin_l1)] = TRADE_BALANCED mean(pi_terminal)`
- `global_mean = mean over TRAIN trades of mean_t pi_terminal`
- Fallback: missing M1 → M0(price) → `global_mean`

Returned keys: `by_split` (TRAIN/VALIDATION/OOS MAE), `bootstrap_oos_delta_mae`, `m1_beats_m0`, `n_m0_cells`, `n_m1_cells`, `lookup: {m0, m1, global_mean}`.

V5 stripped `lookup` before JSON. V6 recovers it once, identity-checks published MAE, persists under the V6 tree only.

**Published identity (must match; relative 1e-9 / abs 1e-12; cell counts exact):**

```
OOS MAE M0 = 20.55697546313149
OOS MAE M1 = 20.12797948988682
ΔMAE       = 0.4289959732446711
n_m0_cells = 20
n_m1_cells = 584
```

Do **not** use `train_lookup_maps()` (L2/L3 Lambda surfaces).

---

## 5. `build_candle_ledger` signature

File: `apps/nba-data/scripts/dre_v5/candle_ledger.py`

```
def build_candle_ledger(trades: list[dict], poss: pd.DataFrame, priors: pd.DataFrame | None) -> pd.DataFrame
```

`trades` from `frozen_universe.gate_a()["trades"]` (enriched FIRST-80). In-game post-entry candles; as-of PBP `wall_start_ts ≤ candle ts`. `fill_status=CANDLE_PATH_PROXY_NOT_PROVEN_FILL`. Diagnostic only for V6 path separation.

---

## 6. V5 split construction

V6 does **not** rebuild splits. `dataset_split` is inherited from the PADE panel / FIRST-80 chronology.

`dre_v5/splits.py` `audit_splits(df)`:

- Game-level isolation: one `event_id` → one split (overlap → FAIL).
- Expected games: TRAIN **503** / VALIDATION **481** / OOS **237**.
- Expected trades: 503 / 481 / 237 (one logical trade per game on the panel).

`n_hat` L1 tertiles and L2 median are TRAIN-only (`state_panel.build_panel`).

---

## 7. V5 output files (confirmed after the one-shot V5 run)

JSON/MD present under `.../dynamic_risk_engine_v5/`:

`SPECIFICATION_LOCKS.json`, `OOS_REPLICATION_PROTOCOL.json`, `NO_OOS_TUNING_AUDIT.json`, `01_trade_ledger.json`, `07_leakage.json`, `08_splits.json`, `09_alpha_surface.json`, `10_hazard_surface.json`, `11_empirical_greeks.json`, `12_universe_accounting.json`, `13_run_manifest.json`, `14_dashboard.json`, `15_discovery_verdict.json`, `pace_audit.json`, plus copied reports.

`13_run_manifest.json`: `headline=B`, `protocol_written_before_oos=true`.

Panel parquets may be absent from the listing. V6 rebuilds the panel **in memory** and must **not** write parquets back into the V5 tree. Gate G hashes the **complete** V5 tree before and after the V6 run.

---

## 8. Predecessor hash sources

| Layer | Source of sha256[:16] |
|-------|------------------------|
| PADE | Frozen in `dre_v5/config.py` `PADE_SHA256_PREFIX` (V5 Gate B) |
| V4 | Frozen in `dre_v5/config.py` `V4_SHA256_PREFIX` (V5 Gate C) |
| V2 / V3 | V4-era prefixes recorded in `docs/research/DRE_V5_REPOSITORY_AUDIT.md` (not a V5 config dict). V6 copies those exact prefixes. |

---

## 9. Unresolved V2 / V3 hash provenance

V5 `config.py` does **not** contain V2/V3 hash dictionaries. The prefixes V6 uses are the V4-era values documented in the V5 repository audit:

| Artifact | sha256[:16] | Provenance |
|----------|-------------|------------|
| V2 `09_predictions/state_predictions.parquet` | `90423de3c8f60d51` | `DRE_V5_REPOSITORY_AUDIT.md` “V2 / V3 hashes remain the V4-era prefixes” |
| V2 `run_manifest.json` | `0dfcb4f13a64dbf6` | same |
| V3 `04_state_panel.parquet` | `cba09b9410f3ab12` | same |
| V3 `19_oos_results.json` | `ccdb87f081e0a38a` | same |
| V3 `20_run_manifest.json` | `b4423b41f720f1ef` | same |

V6 does not invent new predecessor hashes.

Unresolved FIRST-80 trades: V2 `14_diagnostics/unresolved.json` (`6ce310d8caee86fe` in the V5 audit). Universe remains 1230; 9 unresolved stay.

---

## 10. Exact import paths required by V6

From `apps/nba-data/scripts/` on `sys.path`:

```
dre_v5.config
dre_v5.surfaces.m0_m1
dre_v5.state_panel.build_panel, panel_counts
dre_v5.possession_remaining.build_priors
dre_v5.candle_ledger.build_candle_ledger
dre_v5.frozen_universe.gate_a
dre_v5.splits.audit_splits
```

V6 writes only to:

- `apps/nba-data/scripts/dre_v6/`
- `apps/nba-data/scripts/dre_v6.py`
- `.../dynamic_risk_engine_v6/`
- `docs/research/DRE_V6_*.md`, `MOMENTO_DYNAMIC_RISK_ENGINE_V6.md`
- `frontend/dre-v6/`

---

## Frozen scientific object

\[
\overline{\Delta\alpha}_i=\frac{1}{T_i}\sum_t[\alpha_{M1,\mathrm{TRAIN}}(P_{it},X_{it})-\alpha_{M0,\mathrm{TRAIN}}(P_{it})]
\]

\[
\bar R_i=\Pi_i-\frac{1}{T_i}\sum_t\alpha_{M0,\mathrm{TRAIN}}(P_{it})
\]

Primary: \(\overline{\Delta\alpha}_i \longrightarrow \bar R_i\) (TRADE_BALANCED). Row-level is `STATE_OCCUPANCY_WEIGHTED DIAGNOSTIC`.

Decile convention (frozen before analysis): TRAIN `qcut` 10 bins; HALT if not exactly 10 distinct bins. VAL/OOS use persisted TRAIN edges. **Outside TRAIN range:** \(\overline{\Delta\alpha} < e_0\) → decile 1; \(\overline{\Delta\alpha} > e_{10}\) → decile 10 (`CLIP_TO_TRAIN_EXTREMA`). Interior: `pd.cut(..., include_lowest=True, right=True)`.

If A/B/C/D none fire: HALT `UNCLASSIFIED_PRE_REGISTERED_OUTCOME`. Do not silently call it A.

**LIVE DEPLOYMENT: NOT AUTHORIZED**
