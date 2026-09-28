"""T_t — pre-game team features plus in-game score from G_t."""

from __future__ import annotations

from typing import Any

import pandas as pd

from roller.point_in_time.filters import public_filter
from roller.state.missingness import section


def team_state_section(
    features: pd.DataFrame,
    game: dict[str, Any] | None,
    latest_pbp: dict[str, Any] | None,
    *,
    as_of,
    end_of_day: bool = False,
    full_history: bool = False,
) -> dict[str, Any]:
    if features is None or features.empty:
        vis = features
    else:
        vis = (
            features
            if full_history
            else public_filter(features, as_of=as_of, end_of_day=end_of_day)
        )
    rows = [] if vis is None or vis.empty else vis.to_dict("records")
    home = game.get("home_team_id") if game else ""
    away = game.get("away_team_id") if game else ""
    by_team = {str(r.get("team_id") or ""): r for r in rows}
    data = {
        "home": by_team.get(str(home or ""), None),
        "away": by_team.get(str(away or ""), None),
        "in_game": {
            "home_score": None if latest_pbp is None else latest_pbp.get("home_score"),
            "away_score": None if latest_pbp is None else latest_pbp.get("away_score"),
        },
    }
    status = "REAL" if rows or latest_pbp is not None else "PARTIAL"
    return section(status, data)
