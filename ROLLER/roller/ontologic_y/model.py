"""XIB is recorded and refused. The joblib file is never unpickled."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
MANIFEST = (
    REPO
    / "apps/terminal-efficiency/terminal_efficiency/frozen_artifacts/manifests/NBA_2024-2025_XIB-NBA-V1.json"
)

REASONS = (
    "NOT_XGBOOST",
    "JOBLIB_NOT_LOADED",
    "FEATURE_CONTRACT_IS_NOT_ROLLING_TEN",
    "WINNER_CLASSIFIER_DOES_NOT_PRICE_SPREAD_OR_TOTAL",
    "PRESEASON_APPLICABILITY_UNVERIFIED",
)


def assess_xib(manifest_path: Path | None = None) -> dict:
    path = manifest_path or MANIFEST
    if not path.is_file():
        return {
            "model_status": "MODEL_UNAVAILABLE",
            "probabilities": "unavailable",
            "artifact_found": False,
            "reasons": ["MANIFEST_MISSING"],
            "joblib_unpickled": False,
            "trained_in_process": False,
        }
    manifest = json.loads(path.read_text())
    model_file = path.parents[1] / str(manifest.get("frozen_model_file") or "")
    digest = None
    hash_ok = False
    if model_file.is_file() and model_file.suffix == ".joblib":
        digest = hashlib.sha256(model_file.read_bytes()).hexdigest()
        hash_ok = digest == manifest.get("frozen_model_sha256")
    reasons = list(REASONS)
    if not model_file.is_file():
        reasons.append("ARTIFACT_FILE_MISSING")
    elif digest != manifest.get("frozen_model_sha256"):
        reasons.append("HASH_MISMATCH")
    return {
        "model_status": "MODEL_INCOMPATIBLE",
        "probabilities": "unavailable",
        "artifact_found": True,
        "model_id": manifest.get("model_version"),
        "feature_set_version": manifest.get("feature_set_version"),
        "dataset_version": manifest.get("dataset_version"),
        "season": manifest.get("season"),
        "serialization": "joblib",
        "learner": "sklearn.linear_model.LogisticRegression",
        "target": "final_home_win",
        "features": [
            "score_difference",
            "seconds_remaining_game",
            "period",
            "home_win_pct_pre",
            "away_win_pct_pre",
            "home_net_rating_pre",
            "away_net_rating_pre",
            "home_wins_last5_pre",
            "away_wins_last5_pre",
        ],
        "artifact_sha256": digest,
        "manifest_sha256": manifest.get("frozen_model_sha256"),
        "hash_ok": hash_ok,
        "reasons": reasons,
        "supported_markets": [],
        "preseason_applicable": False,
        "pregame_only": False,
        "joblib_unpickled": False,
        "trained_in_process": False,
        "basis": None,
    }
