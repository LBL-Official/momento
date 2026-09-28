"""Nested logistic models. Hyperparameters frozen a priori. No OOS tuning."""

from __future__ import annotations

import math

import numpy as np

from . import config as C
from .calibration import ece
from .feature_builder import ALL_TARGETS, FAMILIES, FAMILY_LAYER

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


def fit_logit(X: np.ndarray, y: np.ndarray):
    if not HAS_SKLEARN or X is None or len(y) < 40 or y.min() == y.max():
        return None
    pipe = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    max_iter=C.LOGIT_MAX_ITER,
                    C=C.LOGIT_C,
                    solver="lbfgs",
                    class_weight="balanced",
                    random_state=C.RANDOM_SEED,
                ),
            ),
        ]
    )
    pipe.fit(X, y)
    return pipe


def metrics_of(y, p) -> dict:
    y = np.asarray(y, dtype=float)
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    out = {"n": int(len(y)), "base_rate": float(y.mean()) if len(y) else None}
    if len(y) < 20 or y.min() == y.max():
        out.update({"auc": None, "brier": None, "logloss": None, "ece": None})
        return out
    out["auc"] = float(roc_auc_score(y, p))
    out["brier"] = float(brier_score_loss(y, p))
    out["logloss"] = float(log_loss(y, p))
    out["ece"] = ece(y, p)
    return out


def _scalar(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return float(int(v))
    if isinstance(v, (int, float)):
        if isinstance(v, float) and math.isnan(v):
            return None
        return float(v)
    return None


def xy(rows, cols, yname):
    xs, ys, keep = [], [], []
    for r in rows:
        y = r.get(yname)
        if y is None:
            continue
        vec = []
        ok = True
        for c in cols:
            v = _scalar(r.get(c))
            if v is None:
                ok = False
                break
            vec.append(v)
        if not ok:
            continue
        xs.append(vec)
        ys.append(int(y))
        keep.append(r)
    if not xs:
        return None, None, []
    return np.array(xs, dtype=float), np.array(ys, dtype=int), keep


def complete_case_report(rows, cols, yname) -> dict:
    n_in = len(rows)
    games_in = len({r["event_id"] for r in rows})
    _, _, keep = xy(rows, cols, yname)
    missing = n_in - len(keep)
    return {
        "n_in": n_in,
        "n_complete": len(keep),
        "n_excluded": missing,
        "games_in": games_in,
        "games_complete": len({r["event_id"] for r in keep}),
        "exclusion_reason": "complete-case: any family feature or label null",
    }


def run_nested(usable: list[dict]) -> tuple[list[dict], dict, dict]:
    """Fit each family on TRAIN; score TRAIN/VAL/OOS. Return metrics, fitted models, exclusions."""
    model_rows = []
    fitted = {}
    exclusions = []
    if not HAS_SKLEARN:
        C.log("sklearn missing — cannot fit models")
        return model_rows, fitted, {"status": "FAIL", "reason": "sklearn missing"}

    for fam, cols in FAMILIES.items():
        for yname, ylab in ALL_TARGETS:
            train = [r for r in usable if r["dataset_split"] == "TRAIN"]
            tr_x, tr_y, _ = xy(train, cols, yname)
            model = fit_logit(tr_x, tr_y) if tr_x is not None else None
            fitted[(fam, yname)] = {"model": model, "cols": cols}
            for split in ("TRAIN", "VALIDATION", "OOS"):
                srows = [r for r in usable if r["dataset_split"] == split]
                sx, sy, kept = xy(srows, cols, yname)
                excl = complete_case_report(srows, cols, yname)
                excl.update({"family": fam, "target": yname, "split": split})
                exclusions.append(excl)
                if model is None or sx is None:
                    model_rows.append(
                        {
                            "family": fam,
                            "layer": FAMILY_LAYER[fam],
                            "target": yname,
                            "target_label": ylab,
                            "split": split,
                            "n": 0 if sy is None else int(len(sy)),
                            "n_in": excl["n_in"],
                            "n_excluded": excl["n_excluded"],
                            "games": excl["games_complete"],
                            "auc": None,
                            "brier": None,
                            "logloss": None,
                            "ece": None,
                            "status": "INSUFFICIENT",
                            "n_features": len(cols),
                        }
                    )
                    continue
                p = model.predict_proba(sx)[:, 1]
                met = metrics_of(sy, p)
                model_rows.append(
                    {
                        "family": fam,
                        "layer": FAMILY_LAYER[fam],
                        "target": yname,
                        "target_label": ylab,
                        "split": split,
                        **met,
                        "n_in": excl["n_in"],
                        "n_excluded": excl["n_excluded"],
                        "games": excl["games_complete"],
                        "status": "FIT",
                        "n_features": len(cols),
                    }
                )

    return model_rows, fitted, {"status": "PASS", "rows": exclusions}


def predict_rows(rows, fitted, fam: str, yname: str) -> list[float | None]:
    pack = fitted.get((fam, yname))
    if not pack or pack["model"] is None:
        return [None] * len(rows)
    cols = pack["cols"]
    out = []
    model = pack["model"]
    for r in rows:
        vec = []
        ok = True
        for c in cols:
            v = _scalar(r.get(c))
            if v is None:
                ok = False
                break
            vec.append(v)
        if not ok:
            out.append(None)
            continue
        p = float(model.predict_proba(np.array([vec], dtype=float))[0, 1])
        out.append(p)
    return out


def pick(model_rows, fam, target, split, field):
    for m in model_rows:
        if m["family"] == fam and m["target"] == target and m["split"] == split:
            return m.get(field)
    return None


def incremental(model_rows) -> list[dict]:
    """Every advanced family vs B0 on the same split/target (GATE G)."""
    out = []
    targets = sorted({m["target"] for m in model_rows})
    for target in targets:
        for fam in FAMILIES:
            if fam == "B0":
                continue
            for split in ("TRAIN", "VALIDATION", "OOS"):
                b0_auc = pick(model_rows, "B0", target, split, "auc")
                b0_brier = pick(model_rows, "B0", target, split, "brier")
                auc = pick(model_rows, fam, target, split, "auc")
                brier = pick(model_rows, fam, target, split, "brier")
                n = pick(model_rows, fam, target, split, "n")
                out.append(
                    {
                        "family": fam,
                        "target": target,
                        "split": split,
                        "n": n,
                        "auc": auc,
                        "brier": brier,
                        "b0_auc": b0_auc,
                        "b0_brier": b0_brier,
                        "d_auc": (auc - b0_auc) if auc is not None and b0_auc is not None else None,
                        "d_brier": (brier - b0_brier) if brier is not None and b0_brier is not None else None,
                    }
                )
    return out
