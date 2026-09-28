"""Brier, log loss, BSS, calibration. No thresholded accuracy as primary."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np

from roller.austin.experiments.hazard.ids import (
    BOOTSTRAP_B,
    BOOTSTRAP_SEED,
    CALIBRATION_BINS,
    H0,
    H1,
    H2,
    NOT_APPLICABLE,
)
from roller.austin.experiments.statistics import clustered_mean_diff


def _pairs(rows: list[dict[str, Any]], y_key: str, p_key: str) -> list[tuple[float, float, str]]:
    out = []
    for row in rows:
        y = row.get(y_key)
        p = row.get(p_key)
        if y in (None, NOT_APPLICABLE) or p is None:
            continue
        out.append((float(y), float(p), str(row.get("internal_game_id") or row.get("trade_id"))))
    return out


def brier_score(pairs: list[tuple[float, float, str]]) -> float | None:
    if not pairs:
        return None
    return float(np.mean([(p - y) ** 2 for y, p, _g in pairs]))


def log_loss(pairs: list[tuple[float, float, str]], *, eps: float = 1e-12) -> float | None:
    if not pairs:
        return None
    vals = []
    for y, p, _g in pairs:
        q = min(1.0 - eps, max(eps, p))
        vals.append(-(y * np.log(q) + (1.0 - y) * np.log(1.0 - q)))
    return float(np.mean(vals))


def roc_auc(pairs: list[tuple[float, float, str]]) -> float | None:
    pos = [p for y, p, _g in pairs if y == 1]
    neg = [p for y, p, _g in pairs if y == 0]
    if not pos or not neg:
        return None
    wins = 0.0
    for a in pos:
        for b in neg:
            if a > b:
                wins += 1.0
            elif a == b:
                wins += 0.5
    return wins / (len(pos) * len(neg))


def pr_auc(pairs: list[tuple[float, float, str]]) -> float | None:
    if not pairs or not any(y == 1 for y, _p, _g in pairs) or not any(y == 0 for y, _p, _g in pairs):
        return None
    order = sorted(pairs, key=lambda t: t[1], reverse=True)
    tp = 0.0
    fp = 0.0
    n_pos = sum(1 for y, _p, _g in pairs if y == 1)
    prev_rec = 0.0
    prev_prec = 1.0
    area = 0.0
    for y, _p, _g in order:
        if y == 1:
            tp += 1.0
        else:
            fp += 1.0
        rec = tp / n_pos
        prec = tp / (tp + fp)
        area += (rec - prev_rec) * (prec + prev_prec) / 2.0
        prev_rec = rec
        prev_prec = prec
    return float(area)


def calibration_rows(pairs: list[tuple[float, float, str]], *, target: str, family: str, experiment_id: str) -> list[dict[str, Any]]:
    out = []
    for lo, hi in CALIBRATION_BINS:
        group = [t for t in pairs if (t[1] >= lo and t[1] < hi) or (hi > 1.0 and t[1] == 1.0)]
        n = len(group)
        mean_p = None if not n else float(np.mean([p for _y, p, _g in group]))
        rate = None if not n else float(np.mean([y for y, _p, _g in group]))
        out.append(
            {
                "source_experiment_id": experiment_id,
                "target": target,
                "family": family,
                "bin_lo": lo,
                "bin_hi": min(hi, 1.0),
                "N": n,
                "mean_predicted": mean_p,
                "observed_rate": rate,
                "difference": None if mean_p is None or rate is None else mean_p - rate,
                "strong_evidence": n >= 10,
            }
        )
    return out


def _clustered_stat(
    rows: list[dict[str, Any]],
    *,
    y_key: str,
    model_key: str,
    h0_key: str,
    kind: str,
) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    eligible = []
    for row in rows:
        if row.get(y_key) in (None, NOT_APPLICABLE):
            continue
        if row.get(model_key) is None or row.get(h0_key) is None:
            continue
        groups[str(row.get("internal_game_id") or row.get("trade_id"))].append(row)
        eligible.append(row)
    keys = sorted(groups)
    rng = np.random.default_rng(BOOTSTRAP_SEED)

    def compute(sample: list[dict[str, Any]]) -> float | None:
        mp = _pairs(sample, y_key, model_key)
        hp = _pairs(sample, y_key, h0_key)
        if kind == "bss":
            bm = brier_score(mp)
            bh = brier_score(hp)
            if bm is None or bh in (None, 0):
                return None
            return 1.0 - bm / bh
        lm = log_loss(mp)
        lh = log_loss(hp)
        if lm is None or lh is None:
            return None
        return lm - lh

    observed = compute(eligible)
    draws = []
    for _ in range(BOOTSTRAP_B):
        if not keys:
            break
        pick = rng.choice(len(keys), size=len(keys), replace=True)
        sample = [r for idx in pick for r in groups[keys[int(idx)]]]
        val = compute(sample)
        if val is not None:
            draws.append(val)
    ci = [None, None] if not draws else [float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))]
    return {
        "observed": observed,
        "ci": ci,
        "n_rows": len(eligible),
        "n_games": len(keys),
        "excludes_zero": bool(ci[0] is not None and (ci[0] > 0 or ci[1] < 0)),
    }


def family_metrics(
    rows: list[dict[str, Any]],
    *,
    y_key: str,
    prefix: str,
    experiment_id: str,
) -> list[dict[str, Any]]:
    out = []
    pairs_h0 = _pairs(rows, y_key, f"p_{prefix}_{H0}")
    for family in (H0, H1, H2):
        pairs = _pairs(rows, y_key, f"p_{prefix}_{family}")
        brier = brier_score(pairs)
        brier_h0 = brier_score(pairs_h0)
        bss = None if brier is None or brier_h0 in (None, 0) else 1.0 - brier / brier_h0
        ll = log_loss(pairs)
        ll0 = log_loss(pairs_h0)
        skill = None
        dlog = None
        if family != H0:
            skill = _clustered_stat(rows, y_key=y_key, model_key=f"p_{prefix}_{family}", h0_key=f"p_{prefix}_{H0}", kind="bss")
            dlog = _clustered_stat(rows, y_key=y_key, model_key=f"p_{prefix}_{family}", h0_key=f"p_{prefix}_{H0}", kind="dlog")
        y_known = [r for r in rows if r.get(y_key) not in (None, NOT_APPLICABLE)]
        pos = sum(1 for r in y_known if r.get(y_key) == 1)
        unavail = sum(1 for r in rows if r.get(y_key) is None and r.get("core_state") not in {"HEALTHY", "RECOVERING", "HEALTHY_AFTER_RECOVERY", "UNRESOLVED", "PRE_ENTRY"})
        out.append(
            {
                "source_experiment_id": experiment_id,
                "target": y_key,
                "family": family,
                "eligible_N": len(pairs),
                "event_N": pos,
                "unavailable_N": unavail,
                "brier": brier,
                "bss_vs_H0": None if family == H0 else bss,
                "bss_ci": None if not skill else skill["ci"],
                "log_loss": ll,
                "delta_log_loss_vs_H0": None if family == H0 or ll is None or ll0 is None else ll - ll0,
                "delta_log_loss_ci": None if not dlog else dlog["ci"],
                "roc_auc": roc_auc(pairs),
                "pr_auc": pr_auc(pairs),
            }
        )
    return out


def probability_contrast(
    rows: list[dict[str, Any]],
    *,
    left: str,
    right: str,
    p_key: str,
) -> dict[str, Any]:
    labeled = [r for r in rows if r.get("core_state") in {left, right} and r.get(p_key) is not None]
    return clustered_mean_diff(
        labeled,
        value_key=p_key,
        positive_pred=lambda r, s=left: r.get("core_state") == s,
        negative_pred=lambda r, s=right: r.get("core_state") == s,
        seed=BOOTSTRAP_SEED,
        draws=BOOTSTRAP_B,
    )


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    if len(set(xs)) < 2 or len(set(ys)) < 2:
        return None
    rx = _ranks(xs)
    ry = _ranks(ys)
    return float(np.corrcoef(rx, ry)[0, 1])


def _ranks(vals: list[float]) -> list[float]:
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    ranks = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def clustered_spearman(
    rows: list[dict[str, Any]],
    *,
    x_key: str,
    y_key: str,
) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    usable = []
    for row in rows:
        if row.get(x_key) is None or row.get(y_key) is None:
            continue
        groups[str(row.get("internal_game_id") or row.get("trade_id"))].append(row)
        usable.append(row)
    keys = sorted(groups)
    observed = spearman([float(r[x_key]) for r in usable], [float(r[y_key]) for r in usable])
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = []
    for _ in range(BOOTSTRAP_B):
        if not keys:
            break
        pick = rng.choice(len(keys), size=len(keys), replace=True)
        sample = [r for idx in pick for r in groups[keys[int(idx)]]]
        val = spearman([float(r[x_key]) for r in sample], [float(r[y_key]) for r in sample])
        if val is not None and not np.isnan(val):
            draws.append(val)
    ci = [None, None] if not draws else [float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))]
    return {"observed": None if observed is not None and np.isnan(observed) else observed, "ci": ci, "n": len(usable)}
