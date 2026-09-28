# MOMENTO — Dynamic Risk Engine V2

**Program:** `MOMENTO_DYNAMIC_RISK_ENGINE_V2`  
**Short name:** `DRE_V2`  
**Schema:** 1.0.0  
**Date:** 2026-09-03  
**Live execution changed:** FALSE  
**NCAAB:** not implemented (no joinable PBP)

```
RESEARCH ONLY — CANDLE PATH ≠ ACTUAL FILL — THEORETICAL TARGET DELTA ≠ EXECUTED DELTA — THEORETICAL EXPOSURE ≠ ACTUAL EXECUTION — LIVE DEPLOYMENT: NOT AUTHORIZED
```

---

## 1. Program definition

DRE V2 is an **offline research engine**. It estimates state-conditional future distributions of downside, recovery, and terminal outcome, then derives a **theoretical target delta**: the fraction of original directional exposure the model would *want* to retain given current state `X_n`.

It does **not** answer “what stop price should we use?”

Central question:

> Given the current state, what is the conditional value and conditional risk of retaining directional exposure?

---

## 2. Scope boundaries

DRE V2 is **not**:

- a live trading system
- a stop-loss optimizer
- a new FIRST-80 universe
- an execution engine, fill simulator, or hedge engine
- a modification to FIRST01, Risk, or PADE V1
- authorization for live deployment

PADE V1 is frozen. DRE consumes it. DRE does not overwrite PADE outputs or possession boundaries.

---

## 3. Upstream PADE dependencies

Read-only root:

`Backtesting Suite/Data/NBA/2025-2026/warehouse/derived/nba/possession_adjusted_deterioration_engine_v1/`

| PADE artifact | Role |
|---------------|------|
| `05_trade_possession_panel.parquet` | Trade × possession as-of state + labels |
| Frozen FIRST-80 loader | Universe gate |
| Remaining-possession R2 | ESTIMATE only (known bias) |

PADE scientific inputs treated as evidence, not re-litigated:

- Time alignment **PASS**
- Possession engine **PASS**
- Leakage **PASS**
- Possession predictive value **INCONCLUSIVE**
- Remaining possessions **WARNING**
- Execution **UNOBSERVED**
- `P(min≤40 within 5 poss)` is **saturated** (B0 AUC ≈ 0.99). It is a **control**, not the DRE headline.

---

## 4. Multi-clock architecture

Three clocks are stored separately and remain queryable:

| Clock | Field | Meaning |
|-------|--------|---------|
| Real time | `real_time_timestamp` | `entry_timestamp + position_age_wall_s` from observed PADE walls |
| Game clock | `game_clock`, `game_seconds_remaining`, `period` | Basketball position |
| Possession time | `possession_index`, `possessions_since_entry` | Discrete state transitions |

Also preserved: `market_age_seconds`. Repeated identical as-of candles are **not** independent market updates. Unique-observation counts and validity flags distinguish possession progression from market-observation progression.

`Possession Time ≠ Game Clock ≠ Real Time`.

---

## 5. State-vector definition

At each eligible PADE possession-state `n`, `X_n` contains only information available then.

Groups: position (entry/current/deterioration, YES side, 80¢ notional proxy), market (bid/ask/spread/age/alignment/unique observations/price changes), deterioration path (current, max-to-date, recovery from max DD, distance from entry/peak), velocity/acceleration **with validity flags** (null is not zero), game state, possession state, temporal clocks.

`estimated_remaining_possessions` is labeled `ESTIMATE_BIASED` / `PADE_V1_R2`.  
`actual_remaining_possessions` is **evaluation-only**.

---

## 6. Leakage rules

Every feature was asked: *could this have been known at state n?*

| Gate | Status | Count |
|------|--------|------:|
| C market lookahead | **PASS** | 0 future candles as features |
| D game lookahead | **PASS** | 0 future PBP as features |

Forbidden as features: future min/max/path, settlement, actual remaining possessions, terminal hold P&L. Artifact: `05_leakage_audit/LEAKAGE_AUDIT.json`.

---

## 7. Forward distributions

Competing objects, not one “danger” probability:

