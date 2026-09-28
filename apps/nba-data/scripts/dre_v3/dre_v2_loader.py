"""Read-only DRE V2 state + predictions."""

from __future__ import annotations

import pandas as pd

from . import config as C


def load_v2_predictions() -> pd.DataFrame:
    path = C.V2_OUT / "09_predictions" / "state_predictions.parquet"
    return pd.read_parquet(path)


def load_v2_gate_a() -> dict:
    import json

    return json.loads((C.V2_OUT / "02_frozen_universe" / "gate_a.json").read_text())
