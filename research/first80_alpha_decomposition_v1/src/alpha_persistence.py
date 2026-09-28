"""Walk-forward conditional calibration. F is estimated, never observed directly."""

from __future__ import annotations

import pandas as pd
import pyarrow.parquet as pq

import config as C
import stats_util as S


def _price_bin(cents) -> int | None:
    if cents is None or pd.isna(cents):
        return None
    x = float(cents)
    if x < 0:
        return None
    return int(x // 5) * 5


def _clock_bin(rem) -> str | None:
    if rem is None or pd.isna(rem):
        return None
    x = float(rem)
    if x <= 720:
        return "LE12MIN"
    if x <= 1440:
        return "12-24"
    if x <= 2160:
        return "24-36"
    return "EARLY"


def _score_bin(sd) -> str | None:
    if sd is None or pd.isna(sd):
        return None
    x = float(sd)
    if x >= 10:
        return "LEAD10+"
    if x >= 1:
        return "LEAD"
    if x <= -10:
        return "TRAIL10+"
    if x <= -1:
        return "TRAIL"
    return "TIE"


def load_pade_states(df80: pd.DataFrame) -> pd.DataFrame:
    """Possession-aligned post-entry states. Drop games not in PADE. No future_* labels."""
    panel = pq.read_table(
        C.PADE / "05_trade_possession_panel.parquet",
        columns=[
            "event_id",
            "market_ticker",
            "dataset_split",
            "expiration_result_yes",
            "A1_yes_bid",
            "period",
            "game_seconds_remaining",
            "score_differential_from_A1",
            "possessions_since_entry",
            "market_observation_timestamp",
        ],
    ).to_pandas()
    panel["dataset_split"] = [C.canon_split(s) for s in panel["dataset_split"]]
    keep_ids = set(df80["event_id"])
    panel = panel[panel["event_id"].isin(keep_ids)].copy()
    panel = panel[panel["possessions_since_entry"].fillna(-1) >= 0]
    panel["W"] = panel["expiration_result_yes"].astype(bool)
    panel["K_cents"] = pd.to_numeric(panel["A1_yes_bid"], errors="coerce")
    panel["price_bin"] = [_price_bin(v) for v in panel["K_cents"]]
    panel["clock_bin"] = [_clock_bin(v) for v in panel["game_seconds_remaining"]]
    panel["score_bin"] = [_score_bin(v) for v in panel["score_differential_from_A1"]]
    panel["period_bin"] = [
        None if pd.isna(v) else ("OT" if int(v) >= 5 else str(int(v))) for v in panel["period"]
    ]
    panel["bucket"] = [
        f"{a}|{b}|{c}|{d}"
        for a, b, c, d in zip(panel["price_bin"], panel["period_bin"], panel["clock_bin"], panel["score_bin"])
    ]
    return panel


def estimate_f(train: pd.DataFrame) -> dict[str, float]:
    """Trade-balanced: one terminal outcome per event_id inside each bucket."""
    f = {}
    for b, g in train.groupby("bucket"):
        # unique games in bucket
        gg = g.drop_duplicates("event_id")
        if len(gg) < 20:
            continue
        f[b] = float(gg["W"].mean())
    return f


def eval_alpha(test: pd.DataFrame, fmap: dict[str, float]) -> dict:
    """Mean (Fhat - K) at the observation row. K in probability units. No self-outcome in Fhat."""
    sub = test[test["bucket"].isin(fmap)].copy()
    if not len(sub):
        return {"n_rows": 0, "n_games": 0, "mean_alpha": None}
    sub["Fhat"] = sub["bucket"].map(fmap)
    sub["K"] = sub["K_cents"] / 100.0
    sub["alpha"] = sub["Fhat"] - sub["K"]
    # trade-balanced: mean alpha per game then across games
    per = sub.groupby("event_id")["alpha"].mean()
    return {
        "n_rows": int(len(sub)),
        "n_games": int(len(per)),
        "n_buckets_used": int(sub["bucket"].nunique()),
        "mean_alpha_row": float(sub["alpha"].mean()),
        "mean_alpha_trade_balanced": float(per.mean()),
        "frac_Fhat_gt_K": float((sub["alpha"] > 0).mean()),
        "note": "Fhat is TRAIN-only bucket frequency. Not observed fair value. Not a fill.",
    }


def run(df80: pd.DataFrame) -> dict:
    panel = load_pade_states(df80)
    n_games_panel = int(panel["event_id"].nunique())
    dropped = C.FROZEN_N - n_games_panel
    train = panel[panel["dataset_split"] == "TRAIN"]
    fmap = estimate_f(train)
    out = {
        "n_first80": C.FROZEN_N,
        "n_games_in_pade": n_games_panel,
        "n_dropped_no_pade": dropped,
        "n_train_buckets": len(fmap),
        "min_games_per_bucket": 20,
        "TRAIN_self": eval_alpha(train, fmap),
        "VALIDATION": eval_alpha(panel[panel["dataset_split"] == "VALIDATION"], fmap),
        "OOS": eval_alpha(panel[panel["dataset_split"] == "OOS"], fmap),
        "anti_leakage": "TRAIN games only construct Fhat. VAL/OOS games are never in their own Fhat.",
        "not": "directly observed alpha",
    }
    C.write_json(C.RESULTS / "alpha_persistence.json", out)
    return out