- **A Downside:** `P(FutureMin ≤ L | X, H)` and `P(FutureDet ≥ D | X, H)` for H ∈ {1,3,5,10,end} and L ∈ {70,60,50,40,30}
- **B Recovery:** `P(FutureMax ≥ current + R)` for R ∈ {5,10,20}¢
- **C Terminal:** `P(Settle YES | X_n)` — primary DRE target
- **D Jump proxy:** `y_jump_40` is an **observed one-minute candle-path proxy**. It is **not** “actual jump execution failure” and **not** a fill.

---

## 8. Nested models

| Family | Layer | Features |
|--------|-------|----------|
| B0 | Market price only | current, entry, deterioration |
| B1 | + wall age | + `market_age_seconds`, `position_age_wall_s` |
| B2 | + game state | + period, game clock, score, possession team |
| M3 | Multi-clock | + possession index/since-entry + R2 estimate |
| M3_NO_REM | Ablation | M3 without remaining-possession estimate |
| M4 | Path state | + max DD, recovery from max DD, distances |
| M5 | Dynamic | + valid velocity/acceleration/unique-obs structure |

Estimator (frozen a priori, **not** tuned on OOS): `StandardScaler + LogisticRegression(C=1.0, class_weight=balanced, seed=42)`.

Complete-case exclusions are recorded per family/target/split. Rows are not silently dropped.

### OOS metrics (primary targets)

| Target | B0 AUC | B1 AUC | B2 AUC | M3 AUC | M4 AUC | M5 AUC | B0 Brier | B1 Brier | B2 Brier | M3 Brier | M4 Brier | M5 Brier |
|--------|-------:|-------:|-------:|-------:|-------:|-------:|-------:|-------:|-------:|-------:|-------:|-------:|
| `y_settle_yes` | 0.843 | 0.842 | 0.847 | 0.861 | 0.853 | 0.845 | 0.160 | 0.163 | 0.161 | 0.157 | 0.157 | 0.159 |
| `y_rec_ge_10_k5` | 0.852 | 0.849 | 0.884 | 0.887 | 0.890 | 0.891 | 0.158 | 0.160 | 0.132 | 0.132 | 0.127 | 0.126 |
| `y_rec_ge_10_end` | 0.869 | 0.863 | 0.858 | 0.875 | 0.895 | 0.895 | 0.198 | 0.189 | 0.155 | 0.144 | 0.125 | 0.126 |
| `y_det_ge_10_k5` | 0.796 | 0.790 | 0.850 | 0.852 | 0.858 | 0.858 | 0.187 | 0.189 | 0.156 | 0.155 | 0.152 | 0.151 |
| `y_det_ge_10_end` | 0.810 | 0.786 | 0.802 | 0.803 | 0.807 | 0.807 | 0.206 | 0.206 | 0.183 | 0.182 | 0.178 | 0.178 |
| `y_min_le_50_k5` | 0.988 | 0.988 | 0.993 | 0.992 | 0.992 | 0.992 | 0.037 | 0.037 | 0.031 | 0.030 | 0.030 | 0.030 |
| `y_jump_40` | 0.832 | 0.814 | 0.784 | 0.780 | 0.790 | 0.790 | 0.196 | 0.199 | 0.193 | 0.187 | 0.181 | 0.181 |

### Saturated control (not the research target)

| Target | B0 AUC | B1 AUC | B2 AUC | M3 AUC | M4 AUC | M5 AUC | B0 Brier | B1 Brier | B2 Brier | M3 Brier | M4 Brier | M5 Brier |
|--------|-------:|-------:|-------:|-------:|-------:|-------:|-------:|-------:|-------:|-------:|-------:|-------:|
| `y_min_le_40_k5` | 0.990 | 0.990 | 0.995 | 0.994 | 0.994 | 0.994 | 0.036 | 0.036 | 0.029 | 0.028 | 0.029 | 0.029 |

---

## 9. OOS methodology

- Splits are **game-level** and chronological: TRAIN `game_date ≤ 2025-12-31`, VALIDATION `≤ 2026-03-15`, OOS after.
- A game appears in exactly one split. GATE E: **PASS**. TRAIN games=503 VAL=481 OOS=237.
- Models fit on TRAIN only.
- Objective-function lambdas selected on **VALIDATION only**, then frozen.
- OOS is evaluation. GATE H: **PASS**.

---

## 10. Downside findings

Incremental OOS AUC vs B0:

