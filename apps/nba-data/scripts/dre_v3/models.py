"""Predictive models. Fit TRAIN only. Separate from exposure-policy objects."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from . import config as C
from .calibration import ece


def _xy(df: pd.DataFrame, ycol: str, cols=None):
    cols = cols or C.FEATURE_COLS
    sub = df[cols + [ycol]].copy()
    for c in cols:
        sub[c] = pd.to_numeric(sub[c], errors="coerce")
    sub[ycol] = pd.to_numeric(sub[ycol], errors="coerce")
    sub = sub.dropna()
    if sub.empty:
        return None, None, None
    return sub[cols].to_numpy(float), sub[ycol].to_numpy(int), sub.index


def fit_logit(X, y):
    if X is None or len(y) < 40 or y.min() == y.max():
        return None
    pipe = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    max_iter=400,
                    C=1.0,
                    solver="lbfgs",
                    random_state=C.RANDOM_SEED,
                ),
            ),
        ]
    )
    pipe.fit(X, y)
    return pipe


def fit_multinomial(X, y):
    if X is None or len(y) < 80:
        return None
    pipe = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    max_iter=500,
                    C=1.0,
                    solver="lbfgs",
                    random_state=C.RANDOM_SEED,
                ),
            ),
        ]
    )
    pipe.fit(X, y)
    return pipe


def metrics_binary(y, p) -> dict:
    y = np.asarray(y, float)
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    out = {"n": int(len(y)), "base_rate": float(y.mean()) if len(y) else None}
    if len(y) < 20 or y.min() == y.max():
        out.update({"auc": None, "brier": None, "logloss": None, "ece": None})
        return out
    out["auc"] = float(roc_auc_score(y, p))
    out["brier"] = float(brier_score_loss(y, p))
    out["logloss"] = float(log_loss(y, p))
    out["ece"] = ece(y, p)
    return out


def predict_binary(model, df: pd.DataFrame, cols=None) -> np.ndarray:
    cols = cols or C.FEATURE_COLS
    out = np.full(len(df), np.nan)
    if model is None:
        return out
    sub = df[cols].apply(pd.to_numeric, errors="coerce")
    ok = sub.notna().all(axis=1)
    if ok.any():
        out[ok.to_numpy()] = model.predict_proba(sub.loc[ok].to_numpy(float))[:, 1]
    return out


def predict_multinomial(model, df: pd.DataFrame, classes, cols=None) -> np.ndarray:
    """Return (n, K) probabilities aligned to C.PATH_BINS order."""
    cols = cols or C.FEATURE_COLS
    K = len(C.PATH_BINS)
    out = np.full((len(df), K), np.nan)
    if model is None:
        return out
    sub = df[cols].apply(pd.to_numeric, errors="coerce")
    ok = sub.notna().all(axis=1)
    if not ok.any():
        return out
    proba = model.predict_proba(sub.loc[ok].to_numpy(float))
    cls = list(model.named_steps["clf"].classes_)
    mapped = np.zeros((proba.shape[0], K))
    for j, b in enumerate(C.PATH_BINS):
        if b in cls:
            mapped[:, j] = proba[:, cls.index(b)]
    s = mapped.sum(axis=1, keepdims=True)
    if np.any(s <= 0) or np.any(~np.isfinite(s)):
        raise RuntimeError("path distribution failed to normalize")
    mapped = mapped / s
    if np.any(np.abs(mapped.sum(axis=1) - 1.0) > 1e-6):
        raise RuntimeError("path distribution sum != 1")
    out[ok.to_numpy()] = mapped
    return out


def fit_predictive(df: pd.DataFrame) -> tuple[dict, list[dict]]:
    """Fit terminal, recovery, downside, path-bin models on TRAIN. Score all splits."""
    train = df[df["dataset_split"] == "TRAIN"]
    fitted = {}
    metrics = []

    # terminal
    X, y, _ = _xy(train, "y_settle_yes")
    fitted["p_terminal"] = fit_logit(X, y)

    # recovery binaries
    train_end = train[train["path_valid_end"]]
    for name, col in (
        ("p_rec10_end", "y_rec_ge_10_end"),
        ("p_rec30_end", "y_rec_ge_30_end"),
        ("p_det10_end", "y_det_ge_10_end"),
        ("p_jump40", "y_jump_40"),
    ):
        if col not in train.columns and col != "y_rec_ge_30_end":
            continue
        X, y, _ = _xy(train_end if "end" in col or col == "y_rec_ge_30_end" else train, col)
        fitted[name] = fit_logit(X, y)

    for hz in C.HORIZONS:
        tr = train[train[f"path_valid_{hz}"]]
        yb = tr[f"path_bin_{hz}"].astype(str)
        cols = C.FEATURE_COLS
        sub = tr[cols].apply(pd.to_numeric, errors="coerce")
        ok = sub.notna().all(axis=1) & yb.notna() & (yb != "None")
        if ok.sum() < 80:
            fitted[f"path_{hz}"] = None
            continue
        fitted[f"path_{hz}"] = fit_multinomial(sub.loc[ok].to_numpy(float), yb.loc[ok].to_numpy())

    # attach predictions
    df = df.copy()
    df["p_terminal_v3"] = predict_binary(fitted["p_terminal"], df)
    # Primary terminal probability is the frozen DRE V2 M3 score (TRAIN-fit in V2).
    # V3 tests nonlinear objectives, not a weaker re-estimate of settlement.
    if "p_settle_M3" in df.columns:
        df["p_terminal"] = pd.to_numeric(df["p_settle_M3"], errors="coerce")
    else:
        df["p_terminal"] = df["p_terminal_v3"]
    for name in ("p_rec10_end", "p_rec30_end", "p_det10_end", "p_jump40"):
        if name in fitted:
            df[name] = predict_binary(fitted[name], df)
    for hz in C.HORIZONS:
        proba = predict_multinomial(fitted.get(f"path_{hz}"), df, C.PATH_BINS)
        for j, b in enumerate(C.PATH_BINS):
            df[f"p_{b}_{hz}"] = proba[:, j]
        df[f"p_path_sum_{hz}"] = proba.sum(axis=1)

    # metrics
    for split in ("TRAIN", "VALIDATION", "OOS"):
        xs = df[df["dataset_split"] == split]
        for key, ycol in (
            ("p_terminal", "y_settle_yes"),
            ("p_terminal_v3", "y_settle_yes"),
            ("p_rec10_end", "y_rec_ge_10_end"),
            ("p_rec30_end", "y_rec_ge_30_end"),
            ("p_det10_end", "y_det_ge_10_end"),
            ("p_jump40", "y_jump_40"),
        ):
            if key not in xs.columns:
                continue
            mask = xs[key].notna() & xs[ycol].notna()
            met = metrics_binary(xs.loc[mask, ycol], xs.loc[mask, key])
            met.update({"model": key, "split": split, "layer": "PREDICTIVE_INFORMATION"})
            metrics.append(met)
        for hz in C.HORIZONS:
            mask = xs[f"path_valid_{hz}"] & xs[f"p_path_sum_{hz}"].notna()
            if mask.sum() < 20:
                continue
            y_true = xs.loc[mask, f"path_bin_{hz}"].astype(str)
            p = np.column_stack([xs.loc[mask, f"p_{b}_{hz}"].to_numpy() for b in C.PATH_BINS])
            # map labels
            y_idx = y_true.map({b: i for i, b in enumerate(C.PATH_BINS)}).to_numpy()
            ok = ~pd.isna(y_idx)
            if ok.sum() < 20:
                continue
            try:
                ll = float(log_loss(y_idx[ok].astype(int), p[ok], labels=list(range(len(C.PATH_BINS)))))
            except Exception:
                ll = None
            metrics.append(
                {
                    "model": f"path_{hz}",
                    "split": split,
                    "n": int(ok.sum()),
                    "logloss": ll,
                    "layer": "PREDICTIVE_INFORMATION",
                    "sum_check_max_abs": float(np.nanmax(np.abs(xs.loc[mask, f"p_path_sum_{hz}"] - 1.0))),
                }
            )
    return df, fitted, metrics
