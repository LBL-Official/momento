"""Nested distributional models. TRAIN fit only. No OOS selection."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from . import config as C


TARGETS = (
    ("y_settle_yes", "terminal"),
    ("y_rec10_5", "recovery"),
    ("y_det10_5", "deterioration"),
    ("y_min_le_40_k5", "negative_control_40"),
)


def _xy(df, cols, ycol):
    sub = df[list(cols) + [ycol]].copy()
    for c in cols:
        sub[c] = pd.to_numeric(sub[c], errors="coerce")
    sub[ycol] = pd.to_numeric(sub[ycol], errors="coerce")
    sub = sub.dropna()
    if sub.empty:
        return None, None, None
    return sub[cols].to_numpy(float), sub[ycol].to_numpy(int), sub.index


def _fit_logit(X, y):
    if X is None or len(y) < 40 or y.min() == y.max():
        return None
    pipe = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=400, C=1.0, solver="lbfgs", random_state=C.RANDOM_SEED)),
        ]
    )
    pipe.fit(X, y)
    return pipe


def _metrics(y, p) -> dict:
    y = np.asarray(y, float)
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    out = {"n": int(len(y)), "base_rate": float(y.mean()) if len(y) else None}
    if len(y) < 20 or y.min() == y.max():
        out.update({"auc": None, "brier": None, "logloss": None})
        return out
    out["auc"] = float(roc_auc_score(y, p))
    out["brier"] = float(brier_score_loss(y, p))
    out["logloss"] = float(log_loss(y, p))
    return out


def fit_nested(df: pd.DataFrame) -> tuple[list[dict], dict]:
    train = df[df["dataset_split"] == "TRAIN"]
    metrics = []
    fitted = {}
    for fam, cols in C.FAMILIES.items():
        for ycol, kind in TARGETS:
            X, y, _ = _xy(train, cols, ycol)
            model = _fit_logit(X, y)
            fitted[(fam, ycol)] = (model, cols)
            for split in ("TRAIN", "VALIDATION", "OOS"):
                xs = df[df["dataset_split"] == split]
                p = _predict(model, xs, cols)
                mask = np.isfinite(p) & xs[ycol].notna()
                met = _metrics(xs.loc[mask, ycol], p[mask.to_numpy()])
                met.update({"family": fam, "target": ycol, "kind": kind, "split": split, "oos_used_for_fit": False})
                metrics.append(met)
        # path class multinomial
        yb = train["path_class_5"].astype(str)
        sub = train[cols].apply(pd.to_numeric, errors="coerce")
        ok = sub.notna().all(axis=1) & yb.notna() & (yb != "INSUFFICIENT_FORWARD_OBSERVATION")
        if ok.sum() >= 80:
            clf = _fit_logit(sub.loc[ok].to_numpy(float), pd.Categorical(yb.loc[ok]).codes)
            # use multinomial explicitly
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
            y_str = yb.loc[ok].to_numpy()
            pipe.fit(sub.loc[ok].to_numpy(float), y_str)
            fitted[(fam, "path_class_5")] = (pipe, cols)
            for split in ("TRAIN", "VALIDATION", "OOS"):
                xs = df[df["dataset_split"] == split]
                feat = xs[cols].apply(pd.to_numeric, errors="coerce")
                m = feat.notna().all(axis=1) & xs["path_class_5"].notna() & (xs["path_class_5"] != "INSUFFICIENT_FORWARD_OBSERVATION")
                if m.sum() < 20:
                    continue
                proba = pipe.predict_proba(feat.loc[m].to_numpy(float))
                classes = list(pipe.named_steps["clf"].classes_)
                y_true = xs.loc[m, "path_class_5"].to_numpy()
                mapped = np.zeros((len(y_true), len(classes)))
                # one-hot for logloss
                try:
                    ll = float(log_loss(y_true, proba, labels=classes))
                except Exception:
                    ll = None
                metrics.append(
                    {
                        "family": fam,
                        "target": "path_class_5",
                        "kind": "path_distribution",
                        "split": split,
                        "n": int(m.sum()),
                        "logloss": ll,
                        "oos_used_for_fit": False,
                    }
                )
    return metrics, fitted


def _predict(model, df, cols):
    out = np.full(len(df), np.nan)
    if model is None:
        return out
    sub = df[cols].apply(pd.to_numeric, errors="coerce")
    ok = sub.notna().all(axis=1)
    if ok.any():
        out[ok.to_numpy()] = model.predict_proba(sub.loc[ok].to_numpy(float))[:, 1]
    return out


def incremental(metrics: list[dict]) -> dict:
    """OOS Δ vs B0. Small AUC deltas are not discoveries."""
    out = {}
    for ycol, _ in TARGETS:
        def grab(fam, split="OOS"):
            hits = [m for m in metrics if m.get("family") == fam and m.get("target") == ycol and m.get("split") == split]
            return hits[0] if hits else {}

        b0 = grab("B0")
        for fam in ("B1", "B2", "M3", "M4", "M5"):
            m = grab(fam)
            d_auc = None
            if b0.get("auc") is not None and m.get("auc") is not None:
                d_auc = m["auc"] - b0["auc"]
            d_brier = None
            if b0.get("brier") is not None and m.get("brier") is not None:
                d_brier = b0["brier"] - m["brier"]
            out[f"{fam}_{ycol}"] = {"d_auc": d_auc, "d_brier": d_brier, "b0_auc": b0.get("auc"), "auc": m.get("auc")}
    return out


def no_oos_tuning_audit() -> dict:
    return {
        "gate": "J",
        "status": "PASS",
        "candidates": {"logit_C": [1.0], "solver": ["lbfgs"]},
        "selected": {"logit_C": 1.0, "solver": "lbfgs"},
        "selection_metric": "none — pre-registered, not searched",
        "selection_split": "none",
        "oos_used": False,
        "matched_price_spec": C.PRIMARY,
        "timestamp": C.utc_now(),
        "note": "No hyperparameter search. PRIMARY contrast pre-registered in config.py.",
    }
