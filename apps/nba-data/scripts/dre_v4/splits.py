"""Game-level chronological isolation inherited from PADE / DRE V2."""

from __future__ import annotations

import pandas as pd


def audit_splits(df: pd.DataFrame) -> dict:
    by = df.groupby("event_id")["dataset_split"].nunique()
    overlap = int((by > 1).sum())
    games = {s: int(df.loc[df["dataset_split"] == s, "event_id"].nunique()) for s in ("TRAIN", "VALIDATION", "OOS")}
    trades = {s: int(df.loc[df["dataset_split"] == s, "trade_id"].nunique()) for s in ("TRAIN", "VALIDATION", "OOS")}
    return {
        "gate": "H",
        "status": "PASS" if overlap == 0 else "FAIL",
        "overlap_games": overlap,
        "games": games,
        "trades": trades,
        "rule": "game-level chronological isolation inherited from DRE V2 / FIRST-80",
    }
