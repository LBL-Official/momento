from __future__ import annotations

import pandas as pd

TRAIN_END = "2025-02-28"
FROZEN_TEST_SEASON = "2025-2026"


def assign_split(game_date: str, season: str, train_end: str = TRAIN_END) -> str:
    if str(season) == FROZEN_TEST_SEASON or str(season).startswith("2025-26"):
        return "TEST_FROZEN"
    gd = str(game_date or "")[:10]
    if gd <= train_end:
        return "TRAIN"
    return "VAL"


def add_split(df: pd.DataFrame, train_end: str = TRAIN_END) -> pd.DataFrame:
    out = df.copy()
    season = out["season"] if "season" in out.columns else ""
    out["split"] = [
        assign_split(d, s, train_end)
        for d, s in zip(out.get("game_date", ""), season if isinstance(season, pd.Series) else [""] * len(out))
    ]
    return out


def assert_no_test_in_fit(df: pd.DataFrame) -> None:
    if "split" not in df.columns:
        return
    if (df["split"] == "TEST_FROZEN").any():
        raise RuntimeError("2025-26 TEST_FROZEN rows must not enter model fitting")


def fit_mask(df: pd.DataFrame) -> pd.Series:
    return df["split"] == "TRAIN"


def val_mask(df: pd.DataFrame) -> pd.Series:
    return df["split"] == "VAL"
