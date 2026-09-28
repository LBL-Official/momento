"""Canonical freeze identity fields. Hashes are computed at publish time, not guessed."""

from __future__ import annotations

from typing import Any

CODE_VERSION = "0.1.0"
FEATURE_SET_VERSION = "model1_plus_pregame"
PREDICTION_RELPATH = "predictions/xib_2024_25.parquet"
FROZEN_MODEL_RELPATH = "models/xib_frozen.joblib"

# Coverage is published as data. Do not flatten into a probability.
NBA_COVERAGE: dict[str, Any] = {
    "xib_coverage": "available within frozen supported coverage",
    "dataset_c_alignment": {
        "MODELED": 5201,
        "UNALIGNED": 42646,
        "OBSERVED": 0,
        "AMBIGUOUS": 0,
        "playoff_tickers": 58,
    },
    "timeActual": "DATA GAP",
    "ncaab_in_game_universe": None,
}

NCAAB_COVERAGE: dict[str, Any] = {
    "xib_coverage": "in-game XIB: P5-vs-P5 verified PBP only; otherwise UNAVAILABLE",
    "dataset_c_alignment": "DATA GAP",
    "timeActual": "DATA GAP",
    "ncaab_in_game_universe": "P5-vs-P5 verified PBP only",
}

FREEZE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "league": "NBA",
        "season": "2024-2025",
        "dataset_version": "TE-DATASET-B-NBA-2024-25-V1",
        "feature_set_version": FEATURE_SET_VERSION,
        "model_version": "XIB-NBA-V1",
        "code_version": CODE_VERSION,
        "prediction_file": PREDICTION_RELPATH,
        "frozen_model_file": FROZEN_MODEL_RELPATH,
        "coverage": NBA_COVERAGE,
        "raw_probability_status": "UNAVAILABLE",
        "calibrated_probability_status": "AVAILABLE",
        "read_only": True,
    },
    {
        "league": "NCAAB",
        "season": "2024-2025",
        "dataset_version": "TE-DATASET-B-NCAAB-2024-25-P5-V1",
        "feature_set_version": FEATURE_SET_VERSION,
        "model_version": "XIB-NCAAB-V1",
        "code_version": CODE_VERSION,
        "prediction_file": PREDICTION_RELPATH,
        "frozen_model_file": FROZEN_MODEL_RELPATH,
        "coverage": NCAAB_COVERAGE,
        "raw_probability_status": "UNAVAILABLE",
        "calibrated_probability_status": "AVAILABLE",
        "read_only": True,
    },
)
