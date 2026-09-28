"""Rebuild V5 panel in memory. Score only from persisted V6 maps. No m0_m1."""

from __future__ import annotations

import json

import pandas as pd

from dre_v5 import splits as V5S
from dre_v5 import state_panel as SP
from dre_v5.possession_remaining import build_priors
from dre_v6 import maps as V6M

from . import config as C


def load_v6_maps() -> dict:
    path = C.V6_OUT / "02_train_frozen_m0_m1.json"
    if not path.exists():
        raise RuntimeError("HALT: V6 persisted maps missing. Do not fit.")
    obj = json.loads(path.read_text())
    return obj


def maps_for_score(obj: dict) -> dict:
    return {"m0": obj["m0"], "m1": obj["m1"], "global_mean": float(obj["global_mean"])}


def rebuild_panel() -> tuple[pd.DataFrame, dict, dict]:
    poss = pd.read_parquet(
        C.PADE_OUT / "03_possessions.parquet",
        columns=[
            "nba_game_id",
            "possession_id",
            "possession_index",
            "period",
            "game_clock_start",
            "elapsed_game_seconds_start",
            "game_seconds_remaining_start",
            "wall_start_ts",
            "wall_end_ts",
            "offensive_team",
            "score_home_start",
            "score_away_start",
        ],
    )
    pade_panel = pd.read_parquet(
        C.PADE_OUT / "05_trade_possession_panel.parquet",
        columns=["trade_id", "nba_game_id", "dataset_split", "game_date", "A1_team", "A2_team"],
    )
    priors, pace = build_priors(poss, pade_panel)
    df = SP.build_panel(priors)
    counts = SP.panel_counts(df)
    if counts["rows"] != C.PANEL_ROWS_EXPECTED or counts["trades"] != C.PANEL_TRADES_EXPECTED:
        raise RuntimeError(f"HALT: panel counts {counts}")
    split_audit = V5S.audit_splits(df)
    if split_audit["status"] != "PASS":
        raise RuntimeError(f"HALT: split overlap {split_audit}")
    for s, n in C.SPLIT_GAMES_EXPECTED.items():
        if (split_audit.get("games") or {}).get(s) != n:
            raise RuntimeError(f"HALT: split games {split_audit}")
    by_split = {
        s: {
            "rows": int((df["dataset_split"] == s).sum()),
            "trades": int(df.loc[df["dataset_split"] == s, "trade_id"].nunique()),
            "games": int(df.loc[df["dataset_split"] == s, "event_id"].nunique()),
        }
        for s in C.SPLITS
    }
    prov = {
        "builders": ["dre_v5.possession_remaining.build_priors", "dre_v5.state_panel.build_panel"],
        "reproduce_v5_exactly": True,
        "quietly_improved": False,
        "m0_m1_calls": 0,
        "n_hat_tertiles_train": df.attrs.get("n_hat_tertiles_train"),
        "row_counts_before_scoring": {"total": counts, "by_split": by_split},
        "causal_note": (
            "Priors use completion-before-start pace and TRAIN league-mean fallback. "
            "V7 documents the frozen V5 process; it does not claim a newly cleaned causal pipeline."
        ),
        "pace": pace,
        "splits": split_audit,
    }
    return df, counts, prov


def score_row(r, maps: dict) -> tuple[float, float, str, bool]:
    p = r.get("price_bin_5")
    key = V6M.m1_key(p, r.get("score_bin_l1"), r.get("clock_bin_l1"), r.get("n_hat_bin_l1"))
    exists = key in maps["m1"]
    if exists:
        a1 = float(maps["m1"][key])
        path = "M1_EXACT"
    else:
        pk = V6M.price_key(p)
        if pk in maps["m0"]:
            a1 = float(maps["m0"][pk])
            path = "M0_FALLBACK"
        else:
            a1 = float(maps["global_mean"])
            path = "GLOBAL_FALLBACK"
    a0 = V6M.predict_m0(p, maps)
    return a0, a1, path, exists


def attach_scores(df: pd.DataFrame, maps: dict) -> pd.DataFrame:
    recs = df.to_dict("records")
    a0, a1, path, exists, keys = [], [], [], [], []
    for r in recs:
        x0, x1, pth, ex = score_row(r, maps)
        a0.append(x0)
        a1.append(x1)
        path.append(pth)
        exists.append(ex)
        keys.append(V6M.m1_key(r.get("price_bin_5"), r.get("score_bin_l1"), r.get("clock_bin_l1"), r.get("n_hat_bin_l1")))
    out = df.copy()
    out["m1_key"] = keys
    out["alpha_m0"] = a0
    out["alpha_m1"] = a1
    out["da_state"] = out["alpha_m1"] - out["alpha_m0"]
    out["r_t"] = out["pi_terminal"] - out["alpha_m0"]
    out["SCORING_PATH"] = path
    out["EXACT_CELL_EXISTS"] = exists
    return out
