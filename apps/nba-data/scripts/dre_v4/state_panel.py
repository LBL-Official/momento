"""Join frozen PADE panel with V2 comparison probabilities. As-of features only."""

from __future__ import annotations

import json

import pandas as pd

from . import config as C
from .labels import attach_path_classes, attach_walk_labels


PADE_KEEP = [
    "trade_id",
    "event_id",
    "nba_game_id",
    "market_ticker",
    "dataset_split",
    "game_date",
    "entry_timestamp",
    "possession_index",
    "possessions_since_entry",
    "period",
    "game_clock",
    "elapsed_game_seconds",
    "game_seconds_remaining",
    "position_age_wall_s",
    "is_A1_team_offense",
    "score_differential_from_A1",
    "current_price",
    "A1_yes_bid",
    "A1_yes_ask",
    "A1_mid",
    "deterioration_absolute",
    "max_deterioration_since_entry",
    "current_price_rank_since_entry",
    "market_observation_timestamp",
    "market_age_seconds",
    "alignment_confidence",
    "unique_market_observations_v1",
    "v_3",
    "v_5",
    "a_short",
    "market_volatility",
    "rolling_range_5",
    "estimated_possessions_remaining_r1",
    "actual_remaining_possessions",
    "y_settle_yes",
    "y_min_le_40_k5",
    "y_jump_40",
    "jump_label_kind",
]
for hz in ("1", "3", "5", "10", "end"):
    PADE_KEEP += [f"future_min_{hz}", f"future_max_{hz}"]
    if hz != "end":
        PADE_KEEP += [f"future_deterioration_{hz}", f"recovery_from_current_{hz}"]
    else:
        PADE_KEEP += ["future_deterioration_end", "recovery_from_current_end"]


V2_KEEP = [
    "trade_id",
    "possession_index",
    "real_time_timestamp",
    "p_settle_M3",
    "p_rec10_k5_M3",
    "p_det10_end_M3",
    "current_price_e4",
    "spread_e4",
]


def build_panel() -> pd.DataFrame:
    pade = pd.read_parquet(C.PADE_OUT / "05_trade_possession_panel.parquet", columns=PADE_KEEP)
    v2 = pd.read_parquet(C.V2_OUT / "09_predictions" / "state_predictions.parquet", columns=V2_KEEP)
    df = pade.merge(v2, on=["trade_id", "possession_index"], how="left")
    if int(df.groupby(["trade_id", "possession_index"]).ngroups) != int(len(df)):
        raise RuntimeError("state panel duplicated (trade_id, possession_index)")
    if len(df) != C.PANEL_ROWS_EXPECTED:
        raise RuntimeError(f"panel rows {len(df)} != {C.PANEL_ROWS_EXPECTED}")
    df["current_yes_bid"] = df["A1_yes_bid"]
    df["current_yes_ask"] = df["A1_yes_ask"]
    df["deterioration_cents"] = pd.to_numeric(df["deterioration_absolute"], errors="coerce")
    df["max_dd_since_entry"] = pd.to_numeric(df["max_deterioration_since_entry"], errors="coerce")
    df["recovery_from_trough"] = df["max_dd_since_entry"] - df["deterioration_cents"]
    df["unique_market_obs"] = pd.to_numeric(df["unique_market_observations_v1"], errors="coerce")
    df["stale_market"] = (pd.to_numeric(df["market_age_seconds"], errors="coerce") >= 60).astype(float)
    df["est_remaining_r1"] = pd.to_numeric(df["estimated_possessions_remaining_r1"], errors="coerce")
    df["is_A1_team_offense"] = df["is_A1_team_offense"].map(
        lambda x: 1 if x is True or x == 1 else (0 if x is False or x == 0 else None)
    )
    df["y_jump_40_kind"] = "CANDLE_PATH_PROXY"
    df = attach_walk_labels(df)
    df = attach_path_classes(df)
    df["regime"] = _asof_regime(df)
    return df


def _asof_regime(df: pd.DataFrame) -> list[str]:
    # Pre-registered as-of thresholds. Not tuned on OOS.
    out = []
    for age, det, rec, rng in zip(
        pd.to_numeric(df["market_age_seconds"], errors="coerce"),
        df["deterioration_cents"],
        df["recovery_from_trough"],
        pd.to_numeric(df["rolling_range_5"], errors="coerce"),
    ):
        if pd.notna(age) and age >= 60:
            out.append("STALE_MARKET")
        elif pd.notna(det) and det >= 20:
            out.append("SEVERELY_DRAWDOWN")
        elif pd.notna(det) and det >= 10:
            out.append("DETERIORATING")
        elif pd.notna(rec) and rec >= 5 and (pd.isna(det) or det < 10):
            out.append("RECOVERING")
        elif pd.notna(rng) and rng >= 10:
            out.append("HIGH_VOLATILITY")
        else:
            out.append("STABLE")
    return out


def universe_accounting(df: pd.DataFrame, gate_a: dict) -> dict:
    unresolved = json.loads((C.V2_OUT / "14_diagnostics" / "unresolved.json").read_text())
    return {
        "universe": C.UNIVERSE_N,
        "matched_known": C.UNIVERSE_N - 7,
        "panel_eligible": int(df["trade_id"].nunique()),
        "panel_rows": int(len(df)),
        "model_eligible_rows": int(df["current_price"].notna().sum()),
        "path_label_eligible_end": int(df["path_valid_end"].sum()),
        "unresolved_n": unresolved["unresolved_n"],
        "unresolved": unresolved["unresolved"],
        "note": "UNRESOLVED ≠ MODEL-ELIGIBLE. Universe remains 1230.",
        "frozen_first80": gate_a.get("observed"),
    }


def panel_counts(df: pd.DataFrame) -> dict:
    return {
        "rows": int(len(df)),
        "trades": int(df["trade_id"].nunique()),
        "games": int(df["event_id"].nunique()),
        "splits": {
            s: {
                "rows": int((df["dataset_split"] == s).sum()),
                "trades": int(df.loc[df["dataset_split"] == s, "trade_id"].nunique()),
                "games": int(df.loc[df["dataset_split"] == s, "event_id"].nunique()),
            }
            for s in ("TRAIN", "VALIDATION", "OOS")
        },
    }
