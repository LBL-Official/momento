"""Human-readable event path. Future columns are labeled as future."""

from __future__ import annotations

from typing import Any

import pandas as pd

from roller.nba_8040_reverse_features.bars import _parse_utc, split_pre_post
from roller.nba_8040_reverse_features.catalog import FUTURE, POST
from roller.nba_8040_reverse_features.locks import event_path_path


def build_event_path(
    instances: list[dict[str, Any]],
    features: pd.DataFrame,
    labels: pd.DataFrame,
    bars: dict,
) -> pd.DataFrame:
    feat = features.set_index("instance_id")
    lab = labels.set_index("instance_id")
    rows = []
    for instance in instances:
        iid = instance["instance_id"]
        frow = feat.loc[iid]
        lrow = lab.loc[iid]
        entry = _parse_utc(instance["timestamp_utc"])
        pre, post = split_pre_post(bars.get(instance["ticker"], []), entry) if entry else ([], [])
        after = {1: None, 3: None, 5: None}
        if entry is not None:
            for minutes in after:
                found = [close for stamp, close in post if (stamp - entry).total_seconds() <= minutes * 60]
                after[minutes] = found[-1] if found else None
        rows.append(
            {
                "instance_id": iid,
                "game": f"{instance['away_team']} @ {instance['home_team']}",
                "period": instance["period"],
                "timestamp_80": instance["timestamp_utc"],
                "game_clock_80": instance["game_clock"],
                "price_at_80": instance["entry_bid_cents"],
                "score_at_80": f"{instance['score_home']}-{instance['score_away']}",
                "margin_at_80": instance["bought_margin"],
                "opening_price": instance["pregame_cents"],
                "price_1m_before": frow.get("close_1m_before"),
                "price_3m_before": frow.get("close_3m_before"),
                "price_5m_before": frow.get("close_5m_before"),
                "price_10m_before": frow.get("close_10m_before"),
                "price_1m_after": after[1],
                "price_3m_after": after[3],
                "price_5m_after": after[5],
                "t40": lrow["t40"],
                "time_to_40": lrow["time_to_40"],
                "min_after": lrow["min_after"],
                "max_after": lrow["max_after"],
                "terminal_yes": lrow["terminal_yes"],
                "exit_period": instance["exit_period"],
                "exit_game_clock": instance["exit_game_clock"],
                "future_namespace": f"{FUTURE}|{POST}",
            }
        )
    return pd.DataFrame(rows)


def write_event_path(frame: pd.DataFrame) -> None:
    path = event_path_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
