"""League/season/date/ticker/game partition map."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from roller.research_query.facts import TradableIndex

UNIVERSE_NAME = "universe.parquet"


def write_universe(
    path: Path,
    index: TradableIndex,
    league: str,
    season: str,
    *,
    games: list[dict[str, Any]] | None = None,
) -> int:
    p5_by_game: dict[str, str] = {}
    for game in games or []:
        gid = str(game.get("internal_game_id") or game.get("game_id") or "")
        if gid and game.get("p5_vs_p5") not in (None, ""):
            p5_by_game[gid] = str(game.get("p5_vs_p5"))
    rows: list[dict[str, Any]] = []
    for ticker, bars in index.bars.items():
        if not bars:
            continue
        gid = bars[0].game_id
        rows.append(
            {
                "ticker": ticker,
                "game_id": gid,
                "league": league,
                "season": season,
                "first_ts": bars[0].ts.isoformat().replace("+00:00", "Z"),
                "last_ts": bars[-1].ts.isoformat().replace("+00:00", "Z"),
                "bar_count": len(bars),
                "p5_vs_p5": p5_by_game.get(gid),
                "team_side": (bars[0].raw or {}).get("team_side"),
            }
        )
    pd.DataFrame(rows).to_parquet(path, index=False)
    return len(rows)


def read_universe(path: Path) -> list[dict[str, Any]]:
    df = pd.read_parquet(path)
    return df.to_dict("records") if not df.empty else []
