"""Gate 1: metadata and future-information reject. V1 half-open stays."""

from __future__ import annotations

from pathlib import Path

import pytest

from roller import Roller
from roller.config import RollerConfig
from roller.maintenance.update import update_sport
from roller.point_in_time.filters import FutureInformationError
from roller.timeutil import apply_as_of, resolve_cutoff
import pandas as pd


def test_half_open_equality_still_hidden():
    cutoff = resolve_cutoff("2025-12-19T10:00:02Z")
    df = pd.DataFrame(
        {
            "available_at": [
                "2025-12-19T10:00:01Z",
                "2025-12-19T10:00:02Z",
                "2025-12-19T10:00:03Z",
            ],
            "v": [1, 2, 3],
        }
    )
    out = apply_as_of(df, cutoff)
    assert list(out["v"]) == [1]


def test_state_schema_and_registries_exist(roller_env: Path):
    cfg = RollerConfig(roller_env)
    assert cfg.db_map["database"]["version"] == "4.0.0-C"
    assert cfg.db_map["database"]["state_schema_version"] == "2.0.0"
    assert cfg.db_map["database"]["measurement_schema_version"] == "3.0.0"
    assert cfg.db_map["database"]["fundamental_schema_version"] == "4.0.0-A"
    assert cfg.db_map["database"]["greek_schema_version"] == "4.0.0-B"
    assert cfg.db_map["database"]["greek_architecture_version"] == "4.0.0-C"
    assert cfg.db_map["as_of"]["filter"] == "available_at < cutoff"
    assert (roller_env / "meta" / "feature_registry.json").is_file() or (
        Path(__file__).resolve().parents[1] / "meta" / "feature_registry.json"
    ).is_file()
    src = Path(__file__).resolve().parents[1]
    feats = (src / "meta" / "feature_registry.json").read_text()
    assert '"lookahead": false' in feats or '"lookahead":false' in feats
    assert (src / "config" / "labels.json").is_file()
    assert (src / "config" / "regimes.json").is_file()


def test_terminal_dataset_rejected_from_public_dataset(roller_env: Path):
    cfg = RollerConfig(roller_env)
    update_sport(cfg, "NBA", "2025-2026", include_pbp=True, include_candles=True)
    db = Roller(roller_env)
    with pytest.raises(FutureInformationError):
        db.dataset("NBA", "2025-2026", "game_state_features", as_of="2025-12-21")
    games = db.dataset("NBA", "2025-2026", "games", as_of="2025-12-19")
    assert not games.empty
