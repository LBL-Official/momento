"""Shared evaluation: rates, experiments, H1–H7 masks, shallow tree."""

from __future__ import annotations

import math

import numpy as np

from common import (
    DELTA_Q_TRAIN,
    EV_MARGIN,
    EV_UNCONDITIONAL,
    MIN_ACCEPTANCE_PROD,
    MIN_ACCEPTANCE_RESEARCH,
    MIN_BUCKET_N_TRAIN,
    MIN_LEAF,
    OUT,
    Q_UNCONDITIONAL,
    benjamini_hochberg,
    ev_from_q,
    join_maps,
    rate_ci,
    read_parquet_rows,
    split_rows,
    two_prop_p,
    wilson,
)


def load_analysis_rows() -> list[dict]:
    feat = read_parquet_rows(OUT / "features_entry.parquet")
    buck = read_parquet_rows(OUT / "bucket_assignments.parquet")
    return join_maps(feat, buck)

TARGET = "Y_40_CLOSE"


def kq(rows, target=TARGET):
    n = len(rows)
    k = sum(int(r.get(target) or 0) for r in rows)
    return k, n, rate_ci(k, n)


def eval_subset(rows, name: str, target=TARGET) -> dict:
    k, n, st = kq(rows, target)
    st = dict(st)
    st["name"] = name
    st["target"] = target
    st["insufficient"] = n < MIN_BUCKET_N_TRAIN
    return st


def complement_p(subset, universe) -> float | None:
    ids = {id(r) for r in subset}
    rest = [r for r in universe if id(r) not in ids]
    k1, n1, _ = kq(subset)
    k0, n0, _ = kq(rest)
    return two_prop_p(k1, n1, k0, n0)


def experiment_row(
    *,
    experiment_id: str,
    hypothesis: str,
    features_used: str,
    bucket_definition: str,
    train,
    val,
    oos,
    universe_train,
) -> dict:
    def pack(rows, prefix):
        st = eval_subset(rows, prefix)
        return {
            f"{prefix}_n": st["n"],
            f"{prefix}_k": st["k"],
            f"{prefix}_q": st["q"],
            f"{prefix}_wilson_lo": st["wilson_lo"],
            f"{prefix}_wilson_hi": st["wilson_hi"],
            f"{prefix}_ev": st["ev"],
            f"{prefix}_delta_q": st["delta_q"],
            f"{prefix}_delta_ev": st["delta_ev"],
        }

    rec = {
        "experiment_id": experiment_id,
        "hypothesis": hypothesis,
        "features_used": features_used,
        "bucket_definition": bucket_definition,
    }
    rec.update(pack(train, "train"))
    rec.update(pack(val, "validation"))
    rec.update(pack(oos, "oos"))
    rec["train_p_vs_complement"] = complement_p(train, universe_train)
    rec["acceptance_train"] = (len(train) / len(universe_train)) if universe_train else None
    status = "EXPLORATORY"
    if rec["train_n"] < MIN_BUCKET_N_TRAIN:
        status = "INSUFFICIENT_SAMPLE"
    rec["promotion_status"] = status
    rec["effect_size"] = rec["train_delta_q"]
    rec["confidence_interval"] = (
        None
        if rec["train_wilson_lo"] is None
        else f"{rec['train_wilson_lo']:.4f}-{rec['train_wilson_hi']:.4f}"
    )
    rec["economic_EV"] = rec["train_ev"]
    rec["train_result"] = rec["train_q"]
    rec["validation_result"] = rec["validation_q"]
    rec["oos_result"] = rec["oos_q"]
    rec["sample_size"] = rec["train_n"]
    rec["notes"] = ""
    return rec


