"""XIB hierarchy. Walk Model 0→3 once. Select on VAL probability quality only."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from terminal_efficiency.models.metrics import bootstrap_brier_ci, probability_metrics
from terminal_efficiency.validation.temporal_split import assert_no_test_in_fit, fit_mask, val_mask

MODEL0 = ["score_difference", "seconds_remaining_game", "period"]
MODEL1 = MODEL0 + [
    "home_win_pct_pre",
    "away_win_pct_pre",
    "home_net_rating_pre",
    "away_net_rating_pre",
    "home_wins_last5_pre",
    "away_wins_last5_pre",
]
MODEL2 = MODEL1 + [
    "possession_home",
    "est_possessions_remaining",
    "current_run_home",
    "home_pace_pre",
    "away_pace_pre",
]

# Material VAL Brier improvement required to accept a richer model.
MIN_BRIER_IMPROVEMENT = 0.001


def _xy(df: pd.DataFrame, cols: list[str]) -> tuple[pd.DataFrame, np.ndarray]:
    x = df[cols].apply(pd.to_numeric, errors="coerce")
    y = df["final_home_win"].astype(int).to_numpy()
    return x, y


def _logit_pipeline() -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            (
                "clf",
                LogisticRegression(max_iter=400, solver="lbfgs"),
            ),
        ]
    )


def _platt(raw: np.ndarray, y: np.ndarray) -> LogisticRegression:
    lr = LogisticRegression(max_iter=200)
    lr.fit(np.asarray(raw).reshape(-1, 1), y)
    return lr


def _fit_logit(train: pd.DataFrame, val: pd.DataFrame, cols: list[str]):
    xtr, ytr = _xy(train, cols)
    pipe = _logit_pipeline()
    pipe.fit(xtr, ytr)
    xva, yva = _xy(val, cols)
    raw = pipe.predict_proba(xva)[:, 1]
    platt = _platt(raw, yva)
    return pipe, platt


def _predict(model_pair, df: pd.DataFrame, cols: list[str]) -> np.ndarray:
    pipe, platt = model_pair
    x, _ = _xy(df, cols)
    raw = pipe.predict_proba(x)[:, 1]
    p = platt.predict_proba(raw.reshape(-1, 1))[:, 1]
    return np.clip(p, 1e-6, 1 - 1e-6)


def _slice_metrics(df: pd.DataFrame, p: np.ndarray) -> dict:
    y = df["final_home_win"].astype(int).to_numpy()
    out = {"overall": {**probability_metrics(y, p), **bootstrap_brier_ci(y, p)}}
    if "period" in df.columns:
        for period, grp in df.groupby("period"):
            idx = grp.index
            # align by position
            mask = df.index.isin(idx)
            out[f"period_{period}"] = probability_metrics(df.loc[mask, "final_home_win"].astype(int).to_numpy(), p[mask])
    return out


def train_xib_hierarchy(obs: pd.DataFrame) -> dict:
    assert_no_test_in_fit(obs)
    work = obs.dropna(subset=["final_home_win", "score_difference", "seconds_remaining_game", "period"]).copy()
    work = work[work["split"].isin(["TRAIN", "VAL"])]
    train = work[fit_mask(work)]
    val = work[val_mask(work)]
    if train.empty or val.empty:
        return {"status": "FAIL", "reason": "empty train or val"}

    candidates = [
        ("model0_score_clock_period", MODEL0, "logit"),
        ("model1_plus_pregame", MODEL1, "logit"),
        ("model2_plus_state", MODEL2, "logit"),
    ]
    results = []
    best = None
    for name, cols, kind in candidates:
        pair = _fit_logit(train, val, cols)
        p_val = _predict(pair, val, cols)
        metrics = _slice_metrics(val.reset_index(drop=True), p_val)
        rec = {
            "name": name,
            "kind": kind,
            "features": cols,
            "val": metrics["overall"],
            "slices": {k: v for k, v in metrics.items() if k != "overall"},
        }
        results.append(rec)
        if best is None:
            best = rec
        else:
            if rec["val"]["brier"] + 1e-12 < best["val"]["brier"] - MIN_BRIER_IMPROVEMENT:
                best = rec

    try:
        import lightgbm as lgb
        from sklearn.pipeline import Pipeline as SkPipeline

        booster = lgb.LGBMClassifier(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=5,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=202425,
            verbose=-1,
        )
        xtr, ytr = _xy(train, MODEL2)
        xva, yva = _xy(val, MODEL2)
        pipe = SkPipeline([("imputer", SimpleImputer(strategy="median")), ("clf", booster)])
        pipe.fit(xtr, ytr)
        raw3 = pipe.predict_proba(xva)[:, 1]
        platt3 = _platt(raw3, yva)
        p3 = np.clip(platt3.predict_proba(raw3.reshape(-1, 1))[:, 1], 1e-6, 1 - 1e-6)
        m3 = _slice_metrics(val.reset_index(drop=True), p3)
        model3 = {
            "name": "model3_lightgbm",
            "kind": "lightgbm",
            "features": MODEL2,
            "val": m3["overall"],
            "slices": {k: v for k, v in m3.items() if k != "overall"},
        }
        results.append(model3)
        if model3["val"]["brier"] + 1e-12 < best["val"]["brier"] - MIN_BRIER_IMPROVEMENT:
            best = model3
    except Exception as exc:  # noqa: BLE001
        results.append({"name": "model3_lightgbm", "skipped": True, "reason": str(exc)})

    if best["name"] == "model3_lightgbm":
        selected_cols = MODEL2
        xtr, ytr = _xy(train, MODEL2)
        xva, yva = _xy(val, MODEL2)
        import lightgbm as lgb
        from sklearn.pipeline import Pipeline as SkPipeline

        pipe = SkPipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "clf",
                    lgb.LGBMClassifier(
                        n_estimators=200,
                        learning_rate=0.05,
                        max_depth=5,
                        subsample=0.8,
                        colsample_bytree=0.8,
                        random_state=202425,
                        verbose=-1,
                    ),
                ),
            ]
        )
        pipe.fit(xtr, ytr)
        selected_cal = (pipe, _platt(pipe.predict_proba(xva)[:, 1], yva))
    else:
        selected_cols = best["features"]
        selected_cal = _fit_logit(train, val, selected_cols)

    return {
        "status": "OK",
        "selected": best["name"],
        "selected_features": selected_cols,
        "candidates": results,
        "calibrator": selected_cal,
        "train_n": int(len(train)),
        "val_n": int(len(val)),
        "train_end": str(train["game_date"].max()) if "game_date" in train else None,
        "val_start": str(val["game_date"].min()) if "game_date" in val else None,
    }


def apply_xib(cal, df: pd.DataFrame, cols: list[str]) -> np.ndarray:
    return _predict(cal, df, cols)
