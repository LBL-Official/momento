from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from roller import Roller
from roller.config import RollerConfig
from roller.maintenance.update import update_sport
from roller.point_in_time.filters import AsOfRequiredError
from roller.timeutil import TimestampError, apply_as_of, resolve_cutoff


def test_date_cutoff_is_utc_start():
    assert resolve_cutoff("2025-12-19").isoformat() == "2025-12-19T00:00:00+00:00"
    assert resolve_cutoff("2025-12-19", end_of_day=True).isoformat() == "2025-12-20T00:00:00+00:00"


def test_half_open_excludes_equality():
    cutoff = resolve_cutoff("2025-12-19")
    df = pd.DataFrame(
        {
            "available_at": ["2025-12-18T23:59:59Z", "2025-12-19T00:00:00Z", "2025-12-19T01:00:00Z"],
            "v": [1, 2, 3],
        }
    )
    out = apply_as_of(df, cutoff)
    assert list(out["v"]) == [1]


def test_public_api_requires_as_of(roller_env: Path):
    cfg = RollerConfig(roller_env)
    update_sport(cfg, "NBA", "2025-2026", include_pbp=True, include_candles=True)
    db = Roller(roller_env)
    with pytest.raises(AsOfRequiredError):
        db.dataset("NBA", "2025-2026", "games")
    games = db.dataset("NBA", "2025-2026", "games", as_of="2025-12-19")
    assert not games.empty
    # Game on 2025-12-20 has identity_available_at at tip 19:00 that day
    assert "NBA_20251220_LAL_BOS" not in set(games["internal_game_id"])


def test_d2d_excludes_future_games(roller_env: Path):
    cfg = RollerConfig(roller_env)
    update_sport(cfg, "NBA", "2025-2026", include_pbp=True, include_candles=True)
    db = Roller(roller_env)
    state = db.get_team_state("LAL", as_of="2025-12-19", sport="NBA", season="2025-2026")
    assert state["games"] == 2
    assert state["wins"] == 1
    assert state["losses"] == 1
    later = db.get_team_state("LAL", as_of="2025-12-21", sport="NBA", season="2025-2026")
    assert later["games"] == 3
    assert later["wins"] == 2


def test_naive_as_of_raises():
    with pytest.raises(TimestampError):
        resolve_cutoff(datetime(2025, 12, 19))
