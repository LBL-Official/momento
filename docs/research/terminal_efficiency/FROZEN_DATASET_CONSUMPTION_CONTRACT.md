# Frozen Dataset Consumption Contract

**Status:** READ-ONLY LOADER COMPLETE. Not a ROLLER producer. Not Phase 7.

```text
FROZEN ARTIFACTS
      │
      ▼
Artifact Manifest
      │
      ▼
Read-Only Loader
      │
      ├── version validation
      ├── schema validation
      ├── coverage validation
      ├── league/universe validation
      ├── quality-flag preservation
      └── provenance preservation
      │
      ▼
AUDITED READ-ONLY VIEW
```

The loader answers:

```text
What frozen intelligence observations are available for this requested universe?
```

It must not answer:

```text
What does the model think about this market?
```

---

## Fail closed

Request or configuration must resolve explicitly against:

```text
league
season
dataset_version
feature_set_version
model_version
code_version
artifact_manifest_hash
```

If the combination is not published, or on-disk hashes do not match the manifest:

```text
UNAVAILABLE
```

No nearest match, fallback model, or silent substitution. `latest` is rejected.

Published identities:

| League | Season | model_version | dataset_version | feature_set_version | code_version |
|--------|--------|---------------|-----------------|---------------------|--------------|
| NBA | 2024-2025 | XIB-NBA-V1 | TE-DATASET-B-NBA-2024-25-V1 | model1_plus_pregame | 0.1.0 |
| NCAAB | 2024-2025 | XIB-NCAAB-V1 | TE-DATASET-B-NCAAB-2024-25-P5-V1 | model1_plus_pregame | 0.1.0 |

---

## Coverage is data

Every returned row includes:

```text
observation_id
game_id
league
season
prediction_timestamp
feature_as_of_timestamp
raw_probability                  # UNAVAILABLE on this freeze (not persisted)
calibrated_probability
model_version
dataset_version
feature_set_version
code_version
artifact_manifest_hash
prediction_available
availability_status              # AVAILABLE | UNAVAILABLE | CORRUPT
coverage_status
feature_availability_status
data_quality_flags
```

A missing prediction is distinguishable from a true zero and from a corrupt null.

NBA Dataset C facts are published on the manifest (`5,201 MODELED / 42,646 UNALIGNED`, `timeActual = DATA GAP`). The loader does not open Dataset C or join Kalshi candles.

NCAAB non-P5 / missing PBP → `UNAVAILABLE`. No nearest-neighbor game. No pregame substitution disguised as in-game XIB.

---

## Architectural isolation

```text
terminal_efficiency/
    training/          # not imported by consumption
    validation/
    frozen_artifacts/
        manifests/
    consumption/
        loader.py
        validation.py
        models.py
```

The consumption path has no `fit()`, `train()`, `calibrate()`, `select_model()`, or `evaluate_oos()`. It does not unpickle `xib_frozen.joblib` to score. Artifact mutation (model / prediction hash change) fails closed.

There is no probabilities-only projection on this loader. A documented projection layer does not exist yet; stripping quality fields is rejected.

`evaluate --season 2025-2026` remains `NOT AUTHORIZED`. The loader may report that no 2025–26 freeze is published (`UNAVAILABLE`). It is not a backdoor around Phase 7.

---

## CLI

Read-only consumer entry (does not import the training pipeline):

```text
python -m terminal_efficiency.consumption inspect \
  --league NBA --season 2024-2025 --model-version XIB-NBA-V1

python -m terminal_efficiency.consumption lookup-game \
  --league NCAAB --season 2024-2025 --model-version XIB-NCAAB-V1 \
  --game-id 401706962
```

Compatibility:

```text
python -m terminal_efficiency inspect-frozen --league NBA --season 2024-2025
```

Does not write inspect reports. Does not evaluate 2025–26.

---

## Forbidden

```text
ROLLER QUESTION → changes XIB features → refits XIB → returns an answer
Kalshi join / residual / XIB edge
Phase 7 OOS through the loader
Naked game_id → probability maps
```

ROLLER remains an empirical market-query engine. Terminal Efficiency remains an independent basketball intelligence layer.
