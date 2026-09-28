"""Labels never enter dataset() or observation(). research() is a V3 stub."""

from __future__ import annotations

from pathlib import Path

import pytest

from roller import Roller
from roller.config import RollerConfig
from roller.maintenance.update import update_sport
from roller.point_in_time.filters import FutureInformationError
from roller.point_in_time.query import ResearchNotImplementedError


def test_named_label_datasets_rejected(roller_env: Path):
    db = Roller(roller_env)
    for name in ("terminal_labels", "horizon_labels", "path_labels", "barrier_labels"):
        with pytest.raises(FutureInformationError):
            db.dataset("NBA", "2025-2026", name, as_of="2025-12-21")


def test_observation_excludes_labels(roller_env: Path):
    cfg = RollerConfig(roller_env)
    update_sport(cfg, "NBA", "2025-2026", include_pbp=True, include_candles=True)
    db = Roller(roller_env)
    obs = db.observation("NBA_20251220_LAL_BOS", as_of="2025-12-20T20:13:30Z")
    assert "labels" not in obs
    assert all("label" not in k.lower() for k in obs)
    blob = str(obs)
    assert "contains_future_information" not in blob
    assert "FIRST75" not in blob and "FIRST80" not in blob


def test_labels_api_requires_observation_identity(roller_env: Path):
    cfg = RollerConfig(roller_env)
    update_sport(cfg, "NBA", "2025-2026", include_pbp=True, include_candles=True)
    db = Roller(roller_env)
    obs = db.observation("NBA_20251220_LAL_BOS", as_of="2025-12-20T20:13:30Z")
    out = db.labels(observation_id=obs["observation_id"])
    assert out["labels"]
    assert all(row["contains_future_information"] is True for row in out["labels"])
    assert all("label_available_only_after" in row for row in out["labels"])
    names = {row["label_name"] for row in out["labels"]}
    assert "home_win" in names
    assert "home_score_change_next_300_seconds" in names
    assert "first80_trigger" in names
    assert "kalshi_yes_settled" in names
    assert not any("FIRST75" in n for n in names)


def test_research_stub_rejects_combining_labels(roller_env: Path):
    db = Roller(roller_env)
    with pytest.raises(ResearchNotImplementedError):
        db.research("NBA_20251220_LAL_BOS", as_of="2025-12-20T20:13:30Z")
