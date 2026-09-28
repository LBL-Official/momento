"""Fundamental tables are not PIT datasets."""

from __future__ import annotations

from pathlib import Path

import pytest

from roller import Roller
from roller.point_in_time.filters import FutureInformationError


def test_fundamental_names_rejected(roller_env: Path):
    db = Roller(roller_env)
    for name in (
        "fundamental",
        "fundamental_win_probability_empirical_v1",
        "v4a_fundamental_state_corpus",
        "home_win_fundamental",
    ):
        with pytest.raises(FutureInformationError, match="use db.fundamental()"):
            db.dataset("NBA", "2025-2026", name, as_of="2025-12-21")


def test_canonical_games_still_load(roller_env: Path):
    from roller.config import RollerConfig
    from roller.maintenance.update import update_sport

    cfg = RollerConfig(roller_env)
    update_sport(cfg, "NBA", "2025-2026", include_pbp=True, include_candles=True)
    db = Roller(roller_env)
    games = db.dataset("NBA", "2025-2026", "games", as_of="2025-12-21")
    assert not games.empty