- M3 `y_det_ge_10_end`: `-0.008`
- B2/M3/M5 on `y_det_ge_10_k5` — see model lab.

PADE already showed game clock (B2) is the first large lift on short-horizon deterioration. DRE treats this as input evidence and asks whether that lift changes **exposure desire**, not whether it beats a 40-cent stop.

The saturated control `y_min_le_40_k5` remains price-dominated (B0 OOS AUC `0.990`). That is expected. It is not a DRE success metric.

---

## 11. Recovery findings

Incremental OOS AUC vs B0:

- M3 `y_rec_ge_10_k5`: `0.035`
- M5 `y_rec_ge_10_k5`: `0.039`
- B2 `y_rec_ge_10_k5`: `0.032`

Recovery is one of the scientifically useful non-saturated targets. Dynamic state (M5) is evaluated only on complete-case rows with valid unique-observation velocity — exclusions are documented.

---

## 12. Settlement findings

Primary terminal object `P(Settle YES | X_n)`.

Incremental OOS AUC vs B0:

- M3: `0.018`
- M5: `0.002`
- M3_NO_REM: `0.015`

Remaining-possessions ablation (settlement OOS): **INCONCLUSIVE**. The R2 estimate is not revised in this experiment.

---

## 13. Exposure asymmetry

Question: do states with the **same current price** have different terminal / recovery / downside distributions once game clock, score, and possession differ?

OOS asymmetry declared: **TRUE**

Notes:

- OOS price≈60 early vs late P(settle) gap=0.425

Full contrast tables: `docs/research/EXPOSURE_ASYMMETRY_REPORT.md`.

---

## 14. Remaining-alpha methodology

Exploratory theoretical objects. **Not realized alpha. Not tradable.**

For a YES position with candle-proxy entry 80¢:

| Object | Formula | Basis |
|--------|---------|--------|
| Market-implied proxy | `current_price / 100` | As-of yes-bid candle, not a fill |
| Model terminal probability | model P(YES given X_n) from nested logits | TRAIN-fit, split-scored |
| `terminal_probability_edge` | model P(YES) minus current_price/100 | Exploratory |
| `EV_hold_mtm` | `100·P(YES) − current_price` | Mark-to-market vs current bid **proxy** |
| `EV_hold_from_entry` | `100·P(YES) − 80` | Entry accounting; do not mix with MTM |

These assume settlement 100/0 and ignore fees, spreads at exit, and fills.

---

## 15. Exposure-value surface

`h ∈ {0.00, 0.10, …, 1.00}` is the **desired theoretical exposure fraction**.

- `h = 1` → retain 100% of original directional exposure
- `h = 0` → retain zero

No fill is invented. The surface is computed from model probabilities × the modular objective. Label: **THEORETICAL — NOT EXECUTION**.

---

## 16. Target-delta methodology

`theoretical_target_delta` = `argmax_h` of a stated objective on the discrete grid.

Families A/B/C are linear in h, so theoretical_target_delta is typically a corner {0, 1}. Family D adds a concave regularizer so interior h can appear. Neither is a live policy. THEORETICAL TARGET DELTA ≠ EXECUTED DELTA.

Primary exposure model for the surface: **M3** (more complete-case than M5). M5 is a nested increment, not the default h* engine. B0 h* is retained for disagreement analysis.

---

## 17. Objective-function sensitivity

Lambdas selected on VALIDATION only (`oos_used=false`).

| Family | λ_D | λ_R | γ | VAL score |
|--------|----:|----:|--:|----------:|
| A EV only | 0 | 0 | 0 | (no hyperparameter) |
| B downside-penalized | 0.00 | 0 | 0 | 0.345 |
| C path-aware | 0.00 | 10.00 | 0 | 0.457 |
| D concave regularizer | 0 | 0 | 0.00 | 0.345 |

OOS theoretical score (`h ×` candle-settlement continuation vs current bid; **not** fill P&L):

| Family | n | mean h | frac h=1 | frac interior | mean h×continuation ¢ |
|--------|--:|-------:|---------:|--------------:|----------------------:|
| A | 26948 | 0.013 | 0.013 | 0.000 | 0.172 |
| B | 26948 | 0.013 | 0.013 | 0.000 | 0.172 |
| C | 26948 | 0.026 | 0.026 | 0.000 | 0.461 |
| D | 26948 | 0.013 | 0.013 | 0.000 | 0.172 |

