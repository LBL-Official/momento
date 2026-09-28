from __future__ import annotations

from pathlib import Path

from roller.config import RollerConfig
from roller.maintenance.update import update_all
from roller.registry import missing_required_paths, save_registry


def test_missing_required_path_fails(roller_env: Path):
    cfg = RollerConfig(roller_env)
    save_registry(
        cfg,
        {
            "datasets": [
                {
                    "dataset_name": "ghost",
                    "path": "data/does_not_exist/games.csv",
                    "status": "required",
                }
            ]
        },
    )
    missing = missing_required_paths(cfg)
    assert "data/does_not_exist/games.csv" in missing


def test_update_pipeline_builds_datasets(roller_env: Path):
    cfg = RollerConfig(roller_env)
    daily = update_all(cfg, sports=["NBA"], include_pbp=True, include_candles=True)
    assert daily["integrity"]["status"] == "PASS"
    assert daily["leakage"]["status"] == "PASS"
    assert (roller_env / "data" / "nba" / "2025_2026" / "canonical" / "games.csv").is_file()


def test_source_hash_logged_on_rebuild(roller_env: Path):
    cfg = RollerConfig(roller_env)
    update_all(cfg, sports=["NBA"], include_pbp=False, include_candles=False, validate=False)
    log = (roller_env / "meta" / "update_log.csv").read_text()
    assert "prior_source_hash" in log.splitlines()[0]
    assert "new_source_hash" in log.splitlines()[0]
