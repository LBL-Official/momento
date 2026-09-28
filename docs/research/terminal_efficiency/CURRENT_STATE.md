# Terminal Efficiency V1 — Current State

```text
TERMINAL EFFICIENCY V1

TRAINING                    COMPLETE
PIT VALIDATION              PASS
MODEL SELECTION             FROZEN
FROZEN ARTIFACT INSPECTION  COMPLETE
READ-ONLY CONSUMPTION       COMPLETE

MARKET ALIGNMENT RESEARCH   NOT AUTHORIZED
PHASE 7                     NOT AUTHORIZED
MARKET RESIDUAL ANALYSIS    NOT AUTHORIZED
ROLLER QUERY INTEGRATION    NOT AUTHORIZED
TRADING                     NOT AUTHORIZED
```

```text
TRAINING PIPELINE COMPLETE
PIT AUDIT PASS
MODEL SELECTION COMPLETE
FROZEN OBJECT AVAILABLE
────────────────────────────────────────
MARKET EVALUATION NOT AUTHORIZED
ROLLER CONSUMPTION NOT AUTHORIZED
PHASE 7 NOT AUTHORIZED
LIVE / TRADING USE NOT AUTHORIZED
```

```text
BASKETBALL PREDICTIVE INTELLIGENCE
                ≠
MARKET MISPRICING INTELLIGENCE
```

The frozen basketball intelligence object is **operationally consumable** through a read-only loader. It is **not** analytically entangled with the market. The loader answers “what frozen intelligence observations are available for this requested universe?” It does not answer “what does the model think about this market?”

Phase 7 (apply frozen F_t to 2025–26 and compare to K_t) is not authorized.

---

## Published freeze identities (exact match only)

| League | Season | model_version | dataset_version | feature_set_version | code_version |
|--------|--------|---------------|-----------------|---------------------|--------------|
| NBA | 2024-2025 | XIB-NBA-V1 | TE-DATASET-B-NBA-2024-25-V1 | model1_plus_pregame | 0.1.0 |
| NCAAB | 2024-2025 | XIB-NCAAB-V1 | TE-DATASET-B-NCAAB-2024-25-P5-V1 | model1_plus_pregame | 0.1.0 |

A consumer must request this tuple (plus `artifact_manifest_hash` when pinning). Mismatch → `UNAVAILABLE`. No latest, nearest-match, or silent substitution.

---

## Coverage preserved as data

```text
NBA
  XIB: available within frozen supported coverage
  Dataset C alignment: 5,201 MODELED / 42,646 UNALIGNED
  timeActual: DATA GAP

NCAAB
  in-game XIB: P5-vs-P5 verified PBP only
  otherwise: UNAVAILABLE
```

Missing ≠ zero. Corrupt null ≠ coverage UNAVAILABLE. Raw probabilities were not persisted (`raw_probability_status=UNAVAILABLE`).

---

## What the Phase 3 PASS means

The audited feature pipeline appears **temporally valid for the datasets used in fitting**.

It does **not** establish out-of-sample predictive performance.

---

## Isolation (intact)

```text
Kalshi price ∉ XIB features
Kalshi price ∉ MCD state
Candle availability ≠ prerequisite for training
Consumption path does not import training
```

---

## Selection (among evaluated candidates only)

NBA VAL Brier: Model 0 = 0.174 · **Model 1 = 0.160 (frozen)** · Model 2 = 0.159 (Δ < 0.001 bar) · Model 3 = **NOT RUN** · MCD = 0.182 on an **800-row sample**.

Model 3 comparison was not performed (`libomp` unavailable). Selected model is best among **evaluated** candidates. Do not rewrite that as “Model 1 beat Model 3.”

MCD: **PROTOTYPE EVALUATED · NOT SELECTED · LIMITED VALIDATION COVERAGE**. Directionally not competitive on the 800-row sample. Not scientifically rejected on the full VAL population. No ensemble.

---

## Do not do next

- Do not begin Phase 7.
- Do not join Kalshi prices or compute residuals.
- Do not optimize trading rules.
- Do not wire XIB into ROLLER’s generic query engine as a feature dimension that can refit the model.
- Do not rename the loader into a market-evaluation layer.

See [FROZEN_DATASET_CONSUMPTION_CONTRACT.md](FROZEN_DATASET_CONSUMPTION_CONTRACT.md).