B0 vs M3 Family-A disagreement: n=26948 frac=0.008

---

## 18. Regime findings

SAFE / DANGER / ACUTE were **not** hard-coded as truth.

Interpretable buckets: price, deterioration, period, score differential. Optional KMeans (k=5) fit on TRAIN only (price, deterioration, remaining game clock, score differential, possessions since entry); VAL/OOS transformed without refit. Status: **FIT_TRAIN_ONLY**.

The goal is whether economically different exposure regimes exist at similar prices — see the asymmetry report — not whether clusters look impressive.

---

## 19. Execution limitations

1. One-minute candles. Many possessions share one stale print.
2. No L2. No IOC. No maker fill tape.
3. `y_jump_*` is a candle-path **proxy**.
4. Seven unmatched FIRST-80 events have no NBA game ID; additional matched-but-no-panel trades remain unresolved.
5. Remaining-possession R2 is biased (~30 possessions in PADE). Not a deterministic clock.
6. Theoretical `h` is not achievable just because it is computed.
7. Settlement 100/0 accounting ignores fees and exit microstructure.

```
CANDLE PATH ≠ ACTUAL FILL
THEORETICAL TARGET DELTA ≠ EXECUTED DELTA
THEORETICAL EXPOSURE ≠ ACTUAL EXECUTION
```

---

## 20. Evidence grades

| Claim | Grade |
|-------|-------|
| Frozen universe reproduction | **A** (gate) |
| PADE as-of panel consumed unchanged | **A** |
| No-lookahead feature audit | **A** (structural) |
| Nested logistic AUC/Brier | **C** |
| Remaining-possession R2 as feature | **B** (biased estimate) |
| Jump-through | **B** candle proxy, **not** a fill |
| Theoretical target delta | **C** (research object) |
| Live / IOC / maker fill | **D / UNOBSERVED** |

---

## 21. Gates

| Gate | Status | Notes |
|------|--------|-------|
| A Frozen universe | **PASS** | 1230 / 910 / 320 / 0 |
| B PADE integrity | **PASS** | Expected files + hashes; PADE not modified |
| C Market lookahead | **PASS** | 0 future candles in `X_n` |
| D Game lookahead | **PASS** | 0 future PBP in `X_n` |
| E Split isolation | **PASS** | 0 games in multiple splits |
| F Unresolved preservation | **PASS** | universe=1230 panel=1221 unresolved=9 |
| G Model baseline | **PASS** | Every advanced family vs B0 |
| H OOS discipline | **PASS** | No OOS hyperparameter tuning |
| I Execution claims | **PASS** | Language constraints preserved |

---

## 22. Scientific verdict

| Item | Result |
|------|--------|
| Architecture / incremental state value | **PARTIAL** |
| Saturated 40-in-5 control | **PASS** |
| Exposure asymmetry | **PASS** |
| Target-delta stability | **PARTIAL** |
| Remaining possessions | **INCONCLUSIVE** |
| Execution evidence | **UNOBSERVED** |
| Live deployment | **NOT AUTHORIZED** |

Panel: 139966 rows / 1221 trades / 1221 games.  
Universe: 1230 frozen FIRST-80 trades. Unresolved preserved: 9.

This experiment does **not** prove DRE “works” as a trading policy. It asks whether additional state changes the *theoretical* desire to retain exposure. See `DRE_V2_RESEARCH_VERDICT.md`.

---

## 23. Explicit next experiment

Authorized only by a later mandate. Candidates, none of which are live:

1. Isolated remaining-possession model revision (side experiment, not a silent DRE revision).
2. Execution-tape / L2 join so `h*` can be tested against **observed** reduce-only opportunities.
3. Sport expansion only after joinable PBP exists (NCAAB currently cannot).

Until execution evidence exists, DRE V2 cannot leave the research layer.

---

## How to rerun

```
/tmp/momento-nba-venv/bin/python apps/nba-data/scripts/dre_v2.py
```

Outputs: `Backtesting Suite/Data/NBA/2025-2026/warehouse/derived/nba/dynamic_risk_engine_v2/`

Dashboard: `frontend/dre-v2` on http://127.0.0.1:5184/

PADE V1 left untouched.

**LIVE DEPLOYMENT: NOT AUTHORIZED**
