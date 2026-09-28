"""Machine-test: ticks after t_s must not change enter/skip features."""

from __future__ import annotations

import numpy as np
import pandas as pd

from roller.nba_path_fe.config import DEFAULT, PathFeConfig
from roller.nba_path_fe.errors import PathFeError
from roller.nba_path_fe.features import build_enter_features
from roller.nba_path_fe.registry import enter_skip_names


def assert_no_post_ts_leakage(
    episodes: pd.DataFrame,
    ticks: pd.DataFrame,
    labels: pd.DataFrame,
    cfg: PathFeConfig = DEFAULT,
) -> dict:
    feat_a, _ = build_enter_features(episodes, ticks, labels, cfg)
    cols = [c for c in enter_skip_names() if c in feat_a.columns]
    checked = 0
    scrambled = 0
    # Per episode: only that market's ticks after its own t_s.
    sample = episodes
    if len(sample) > 24:
        sample = episodes.iloc[:: max(1, len(episodes) // 24)].head(24)
    for rec in sample.itertuples(index=False):
        dirty = ticks.copy()
        hit = (
            (dirty["game_id"] == rec.game_id)
            & (dirty["market_id"] == rec.market_id)
            & (dirty["t"] > int(rec.t_s))
        )
        n = int(hit.sum())
        if n == 0:
            continue
        dirty.loc[hit, "yes_bid"] = 1
        dirty.loc[hit, "yes_ask"] = 99
        dirty.loc[hit, "spread"] = 50.0
        dirty.loc[hit, "size_bid"] = 0.0
        dirty.loc[hit, "home_score"] = 0
        dirty.loc[hit, "away_score"] = 0
        feat_b, _ = build_enter_features(episodes, dirty, labels, cfg)
        a = feat_a.loc[feat_a["episode_id"] == rec.episode_id, cols].iloc[0]
        b = feat_b.loc[feat_b["episode_id"] == rec.episode_id, cols].iloc[0]
        diffs = []
        for c in cols:
            av, bv = a[c], b[c]
            if pd.isna(av) and pd.isna(bv):
                continue
            if not np.isclose(av, bv, rtol=0, atol=1e-9, equal_nan=True):
                diffs.append(c)
        if diffs:
            raise PathFeError(
                "LEAKAGE_FAIL",
                f"{rec.episode_id} enter_skip changed after own post-t_s scramble: {diffs}",
            )
        checked += 1
        scrambled += n
    if checked == 0:
        raise PathFeError("LEAKAGE_TEST_INVALID", "no post-t_s ticks to scramble")
    return {"ok": True, "n_episodes_checked": checked, "n_scrambled_ticks": scrambled, "columns_checked": cols}
