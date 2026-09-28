"""Read-only PADE V1 loader for forward-path labels."""

from __future__ import annotations

import pandas as pd

from . import config as C

LABEL_COLS = [
    "trade_id",
    "possession_index",
    "future_min_5",
    "future_max_5",
    "future_min_10",
    "future_max_10",
    "future_min_end",
    "future_max_end",
    "recovery_from_current_5",
    "recovery_from_current_10",
    "recovery_from_current_end",
    "future_deterioration_5",
    "future_deterioration_10",
    "future_deterioration_end",
    "y_jump_40",
    "jump_label_kind",
]


def load_forward_labels() -> pd.DataFrame:
    path = C.PADE_OUT / "05_trade_possession_panel.parquet"
    df = pd.read_parquet(path, columns=LABEL_COLS)
    return df
