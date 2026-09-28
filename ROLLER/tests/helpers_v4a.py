"""Synthetic V4A fixtures. Not a public API."""

from __future__ import annotations

from typing import Any

from roller.config import RollerConfig
from roller.fundamental.conditioning import condition_state


def fake_observation(
    *,
    gid: str = "NBA_CUR",
    t: str = "2025-12-20T20:14:00Z",
    period: int = 2,
    elapsed: int = 780,
    margin: int = -3,
    sport: str = "NBA",
    season: str = "2025-2026",
) -> dict[str, Any]:
    return {
        "observation_id": f"OBS_{gid}_20251220T201400000Z_V2.0.0",
        "internal_game_id": gid,
        "sport": sport,
        "season": season,
        "observation_time": t,
        "GAME_STATE": {
            "data": {
                "period": period,
                "elapsed_game_seconds": elapsed,
                "clock": "PT11M00S",
                "score": {"score_differential_home": {"value": margin}, "home": {"value": 50}, "away": {"value": 53}},
            }
        },
    }


def stamped_row(
    cfg: RollerConfig,
    *,
    gid: str,
    state_at: str,
    result_at: str,
    home_win: str,
    period: int = 2,
    elapsed: int = 780,
    margin: int = -3,
    season: str = "2025-2026",
    home_team_id: str = "BOS",
    away_team_id: str = "LAL",
) -> dict[str, Any]:
    cond = condition_state(
        cfg,
        {"period": period, "elapsed_game_seconds": elapsed, "score_differential_home": margin},
    )
    return {
        "internal_game_id": gid,
        "sport": "NBA",
        "season": season,
        "home_team_id": home_team_id,
        "away_team_id": away_team_id,
        "observation_time": state_at,
        "state_available_at": state_at,
        "result_available_at": result_at,
        "period": period,
        "elapsed_game_seconds": elapsed,
        "score_differential_home": margin,
        "condition_id": cond["condition_id"],
        "conditioning_schema_version": cond["conditioning_schema_version"],
        "home_win": home_win,
        "y_home_win": 1 if home_win == "1" else 0,
    }
