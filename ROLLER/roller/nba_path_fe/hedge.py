"""Family E. Post-entry only. Never imported by enter_skip."""

from __future__ import annotations

import numpy as np
import pandas as pd

from roller.nba_path_fe.config import DEFAULT, PathFeConfig
from roller.nba_path_fe.episodes import opposite_market_id
from roller.nba_path_fe.errors import PathFeError


def build_hedge_features(
    episodes: pd.DataFrame,
    ticks: pd.DataFrame,
    labels: pd.DataFrame,
    cfg: PathFeConfig = DEFAULT,
) -> pd.DataFrame:
    rows: list[dict] = []
    for rec in episodes.itertuples(index=False):
        lab = labels.loc[labels["episode_id"] == rec.episode_id]
        if lab.empty or int(lab.iloc[0]["filled"]) != 1:
            continue
        fill_t = lab.iloc[0]["fill_t"]
        if pd.isna(fill_t):
            continue
        fill_t = int(fill_t)
        path = ticks.loc[
            (ticks["game_id"] == rec.game_id)
            & (ticks["market_id"] == rec.market_id)
            & (ticks["t"] >= fill_t)
        ].sort_values("t")
        first55 = None
        for r in path.itertuples(index=False):
            if int(r.yes_bid) <= 55:
                first55 = r
                break
        opp_id = None if pd.isna(getattr(rec, "opposite_market_id", None)) else str(rec.opposite_market_id)
        if opp_id is None:
            try:
                opp_id = opposite_market_id(str(rec.market_id))
            except PathFeError:
                opp_id = None
        spread_opp = np.nan
        size_opp = np.nan
        restable = 0
        minutes = np.nan
        if first55 is not None and opp_id is not None:
            minutes = float(int(first55.t) - fill_t)
            opp = ticks.loc[
                (ticks["game_id"] == rec.game_id)
                & (ticks["market_id"] == opp_id)
                & (ticks["t"] == int(first55.t))
            ]
            if not opp.empty:
                o = opp.iloc[0]
                spread_opp = np.nan if pd.isna(o["spread"]) else float(o["spread"])
                size_opp = np.nan if pd.isna(o["size_bid"]) else float(o["size_bid"])
                opp_bid = int(o["yes_bid"])
                restable = int(
                    cfg.hedge_lo <= opp_bid <= cfg.hedge_hi
                    and np.isfinite(spread_opp)
                    and spread_opp <= 6.0
                    and np.isfinite(size_opp)
                    and size_opp >= 5.0
                )
        rows.append(
            {
                "episode_id": rec.episode_id,
                "game_id": rec.game_id,
                "hedge_spread_opp": spread_opp,
                "hedge_size_opp_bid": size_opp,
                "hedge_minutes_to_first_55": minutes,
                "hedge_restable_38_42": float(restable) if first55 is not None else np.nan,
            }
        )
    return pd.DataFrame(rows)