def attach_status(rec, chosen_id: str | None) -> dict:
    if rec["promotion_status"] == "INSUFFICIENT_SAMPLE":
        return rec
    tq, vq, oq = rec["train_q"], rec["validation_q"], rec["oos_q"]
    if tq is None:
        rec["promotion_status"] = "INSUFFICIENT_SAMPLE"
        return rec
    train_ok = abs(rec["train_delta_q"] or 0) >= DELTA_Q_TRAIN and rec["train_n"] >= MIN_BUCKET_N_TRAIN
    val_persist = (
        vq is not None
        and rec["validation_n"] >= 30
        and math.copysign(1, (rec["train_delta_q"] or 0) or 1)
        == math.copysign(1, (rec["validation_delta_q"] or 0) or 1)
        and abs(rec["validation_delta_q"] or 0) >= 0.02
    )
    if train_ok and vq is not None and not val_persist:
        rec["promotion_status"] = "OVERFIT"
        rec["notes"] = "TRAIN effect failed VALIDATION persistence"
        return rec
    if rec["experiment_id"] == chosen_id:
        if oq is None:
            rec["promotion_status"] = "CANDIDATE"
        else:
            oos_persist = (
                rec["oos_n"] >= 25
                and math.copysign(1, (rec["train_delta_q"] or 0) or 1)
                == math.copysign(1, (rec["oos_delta_q"] or 0) or 1)
                and (rec["oos_delta_ev"] or 0) > 0
            )
            rec["promotion_status"] = "VALIDATED" if oos_persist else "REJECTED"
            if not oos_persist:
                rec["notes"] = "Frozen candidate failed single OOS pass"
        return rec
    if train_ok and val_persist:
        rec["promotion_status"] = "CANDIDATE"
    elif train_ok:
        rec["promotion_status"] = "EXPLORATORY"
    else:
        rec["promotion_status"] = "EXPLORATORY"
    return rec


def hmasks(row: dict, train_stats: dict) -> dict[str, bool]:
    lead = row.get("lead_size")
    cld = row.get("current_lead_duration_s")
    lc = row.get("number_of_lead_changes")
    sdstd = row.get("score_differential_stdev")
    mdo = row.get("maximum_deficit_overcome")
    tdef = row.get("time_since_max_deficit_s")
    dmax = row.get("distance_from_max_lead")
    q = row.get("quarter")
    align = row.get("GAME_MARKET_ALIGNMENT")
    m50 = row.get("minutes_from_50_to_80")
    med_lc = train_stats.get("median_lead_changes")
    med_std = train_stats.get("median_score_diff_stdev")
    p25_m50 = train_stats.get("p25_minutes_50_80")
    p75_m50 = train_stats.get("p75_minutes_50_80")
    return {
        "H1": bool(
            lead is not None
            and lead >= 15
            and cld is not None
            and cld >= 300
        ),
        "H2": bool(
            lc is not None
            and med_lc is not None
            and lc >= med_lc
            and sdstd is not None
            and med_std is not None
            and sdstd >= med_std
        ),
        "H3": bool(
            mdo is not None
            and mdo >= 10
            and tdef is not None
            and tdef <= 300
        ),
        "H4": bool(
            row.get("team_is_leading")
            and dmax is not None
            and dmax >= 8
        ),
        "H5": bool(q == 4 and lead is not None and lead >= 15),
        "H6": align in ("MARKET_LEADING_GAME", "GAME_WORSENING_MARKET_FLAT"),
        "H7_violent": bool(
            m50 is not None and p25_m50 is not None and m50 <= p25_m50
        ),
        "H7_gradual": bool(
            m50 is not None and p75_m50 is not None and m50 >= p75_m50
        ),
    }


