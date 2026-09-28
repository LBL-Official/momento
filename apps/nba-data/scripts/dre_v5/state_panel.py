"""Workstream 3 — possession-primary X_t panel and frozen payoff labels."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import config as C
from .possession_remaining import attach_n_hat


PADE_KEEP = [
    "trade_id",
    "event_id",
    "nba_game_id",
    "market_ticker",
    "opponent_ticker",
    "A1_team",
    "A2_team",
    "dataset_split",
    "game_date",
    "entry_timestamp",
    "possession_id",
    "possession_index",
    "possessions_since_entry",
    "period",
    "is_overtime",
    "game_clock",
    "elapsed_game_seconds",
    "game_seconds_remaining",
    "position_age_wall_s",
    "is_A1_team_offense",
    "offensive_team",
    "score_home",
    "score_away",
    "score_differential_from_A1",
    "current_price",
    "A1_yes_bid",
    "A1_yes_ask",
    "A1_mid",
    "A1_candle_high",
    "A1_candle_low",
    "A2_yes_bid",
    "A2_yes_ask",
    "estimated_possessions_remaining_r1",
    "actual_remaining_possessions",
    "market_observation_timestamp",
    "market_age_seconds",
    "alignment_confidence",
    "y_settle_yes",
    "y_min_le_40_k5",
    "y_min_le_40_end",
    "future_min_5",
    "future_max_5",
    "future_min_end",
    "future_deterioration_5",
    "recovery_from_current_5",
    "y_jump_40",
    "expiration_result_yes",
]


def clock_bin_l1(period, elapsed, gsr, is_ot) -> str:
    if bool(is_ot) or (period is not None and pd.notna(period) and int(period) > 4):
        return "OT"
    p = None if period is None or pd.isna(period) else int(period)
    el = None if elapsed is None or pd.isna(elapsed) else float(elapsed)
    if p is not None and p <= 2:
        return "Q1_Q2"
    if el is not None and el < 1440:
        return "Q1_Q2"
    if p == 3 or (el is not None and el < 2160):
        return "Q3"
    rem = None if gsr is None or pd.isna(gsr) else float(gsr)
    if rem is None and el is not None:
        rem = max(0.0, C.REG_GAME_S - el)
    if rem is None:
        return "Q4_GT6"
    if rem > 360:
        return "Q4_GT6"
    if rem > 120:
        return "Q4_2_6"
    return "Q4_LT2"


def score_bin_l1(diff) -> str | None:
    if diff is None or pd.isna(diff):
        return None
    x = float(diff)
    if x >= 10:
        return "ge_p10"
    if x >= 5:
        return "p5_9"
    if x >= 1:
        return "p1_4"
    if x == 0:
        return "zero"
    if x >= -4:
        return "m1_4"
    return "le_m5"


def clock_l2(bin_l1: str | None) -> str | None:
    """Frozen L2: EARLY=Q1+Q2+Q3, LATE=Q4, OT separately flagged (not folded into LATE)."""
    if bin_l1 is None:
        return None
    return C.CLOCK_L2_FROM_L1.get(str(bin_l1))


def score_l2(diff) -> str | None:
    if diff is None or pd.isna(diff):
        return None
    return "lead" if float(diff) > 0 else "tie_trail"


def price_bin(price, width: int) -> float | None:
    if price is None or pd.isna(price):
        return None
    return float(int(np.floor(float(price) / width) * width))


def build_panel(priors: pd.DataFrame) -> pd.DataFrame:
    pade = pd.read_parquet(C.PADE_OUT / "05_trade_possession_panel.parquet", columns=PADE_KEEP)
    if int(pade.groupby(["trade_id", "possession_index"]).ngroups) != int(len(pade)):
        raise RuntimeError("state panel duplicated (trade_id, possession_index)")
    if len(pade) != C.PANEL_ROWS_EXPECTED:
        raise RuntimeError(f"panel rows {len(pade)} != {C.PANEL_ROWS_EXPECTED}")

    df = attach_n_hat(pade, priors)
    # Canonical market units: cents per contract on [0, 100]. Not dollars.
    df["current_price_cents"] = pd.to_numeric(df["current_price"], errors="coerce")
    df["A1_yes_bid_cents"] = pd.to_numeric(df["A1_yes_bid"], errors="coerce")
    df["A2_yes_bid_cents"] = pd.to_numeric(df["A2_yes_bid"], errors="coerce")
    df["entry_price_cents"] = float(C.ENTRY_PRICE_CENTS)
    df["rel_a1_a2_cents"] = df["A1_yes_bid_cents"] - df["A2_yes_bid_cents"]
    df["complement_residual_cents"] = df["A1_yes_bid_cents"] + df["A2_yes_bid_cents"] - 100.0
    # V_mtm_cents = 100 * P_A1_cents. Not 100 * possessions.
    df["V_mtm_cents"] = C.CONTRACTS_RESEARCH * df["current_price_cents"]
    df["delta_inv"] = C.DELTA_INV
    df["current_price"] = df["current_price_cents"]
    df["A1_yes_bid"] = df["A1_yes_bid_cents"]
    df["A2_yes_bid"] = df["A2_yes_bid_cents"]

    y = pd.to_numeric(df["y_settle_yes"], errors="coerce")
    df["y_settle_yes"] = y
    df["pi_terminal"] = 100.0 * y - 80.0
    df["pi_mtm"] = 100.0 * y - df["current_price_cents"]
    hit40_end = pd.to_numeric(df["y_min_le_40_end"], errors="coerce")
    df["pi_40_framework"] = np.where(hit40_end == 1, -float(C.BRANCH_THRESHOLD_CENTS), df["pi_terminal"])
    df["pi_40_framework_label"] = "CANDLE_PATH_PROXY"
    df["pi_40_framework_disclaimer"] = "OBSERVED CANDLE PATH ≠ EXECUTED STOP"
    df["pi_40_framework_role"] = "DIAGNOSTIC_ONLY"

    df["is_A1_team_offense"] = df["is_A1_team_offense"].map(
        lambda x: 1 if x is True or x == 1 else (0 if x is False or x == 0 else None)
    )
    df["is_overtime"] = df["is_overtime"].map(lambda x: bool(x) if pd.notna(x) else False)

    elapsed = pd.to_numeric(df["elapsed_game_seconds"], errors="coerce")
    df["clock_cluster_30s"] = np.where(
        df["is_overtime"] | (pd.to_numeric(df["period"], errors="coerce") > 4),
        np.nan,
        np.clip(np.floor(elapsed / 30.0), 0, 95),
    )
    df["clock_cluster_ot_flag"] = df["is_overtime"] | (pd.to_numeric(df["period"], errors="coerce") > 4)

    df["clock_bin_l1"] = [
        clock_bin_l1(p, e, g, ot)
        for p, e, g, ot in zip(df["period"], df["elapsed_game_seconds"], df["game_seconds_remaining"], df["is_overtime"])
    ]
    df["score_bin_l1"] = [score_bin_l1(x) for x in df["score_differential_from_A1"]]
    df["clock_bin_l2"] = [clock_l2(x) for x in df["clock_bin_l1"]]
    df["score_bin_l2"] = [score_l2(x) for x in df["score_differential_from_A1"]]
    df["price_bin_5"] = [price_bin(x, C.PRICE_BIN_CENTS) for x in df["current_price_cents"]]
    df["price_bin_10"] = [price_bin(x, C.PRICE_BIN_L2_CENTS) for x in df["current_price_cents"]]

    train_n = pd.to_numeric(df.loc[df["dataset_split"] == "TRAIN", "n_hat_remaining_prior"], errors="coerce").dropna()
    q33, q67 = (float(train_n.quantile(1 / 3)), float(train_n.quantile(2 / 3))) if len(train_n) else (np.nan, np.nan)
    med = float(train_n.median()) if len(train_n) else np.nan
    nh = pd.to_numeric(df["n_hat_remaining_prior"], errors="coerce")
    df["n_hat_bin_l1"] = np.where(nh.isna(), None, np.where(nh >= q67, "high", np.where(nh >= q33, "mid", "low")))
    df["n_hat_bin_l2"] = np.where(nh.isna(), None, np.where(nh >= med, "high", "low"))
    df.attrs["n_hat_tertiles_train"] = {"q33": q33, "q67": q67, "median": med}

    df = _asof_rolls(df)
    df = _at_risk(df)
    return df


def _asof_rolls(df: pd.DataFrame) -> pd.DataFrame:
    d1 = np.full(len(df), np.nan)
    d3 = np.full(len(df), np.nan)
    d5 = np.full(len(df), np.nan)
    sig = np.full(len(df), np.nan)
    idx = np.arange(len(df))
    df = df.copy()
    df["_i"] = idx
    for _, g in df.groupby("trade_id", sort=False):
        g = g.sort_values("possession_index")
        ii = g["_i"].to_numpy()
        sd = pd.to_numeric(g["score_differential_from_A1"], errors="coerce").to_numpy(float)
        px = pd.to_numeric(g["current_price_cents"], errors="coerce").to_numpy(float)
        dp = np.diff(px, prepend=np.nan)
        for k, gi in enumerate(ii):
            if k >= 1:
                d1[gi] = sd[k] - sd[k - 1]
            if k >= 3:
                d3[gi] = sd[k] - sd[k - 3]
            if k >= 5:
                d5[gi] = sd[k] - sd[k - 5]
            w = dp[max(0, k - 4) : k + 1]
            w = w[np.isfinite(w)]
            if len(w) >= 3:
                sig[gi] = float(np.std(w, ddof=1)) if len(w) > 1 else float(np.std(w))
    df["d_sd_1"] = d1
    df["d_sd_3"] = d3
    df["d_sd_5"] = d5
    df["sigma_P"] = sig
    df["sigma_P_note"] = "as-of rolling std of ΔP per possession (window ≤5)"
    return df.drop(columns=["_i"])


def _at_risk(df: pd.DataFrame) -> pd.DataFrame:
    already = np.zeros(len(df), dtype=bool)
    at_risk = np.zeros(len(df), dtype=bool)
    y_hit = np.full(len(df), np.nan)
    idx = np.arange(len(df))
    df = df.copy()
    df["_i"] = idx
    for _, g in df.groupby("trade_id", sort=False):
        g = g.sort_values("possession_index")
        ii = g["_i"].to_numpy()
        px = pd.to_numeric(g["current_price_cents"], errors="coerce").to_numpy(float)
        run_min = np.inf
        for k, gi in enumerate(ii):
            if np.isfinite(px[k]):
                run_min = min(run_min, px[k])
            damaged = run_min <= C.BRANCH_THRESHOLD_CENTS
            already[gi] = damaged
            at_risk[gi] = (not damaged) and np.isfinite(run_min)
            fut = px[k + 1 :]
            fut = fut[np.isfinite(fut)]
            if at_risk[gi]:
                y_hit[gi] = float((fut <= C.BRANCH_THRESHOLD_CENTS).any()) if len(fut) else 0.0
    df["already_in_branch_40"] = already
    df["at_risk_40"] = at_risk
    df["y_future_hit_40"] = y_hit
    return df.drop(columns=["_i"])


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


def universe_accounting(df: pd.DataFrame, gate_a: dict) -> dict:
    unresolved = json.loads((C.V2_OUT / "14_diagnostics" / "unresolved.json").read_text())
    return {
        "universe": C.UNIVERSE_N,
        "matched_known": C.UNIVERSE_N - 7,
        "panel_eligible": int(df["trade_id"].nunique()),
        "panel_rows": int(len(df)),
        "model_eligible_rows": int(df["current_price_cents"].notna().sum()),
        "V_mtm_formula": "100 * P_A1_cents",
        "delta_inv": C.DELTA_INV,
        "units": C.UNITS,
        "unresolved_n": unresolved["unresolved_n"],
        "unresolved": unresolved["unresolved"],
        "contracts_research": C.CONTRACTS_RESEARCH,
        "entry_price_cents": C.ENTRY_PRICE_CENTS,
        "V_mtm_entry_cents": C.V_MTM_ENTRY_CENTS,
        "note": "UNRESOLVED ≠ MODEL-ELIGIBLE. Universe remains 1230. Q=100 is research inventory, not production size.",
        "frozen_first80": gate_a.get("observed"),
        "s5_redundancy": (
            "P_A1, P_A2, rel=A1-A2, and CR=A1+A2-100 are related market coordinates, "
            "not four independent discoveries."
        ),
    }
