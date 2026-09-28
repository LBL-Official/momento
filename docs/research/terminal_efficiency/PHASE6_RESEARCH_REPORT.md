# Terminal Efficiency — Phase 6 Research Report

```text
TRAINING PIPELINE COMPLETE · PIT AUDIT PASS · MODEL SELECTION COMPLETE · MARKET EVALUATION NOT AUTHORIZED
```

Canonical status: [CURRENT_STATE.md](CURRENT_STATE.md).

**Stop condition:** Phases 0–6 complete. Phase 7 OOS is **not authorized**. This is **not** a claim that F_t vs K_t has been validated.

```text
MODEL ≠ EDGE
K_t − F_t ≠ TRADE
CANDLE PATH ≠ FILL
```

---

## Data coverage

### NBA 2024–25

| Asset | Result |
|-------|--------|
| Games (paired LeagueGameLog + box) | 1,385 |
| PBP events | 684,495 |
| Dataset B possession observations | 276,994 |
| TRAIN / VAL | 186,614 / 90,380 |
| `timeActual` | DATA GAP — alignment MODELED |
| Kalshi candles | PARTIAL — 47,847 bars loaded from 58 playoff tickers |
| Dataset C (prominent) | **5,201 MODELED · 42,646 UNALIGNED · 58 playoff tickers** |

Training ran **without** requiring candles. Dataset C is a small, playoff-selected, MODELED-clock surface — not a season-representative market grid.

### NCAAB 2024–25

| Asset | Result |
|-------|--------|
| Kalshi | DATA GAP — warehouse CLI dry-run `events=0`; Dataset C empty |
| ESPN D1 scoreboard | 156 days, **6,299** games |
| P5-vs-P5 | 820 games; **816** PBP files (1 ESPN 504) |
| Dataset B | 71,108 possession rows; VAL n=15,546 |
| Non-P5 PBP | Not fabricated (Dataset A only) |

### Frozen 2025–26

Read-only. Not used for fit, selection, or calibration.

---

## Leakage audit

NBA and NCAAB Dataset A/B: **PASS** on the tables used for fitting (`reports/leakage_audit.json`).

Interpretation is narrow: the feature pipeline appears **temporally valid for those fit tables**. It does not establish OOS performance or a Kalshi residual.

---

## Baseline vs XIB (NBA VAL)

| Model | Brier | Log loss | ECE |
|-------|-------|----------|-----|
| Model 0 score+clock+period | 0.1743 | 0.5193 | 0.0375 |
| **Model 1 + PIT team strength (SELECTED)** | **0.1596** | **0.4840** | **0.0351** |
| Model 2 + possession/pace/run | 0.1588 | 0.4819 | 0.0371 |
| Model 3 LightGBM | **NOT RUN** — `libomp` unavailable |

Model 2’s Brier improvement (0.00076) is below the pre-registered 0.001 threshold, so Model 1 is selected over the slightly lower Model 2 number.

```text
MODEL 3 COMPARISON: NOT RUN
REASON: ENVIRONMENT DEPENDENCY UNAVAILABLE
IMPLICATION: SELECTED MODEL IS BEST AMONG EVALUATED CANDIDATES
```

Do not rewrite “LightGBM skipped” as “Model 1 beat Model 3.”

Accuracy is secondary (Model 0 ~73% vs Model 1 similar). Q1 is the weakest slice (highest Brier), as expected.

---

## MCD vs XIB (NBA VAL sample)

| Object | n | Brier | Log loss | ECE |
|--------|---|-------|----------|-----|
| XIB-NBA-V1 | 90,380 | 0.1596 | 0.484 | 0.035 |
| MCD-NBA-V1 | 800 | 0.1815 | 0.636 | 0.100 |

**No ensemble.** MCD did not demonstrate competitiveness on this **800-row sample**. That is not a full-VAL rejection. Classification: `PROTOTYPE EVALUATED · NOT SELECTED · LIMITED VALIDATION COVERAGE`. Sample residuals look over-confident at the extremes.

---

## NCAAB XIB / MCD (VAL)

| Object | Brier | Note |
|--------|-------|------|
| Model 0 | 0.1577 | score + clock + period |
| **XIB Model 1 (SELECTED)** | **0.1513** | + prior win% / last-5 |
| Model 2 | 0.1513 | no material gain; pace/possession often missing |
| MCD (n=800 sample) | 0.1635 | not competitive on the sample; no ensemble |

---

## Known weaknesses

- NBA 2024–25 wall clock is MODELED (period-bounded / elapsed-clock proxy).
- Logistic Model 1/2 hit `max_iter` without a scaler (convergence warning).
- Model 3 not evaluated (OpenMP).
- Dataset C coverage is playoff-only and mostly unaligned to regular-season games.
- NCAAB 2024–25 Kalshi absent; D1 box advanced stats absent.
- MCD has no foul/bonus model and was scored on a VAL subsample.

---

## Recommended next research (not this assignment)

1. Install `libomp` and walk Model 3 **once** on the same frozen split.
2. Add TRAIN-only `StandardScaler` and re-walk 0→2 once (new version, not silent overwrite).
3. Complete NCAAB ESPN through April so official VAL exists; then freeze XIB-NCAAB-V1.
4. Optional `timeActual` backfill for 2024–25 if CDN serves it.
5. **Do not begin Phase 7. Do not wire XIB into ROLLER’s query engine.**
6. Frozen object loader: **COMPLETE** ([consumption contract](FROZEN_DATASET_CONSUMPTION_CONTRACT.md)). Do not join Kalshi, compute residuals, or start Phase 7 under another name.

---

## STOP

Do not modify ROLLER. Do not run 2025–26 evaluation. Do not claim alpha.