def train_stats(train_rows: list[dict]) -> dict:
    def med(col):
        xs = [r.get(col) for r in train_rows if isinstance(r.get(col), (int, float))]
        if not xs:
            return None
        xs.sort()
        return xs[len(xs) // 2]

    def qtl(col, p):
        xs = [float(r.get(col)) for r in train_rows if isinstance(r.get(col), (int, float))]
        if len(xs) < 20:
            return None
        xs.sort()
        i = min(len(xs) - 1, max(0, int(round(p * (len(xs) - 1)))))
        return xs[i]

    return {
        "median_lead_changes": med("number_of_lead_changes"),
        "median_score_diff_stdev": med("score_differential_stdev"),
        "p25_minutes_50_80": qtl("minutes_from_50_to_80", 0.25),
        "p75_minutes_50_80": qtl("minutes_from_50_to_80", 0.75),
    }


def group_by(rows, key):
    out = {}
    for r in rows:
        k = r.get(key)
        if k is None:
            continue
        out.setdefault(str(k), []).append(r)
    return out


def depth2_tree(train_rows, feature_cols, min_leaf=MIN_LEAF):
    """Gini / SSE residual stump then second split. Discovery only."""
    y = np.array([int(r[TARGET]) for r in train_rows], dtype=float)
    X = np.zeros((len(train_rows), len(feature_cols)))
    mask = np.ones_like(X, dtype=bool)
    for j, c in enumerate(feature_cols):
        for i, r in enumerate(train_rows):
            v = r.get(c)
            if v is None or isinstance(v, bool):
                if isinstance(v, bool):
                    X[i, j] = 1.0 if v else 0.0
                else:
                    mask[i, j] = False
            else:
                try:
                    X[i, j] = float(v)
                except (TypeError, ValueError):
                    mask[i, j] = False
    med = []
    for j in range(X.shape[1]):
        vals = X[mask[:, j], j]
        med.append(float(np.median(vals)) if len(vals) else 0.0)
        X[~mask[:, j], j] = med[j]

    def best_split(idx):
        best = None
        yy = y[idx]
        parent = float(np.mean((yy - yy.mean()) ** 2)) * len(idx)
        for j, col in enumerate(feature_cols):
            xv = X[idx, j]
            qs = np.unique(np.quantile(xv, np.linspace(0.2, 0.8, 7)))
            for t in qs:
                left = xv <= t
                nl, nr = int(left.sum()), int((~left).sum())
                if nl < min_leaf or nr < min_leaf:
                    continue
                yl, yr = yy[left], yy[~left]
                sse = float(np.sum((yl - yl.mean()) ** 2) + np.sum((yr - yr.mean()) ** 2))
                gain = parent - sse
                if best is None or gain > best[0]:
                    best = (gain, j, float(t), col)
        return best

    idx_all = np.arange(len(train_rows))
    root = best_split(idx_all)
    if root is None:
        return {"splits": [], "leaves": []}
    _g, j0, t0, c0 = root
    left0 = X[:, j0] <= t0
    leaves = []
    splits = [{"feature": c0, "threshold": t0, "side": "root"}]
    for side, mask_s in (("L", left0), ("R", ~left0)):
        idx = np.where(mask_s)[0]
        sub = best_split(idx)
        if sub is None:
            leaves.append(
                {
                    "rule": f"{c0} {'<=' if side=='L' else '>'} {t0:.4g}",
                    "feature": c0,
                    "threshold": t0,
                    "side": side,
                    "n": int(mask_s.sum()),
                    "q": float(y[mask_s].mean()) if mask_s.any() else None,
                }
            )
            continue
        _g2, j1, t1, c1 = sub
        splits.append({"feature": c1, "threshold": t1, "side": side})
        xv = X[:, j1]
        m_ll = mask_s & (xv <= t1)
        m_lr = mask_s & (xv > t1)
        for lab, m in ((f"{side}L", m_ll), (f"{side}R", m_lr)):
            leaves.append(
                {
                    "rule": (
                        f"{c0} {'<=' if side=='L' else '>'} {t0:.4g} AND "
                        f"{c1} {'<=' if lab.endswith('L') else '>'} {t1:.4g}"
                    ),
                    "n": int(m.sum()),
                    "q": float(y[m].mean()) if m.any() else None,
                    "mask_train_ids": [train_rows[i]["observation_id"] for i, v in enumerate(m) if v],
                    "pred_fn": (c0, t0, side, c1, t1, lab.endswith("L")),
                }
            )
    return {"splits": splits, "leaves": leaves, "medians": dict(zip(feature_cols, med))}


def apply_tree_leaf(row, pred_fn, medians):
    c0, t0, side, c1, t1, left2 = pred_fn
    v0 = row.get(c0)
    if v0 is None:
        v0 = medians.get(c0, 0.0)
    try:
        v0 = float(v0)
    except (TypeError, ValueError):
        v0 = medians.get(c0, 0.0)
    in_side = v0 <= t0 if side == "L" else v0 > t0
    if not in_side:
        return False
    v1 = row.get(c1)
    if v1 is None:
        v1 = medians.get(c1, 0.0)
    try:
        v1 = float(v1)
    except (TypeError, ValueError):
        v1 = medians.get(c1, 0.0)
    return v1 <= t1 if left2 else v1 > t1
