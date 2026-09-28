"""Outcome labels. Isolated from the pre-80 feature store."""

from __future__ import annotations

from typing import Any

import pandas as pd

from roller.nba_8040_reverse_features.bars import _parse_utc, load_ticker_bars, split_pre_post
from roller.nba_8040_reverse_features.errors import ReverseFeaturesError
from roller.nba_8040_reverse_features.instances import load_instances
from roller.choosin_texas.locks import loss_cents_for_stop
from roller.nba_8040_reverse_features.locks import GAIN_CENTS, LOSS_CENTS, NBA_Q2Q3_N, labels_path


def target(instance: dict[str, Any], stop_cents: int = 40) -> dict[str, Any]:
    """Outcome for a stop. Features do not call this. v1 analysis uses 40 only."""
    post = int(instance["post_entry_min"])
    t_stop = post <= int(stop_cents)
    survive = not t_stop
    loss = loss_cents_for_stop(int(stop_cents))
    return {
        "stop_cents": int(stop_cents),
        "t_stop": t_stop,
        "s": survive,
        "ev_contribution": GAIN_CENTS if survive else -int(loss),
    }


def _time_to_40(instance: dict[str, Any]) -> float | None:
    if not instance["t40"]:
        return None
    start = _parse_utc(instance["timestamp_utc"])
    end = _parse_utc(instance["exit_timestamp_utc"])
    if start is None or end is None:
        return None
    return (end - start).total_seconds()


def build_labels(
    instances: list[dict[str, Any]] | None = None,
    bars: dict | None = None,
) -> pd.DataFrame:
    rows = instances if instances is not None else load_instances()
    if bars is None:
        bars = load_ticker_bars({row["ticker"] for row in rows})
    out: list[dict[str, Any]] = []
    for instance in rows:
        entry_ts = _parse_utc(instance["timestamp_utc"])
        if entry_ts is None:
            raise ReverseFeaturesError("DATA_REQUIRED", f"bad timestamp {instance['ticker']}")
        _pre, post = split_pre_post(bars.get(instance["ticker"], []), entry_ts)
        post_closes = [close for _stamp, close in post]
        t40 = bool(instance["t40"])
        win = bool(instance["w"])
        survive = not t40
        hit_90 = None
        min_after = None
        max_after = None
        if post_closes:
            hit_90 = any(close >= 90 for close in post_closes)
            min_after = min(post_closes)
            max_after = max(post_closes)
        out.append(
            {
                "instance_id": instance["instance_id"],
                "period": instance["period"],
                "season_phase": instance["season_phase"],
                "dataset_split": instance["dataset_split"],
                "regular_season": instance["regular_season"],
                "t40": t40,
                "s": survive,
                "w": win,
                "w_and_t40": t40 and win,
                "l_and_t40": t40 and not win,
                "terminal_yes": bool(instance["terminal_yes"]),
                "post_entry_min": int(instance["post_entry_min"]),
                "ev_contribution": GAIN_CENTS if survive else -LOSS_CENTS,
                "time_to_40": _time_to_40(instance),
                "hit_90": hit_90,
                "min_after": min_after,
                "max_after": max_after,
            }
        )
    frame = pd.DataFrame(out)
    if len(frame) != NBA_Q2Q3_N:
        raise ReverseFeaturesError("LOCK_MISMATCH", "label N mismatch")
    return frame


def write_labels(frame: pd.DataFrame) -> None:
    path = labels_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
