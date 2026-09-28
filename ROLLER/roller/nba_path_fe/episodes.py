"""First-touch-80 episodes. One per (game, market, side). All periods stored."""

from __future__ import annotations

import pandas as pd

from roller.nba_path_fe.config import DEFAULT, PathFeConfig
from roller.nba_path_fe.errors import PathFeError
from roller.nba_path_fe.mathutil import episode_id


def build_episodes(ticks: pd.DataFrame, games: pd.DataFrame, cfg: PathFeConfig = DEFAULT) -> pd.DataFrame:
    if ticks.empty:
        raise PathFeError("DATA_REQUIRED", "no ticks")
    rows: list[dict] = []
    for (game_id, market_id, side), g in ticks.sort_values("t").groupby(
        ["game_id", "market_id", "side"], sort=False
    ):
        prev = None
        hit = None
        for rec in g.itertuples(index=False):
            bid = int(rec.yes_bid)
            if prev is not None and int(prev) < 80 <= bid:
                hit = rec
                break
            if prev is None and bid >= 80:
                hit = rec
                break
            prev = bid
        if hit is None:
            continue
        game = games.loc[games["game_id"] == game_id].iloc[0]
        rest_col = "rest_home" if side == "home" else "rest_away"
        rest = int(game[rest_col]) if rest_col in game.index and pd.notna(game[rest_col]) else 0
        opp = getattr(hit, "opposite_market_id", None)
        rows.append(
            {
                "episode_id": episode_id(str(game_id), str(market_id), str(side), str(hit.timestamp_utc)),
                "game_id": str(game_id),
                "market_id": str(market_id),
                "opposite_market_id": None if pd.isna(opp) else str(opp),
                "side": str(side),
                "era": str(hit.era),
                "season": int(hit.season),
                "timestamp_utc": str(hit.timestamp_utc),
                "t_s": int(hit.t),
                "period": None if pd.isna(getattr(hit, "period", None)) else int(hit.period),
                "sec_left_period": None if pd.isna(getattr(hit, "sec_left_period", None)) else int(hit.sec_left_period),
                "sec_left_game": None if pd.isna(getattr(hit, "sec_left_game", None)) else int(hit.sec_left_game),
                "p_ts": int(hit.yes_bid),
                "yes_ask": None if pd.isna(hit.yes_ask) else int(hit.yes_ask),
                "spread_own": None if pd.isna(hit.spread) else float(hit.spread),
                "size_own_bid": None if pd.isna(hit.size_bid) else float(hit.size_bid),
                "home_score": None if pd.isna(getattr(hit, "home_score", None)) else int(hit.home_score),
                "away_score": None if pd.isna(getattr(hit, "away_score", None)) else int(hit.away_score),
                "possession": None if pd.isna(hit.possession) else int(hit.possession),
                "rest_days": rest,
                "impulse_style": int(getattr(hit, "impulse_style", 0) or 0),
                "thin_style": int(getattr(hit, "thin_style", 0) or 0),
                "source": str(hit.source),
                "book_source": str(hit.book_source),
                "tip_utc": str(game["tip_utc"]) if pd.notna(game.get("tip_utc")) else str(hit.timestamp_utc),
                "winner_side": None if pd.isna(game.get("winner_side")) else str(game["winner_side"]),
            }
        )
    ep = pd.DataFrame(rows)
    if ep.empty:
        raise PathFeError("DATA_REQUIRED", "no first-touch-80 episodes")
    if cfg.q2_policy_filter:
        ep = ep.loc[ep["period"] == 2].copy()
    return ep.reset_index(drop=True)


def opposite_market_id(market_id: str, lookup: dict[str, str] | None = None) -> str:
    if lookup and market_id in lookup:
        return lookup[market_id]
    if market_id.endswith("-home"):
        return market_id[: -len("home")] + "away"
    if market_id.endswith("-away"):
        return market_id[: -len("away")] + "home"
    raise PathFeError("EPISODE_INVALID", f"cannot map opposite {market_id}")
