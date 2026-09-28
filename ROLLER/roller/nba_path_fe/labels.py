"""Filled-episode labels. Y = 1{S=1} · 1{M>40}. Unfilled is not a skip."""

from __future__ import annotations

import numpy as np
import pandas as pd

from roller.nba_path_fe.config import DEFAULT, PathFeConfig
from roller.nba_path_fe.errors import PathFeError


def build_labels(
    episodes: pd.DataFrame,
    ticks: pd.DataFrame,
    cfg: PathFeConfig = DEFAULT,
) -> pd.DataFrame:
    rng = np.random.default_rng(cfg.seed + 7)
    rows: list[dict] = []
    for rec in episodes.itertuples(index=False):
        path = ticks.loc[
            (ticks["game_id"] == rec.game_id)
            & (ticks["market_id"] == rec.market_id)
            & (ticks["t"] >= int(rec.t_s))
        ].sort_values("t")
        if path.empty:
            raise PathFeError("DATA_REQUIRED", f"empty path {rec.episode_id}")
        bids = path["yes_bid"].astype(int).to_numpy()
        # fill: first print in [78,82] before chase 89, after t_s inclusive
        filled = False
        fill_px = None
        fill_t = None
        min_after = int(bids[0])
        hit40 = False
        t40 = None
        first55 = None
        warehouse = "SYNTHETIC" not in str(rec.source)
        fill_chance = 1.0 if warehouse else cfg.fill_rate
        for i, px in enumerate(bids):
            t = int(path.iloc[i]["t"])
            min_after = min(min_after, int(px))
            if not filled:
                if int(px) >= cfg.chase:
                    break
                if cfg.entry_lo <= int(px) <= cfg.entry_hi:
                    if warehouse or rng.random() <= fill_chance:
                        filled = True
                        fill_px = int(px)
                        fill_t = t
            if filled:
                if first55 is None and int(px) <= 55:
                    first55 = t
                if int(px) <= cfg.bail:
                    hit40 = True
                    t40 = t
                    break
        if rec.winner_side is None or pd.isna(rec.winner_side):
            s = None
        else:
            s = 1 if rec.side == rec.winner_side else 0
        m_min = int(min_after) if filled else None
        y = None
        if filled and s is not None:
            y = int(s == 1 and (not hit40) and (m_min is not None and m_min > cfg.bail))
        rows.append(
            {
                "episode_id": rec.episode_id,
                "game_id": rec.game_id,
                "filled": int(filled),
                "fill_px": fill_px,
                "fill_t": fill_t,
                "S": s,
                "hit40": int(hit40) if filled else None,
                "t40": t40,
                "M": m_min,
                "Y": y,
                "first_touch_55_t": first55,
                "label_source": "candle_path_proxy" if warehouse else "synthetic_path",
            }
        )
    lab = pd.DataFrame(rows)
    filled = lab.loc[lab["filled"] == 1]
    if filled.empty:
        raise PathFeError("DATA_REQUIRED", "no filled episodes")
    return lab
