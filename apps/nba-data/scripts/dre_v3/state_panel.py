"""Join frozen DRE V2 state with PADE forward labels. As-of features only."""

from __future__ import annotations

import pandas as pd

from . import config as C
from .dre_v2_loader import load_v2_predictions
from .forward_paths import add_path_bins
from .pade_loader import load_forward_labels


def build_panel() -> pd.DataFrame:
    v2 = load_v2_predictions()
    lab = load_forward_labels()
    df = v2.merge(lab, on=["trade_id", "possession_index"], how="left", suffixes=("", "_pade"))
    if "y_jump_40_pade" in df.columns:
        df["y_jump_40"] = df["y_jump_40"].fillna(df["y_jump_40_pade"])
    if int(df.groupby(["trade_id", "possession_index"]).ngroups) != int(len(df)):
        raise RuntimeError("state panel duplicated (trade_id, possession_index)")
    df = add_path_bins(df)
    df["entry_price"] = C.ENTRY_CENTS
    df["is_A1_team_offense"] = df["is_A1_team_offense"].map(
        lambda x: 1 if x is True or x == 1 else (0 if x is False or x == 0 else None)
    )
    return df


def panel_counts(df: pd.DataFrame) -> dict:
    return {
        "rows": int(len(df)),
        "trades": int(df["trade_id"].nunique()),
        "games": int(df["event_id"].nunique()),
        "splits": {
            s: {
                "rows": int((df["dataset_split"] == s).sum()),
                "trades": int(df.loc[df["dataset_split"] == s, "trade_id"].nunique()),
            }
            for s in ("TRAIN", "VALIDATION", "OOS")
        },
        "path_valid_end": int(df["path_valid_end"].sum()),
        "path_invalid_end": int((~df["path_valid_end"]).sum()),
    }
