from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from terminal_efficiency.consumption.errors import (
    ConsumptionForbidden,
    FrozenUnavailable,
    ProvenanceRequired,
    VersionMismatch,
)
from terminal_efficiency.consumption.loader import FrozenObjectLoader
from terminal_efficiency.consumption.models import FrozenIdentity, REQUIRED_VIEW_FIELDS
from terminal_efficiency.consumption.store import data_root, derived_root
from terminal_efficiency.frozen_artifacts.registry import resolve_published

PKG = Path(__file__).resolve().parents[1]


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _canon(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _write_temp_freeze(tmp: Path, *, league: str = "NBA", p5_games: dict[str, bool] | None = None) -> FrozenIdentity:
    dest = derived_root(tmp, league, "2024-2025")
    (dest / "predictions").mkdir(parents=True)
    (dest / "models").mkdir(parents=True)
    (dest / "frozen_artifacts" / "manifests").mkdir(parents=True)
    pred = pd.DataFrame(
        [
            {
                "observation_id": "TE_G1_1",
                "league": league,
                "season": "2024-2025",
                "game_id": "G1",
                "prediction_timestamp": "2025-01-01T00:00:00Z",
                "feature_as_of_timestamp": "2024-12-31T00:00:00Z",
                "timestamp_quality": "MODELED",
                "data_quality_flags": "MODELED",
                "xib_home_win_probability": 0.61,
            }
        ]
    )
    pred_path = dest / "predictions" / "xib_2024_25.parquet"
    pred.to_parquet(pred_path, index=False)
    model_path = dest / "models" / "xib_frozen.joblib"
    model_path.write_bytes(b"not-a-real-model")
    if league == "NCAAB":
        games = pd.DataFrame(
            [
                {"game_id": gid, "p5_vs_p5": flag}
                for gid, flag in (p5_games or {"G1": True, "NONP5": False}).items()
            ]
        )
        games.to_parquet(dest / "games.parquet", index=False)
    payload = {
        "league": league,
        "season": "2024-2025",
        "dataset_version": "TE-TEST-V1",
        "feature_set_version": "model1_plus_pregame",
        "model_version": f"XIB-{league}-TEST",
        "code_version": "0.1.0",
        "prediction_file": "predictions/xib_2024_25.parquet",
        "frozen_model_file": "models/xib_frozen.joblib",
        "coverage": {"xib_coverage": "test"},
        "raw_probability_status": "UNAVAILABLE",
        "calibrated_probability_status": "AVAILABLE",
        "read_only": True,
        "prediction_sha256": _sha(pred_path),
        "frozen_model_sha256": _sha(model_path),
    }
    payload["artifact_manifest_hash"] = hashlib.sha256(_canon(payload).encode()).hexdigest()
    name = f"{league}_2024-2025_{payload['model_version']}.json"
    (dest / "frozen_artifacts" / "manifests" / name).write_text(json.dumps(payload, indent=2, sort_keys=True))
    identity = FrozenIdentity(
        league=league,
        season="2024-2025",
        dataset_version=payload["dataset_version"],
        feature_set_version=payload["feature_set_version"],
        model_version=payload["model_version"],
        code_version=payload["code_version"],
        artifact_manifest_hash=payload["artifact_manifest_hash"],
    )
    return identity, [payload]


def test_loader_has_no_training_api():
    loader = FrozenObjectLoader(data_root_path=Path("/tmp"))
    for name in ("fit", "train", "calibrate", "select_model", "evaluate_oos"):
        with pytest.raises(ConsumptionForbidden):
            getattr(loader, name)


def test_nonexistent_model_version_fails_closed():
    with pytest.raises(VersionMismatch):
        resolve_published(league="NBA", season="2024-2025", model_version="XIB_V999")


def test_latest_alias_fails_closed():
    with pytest.raises(VersionMismatch):
        resolve_published(league="NBA", season="2024-2025", model_version="latest")


def test_phase7_season_is_unavailable_not_evaluated():
    with pytest.raises(VersionMismatch):
        resolve_published(league="NBA", season="2025-2026", model_version="XIB-NBA-V1")


def test_evaluate_kwargs_forbidden(tmp_path: Path):
    identity, records = _write_temp_freeze(tmp_path)
    loader = FrozenObjectLoader(data_root_path=tmp_path, registry_records=records)
    with pytest.raises(ConsumptionForbidden):
        loader.inspect(identity, evaluate=True)
    with pytest.raises(ConsumptionForbidden):
        loader.load_observations(identity, game_ids=["G1"], evaluate_oos=True)
    with pytest.raises(ConsumptionForbidden):
        loader.inspect(identity, kalshi=True)


def test_ncaab_non_p5_is_unavailable(tmp_path: Path):
    identity, records = _write_temp_freeze(tmp_path, league="NCAAB")
    loader = FrozenObjectLoader(data_root_path=tmp_path, registry_records=records)
    view = loader.lookup_game(identity, "NONP5")
    frame = view.to_frame()
    assert len(frame) == 1
    assert bool(frame.iloc[0]["prediction_available"]) is False
    assert frame.iloc[0]["availability_status"] == "UNAVAILABLE"
    assert frame.iloc[0]["coverage_status"] == "NCAAB_INGAME_XIB_REQUIRES_P5_VS_P5_VERIFIED_PBP"
    assert frame.iloc[0]["calibrated_probability"] is None
    assert pd.isna(frame.iloc[0]["raw_probability"]) or frame.iloc[0]["raw_probability"] is None


def test_ncaab_does_not_substitute_nearest_or_pregame(tmp_path: Path):
    identity, records = _write_temp_freeze(tmp_path, league="NCAAB")
    dest = derived_root(tmp_path, "NCAAB", "2024-2025")
    pd.DataFrame([{"game_id": "NONP5", "xib_home_win_probability": 0.99}]).to_parquet(
        dest / "dataset_a_pregame.parquet", index=False
    )
    loader = FrozenObjectLoader(data_root_path=tmp_path, registry_records=records)
    view = loader.lookup_game(identity, "NONP5")
    frame = view.to_frame()
    assert frame.iloc[0]["calibrated_probability"] is None
    assert frame.iloc[0]["game_id"] == "NONP5"
    assert (frame["calibrated_probability"] == 0.61).sum() == 0


def test_mutation_of_model_artifact_fails_closed(tmp_path: Path):
    identity, records = _write_temp_freeze(tmp_path)
    loader = FrozenObjectLoader(data_root_path=tmp_path, registry_records=records)
    loader.inspect(identity)
    dest = derived_root(tmp_path, "NBA", "2024-2025")
    (dest / "models" / "xib_frozen.joblib").write_bytes(b"mutated")
    with pytest.raises(FrozenUnavailable, match="hash mismatch"):
        loader.inspect(identity)


def test_mutation_of_prediction_artifact_fails_closed(tmp_path: Path):
    identity, records = _write_temp_freeze(tmp_path)
    dest = derived_root(tmp_path, "NBA", "2024-2025")
    pred = dest / "predictions" / "xib_2024_25.parquet"
    extra = pd.read_parquet(pred)
    extra.loc[0, "xib_home_win_probability"] = 0.01
    extra.to_parquet(pred, index=False)
    loader = FrozenObjectLoader(data_root_path=tmp_path, registry_records=records)
    with pytest.raises(FrozenUnavailable, match="hash mismatch"):
        loader.load_observations(identity, game_ids=["G1"])


def test_loader_cannot_write_artifacts(tmp_path: Path):
    identity, records = _write_temp_freeze(tmp_path)
    loader = FrozenObjectLoader(data_root_path=tmp_path, registry_records=records)
    with pytest.raises(ConsumptionForbidden):
        loader.write_artifact(tmp_path / "models" / "xib_frozen.joblib", b"x")
    with pytest.raises(ConsumptionForbidden):
        loader.persist()


def test_probabilities_only_rejected(tmp_path: Path):
    identity, records = _write_temp_freeze(tmp_path)
    loader = FrozenObjectLoader(data_root_path=tmp_path, registry_records=records)
    with pytest.raises(ProvenanceRequired):
        loader.load_observations(identity, game_ids=["G1"], columns=["game_id", "calibrated_probability"])
    view = loader.lookup_game(identity, "G1")
    with pytest.raises(ProvenanceRequired):
        view.probabilities_only()
    with pytest.raises(ProvenanceRequired):
        view.to_probability_map()


def test_row_level_provenance_survives(tmp_path: Path):
    identity, records = _write_temp_freeze(tmp_path)
    loader = FrozenObjectLoader(data_root_path=tmp_path, registry_records=records)
    view = loader.lookup_game(identity, "G1")
    rec = view.records()[0]
    for field in REQUIRED_VIEW_FIELDS:
        assert hasattr(rec, field)
    assert rec.prediction_available is True
    assert rec.calibrated_probability == pytest.approx(0.61)
    assert rec.raw_probability is None
    assert rec.model_version == identity.model_version
    assert rec.artifact_manifest_hash == identity.artifact_manifest_hash
    assert rec.prediction_timestamp
    assert rec.feature_as_of_timestamp
    assert "MODELED" in rec.data_quality_flags


def test_zero_probability_is_not_unavailable(tmp_path: Path):
    dest = derived_root(tmp_path, "NBA", "2024-2025")
    identity, records = _write_temp_freeze(tmp_path)
    pred = dest / "predictions" / "xib_2024_25.parquet"
    df = pd.read_parquet(pred)
    df.loc[0, "xib_home_win_probability"] = 0.0
    df.to_parquet(pred, index=False)
    records[0]["prediction_sha256"] = _sha(pred)
    body = {k: v for k, v in records[0].items() if k != "artifact_manifest_hash"}
    records[0]["artifact_manifest_hash"] = hashlib.sha256(_canon(body).encode()).hexdigest()
    identity = FrozenIdentity(**{**identity.as_dict(), "artifact_manifest_hash": records[0]["artifact_manifest_hash"]})
    name = f"NBA_2024-2025_{records[0]['model_version']}.json"
    (dest / "frozen_artifacts" / "manifests" / name).write_text(json.dumps(records[0], indent=2, sort_keys=True))
    loader = FrozenObjectLoader(data_root_path=tmp_path, registry_records=records)
    rec = loader.lookup_game(identity, "G1").records()[0]
    assert rec.prediction_available is True
    assert rec.calibrated_probability == 0.0
    assert rec.availability_status == "AVAILABLE"


def test_consumption_import_does_not_load_training():
    script = """
import sys
import terminal_efficiency.consumption.loader as loader
banned = [
    "terminal_efficiency.pipeline",
    "terminal_efficiency.models.xib",
    "terminal_efficiency.models.mcd",
    "terminal_efficiency.training",
    "terminal_efficiency.training.charts",
    "joblib",
    "sklearn",
    "lightgbm",
]
hit = [m for m in banned if m in sys.modules]
assert not hit, hit
assert not hasattr(loader.FrozenObjectLoader, "fit")
print("ok")
"""
    proc = subprocess.run([sys.executable, "-c", script], cwd=str(PKG), capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "ok" in proc.stdout


def _warehouse_present(league: str) -> bool:
    dest = derived_root(data_root(), league, "2024-2025")
    return (dest / "predictions" / "xib_2024_25.parquet").is_file()


@pytest.mark.skipif(not _warehouse_present("NBA"), reason="NBA frozen artifacts not on disk")
def test_real_nba_inspect_and_lookup():
    identity, record = resolve_published(league="NBA", season="2024-2025", model_version="XIB-NBA-V1")
    loader = FrozenObjectLoader()
    info = loader.inspect(identity)
    assert info["read_only"] is True
    assert info["joblib_unpickled"] is False
    assert info["dataset_c_opened"] is False
    assert info["coverage"]["timeActual"] == "DATA GAP"
    assert info["coverage"]["dataset_c_alignment"]["MODELED"] == 5201
    view = loader.lookup_game(identity, "0022400062")
    frame = view.to_frame()
    assert frame["prediction_available"].all()
    assert set(REQUIRED_VIEW_FIELDS) <= set(frame.columns)
    assert frame["model_version"].eq("XIB-NBA-V1").all()
    missing = loader.lookup_game(identity, "NO_SUCH_GAME")
    assert missing.records()[0].availability_status == "UNAVAILABLE"


@pytest.mark.skipif(not _warehouse_present("NCAAB"), reason="NCAAB frozen artifacts not on disk")
def test_real_ncaab_non_p5_unavailable():
    identity, _ = resolve_published(league="NCAAB", season="2024-2025", model_version="XIB-NCAAB-V1")
    loader = FrozenObjectLoader()
    view = loader.lookup_game(identity, "401706962")
    rec = view.records()[0]
    assert rec.prediction_available is False
    assert rec.availability_status == "UNAVAILABLE"
    assert rec.coverage_status == "NCAAB_INGAME_XIB_REQUIRES_P5_VS_P5_VERIFIED_PBP"
    assert rec.calibrated_probability is None
    ok = loader.lookup_game(identity, "401715355")
    assert ok.records()[0].prediction_available is True
    assert ok.records()[0].coverage_status == "P5_VS_P5_VERIFIED_PBP"
