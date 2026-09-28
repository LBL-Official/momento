"""Fixed-k neighborhood diagnostics. Not a classifier. No EV-tuned k."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from roller.nba_8040_reverse_features.locks import GAIN_CENTS, LOSS_CENTS
from roller.nba_8040_reverse_features.matrix import coverage_names, standardized_matrix
from roller.choosin_texas.ev import book_cents

KS = (5, 10, 20, 30)


def _default_names(features: pd.DataFrame, names: list[str] | None) -> list[str]:
    return names or coverage_names(features, min_frac=0.90)


def _labels_aligned(features: pd.DataFrame, labels: pd.DataFrame, index: pd.Index) -> pd.DataFrame:
    kept = features.loc[index, ["instance_id", "period"]].reset_index(drop=True)
    labs = labels.set_index("instance_id").loc[kept["instance_id"]].reset_index()
    return pd.concat([kept.reset_index(drop=True), labs[["s", "t40", "ev_contribution"]]], axis=1)


def neighborhood_table(
    features: pd.DataFrame,
    labels: pd.DataFrame,
    names: list[str] | None = None,
    *,
    ks: tuple[int, ...] = KS,
    within: bool = False,
) -> list[dict[str, Any]]:
    used = _default_names(features, names)
    matrix, _used, index = standardized_matrix(features, used)
    meta = _labels_aligned(features, labels, index)
    survive = meta["s"].to_numpy(dtype=bool)
    ev = meta["ev_contribution"].to_numpy(dtype=float)
    periods = meta["period"].to_numpy()
    dist = np.sqrt(((matrix[:, None, :] - matrix[None, :, :]) ** 2).sum(axis=2))
    np.fill_diagonal(dist, np.inf)
    rows = []
    for period in ("Q2", "Q3", "ALL"):
        if period == "ALL":
            mask = np.ones(len(meta), dtype=bool)
        else:
            mask = periods == period
        idx = np.where(mask)[0]
        if len(idx) < max(ks) + 2:
            continue
        for k in ks:
            agreements = []
            neigh_ev = []
            for row in idx:
                if within:
                    allowed = np.where(periods == periods[row])[0]
                else:
                    allowed = np.arange(len(meta))
                order = allowed[np.argsort(dist[row, allowed])]
                take = [item for item in order if item != row][:k]
                if len(take) < k:
                    continue
                neigh = survive[take]
                agreements.append(float((neigh == survive[row]).mean()))
                neigh_ev.append(float(ev[take].mean()))
            if not agreements:
                continue
            rows.append(
                {
                    "period": period,
                    "k": k,
                    "n": len(agreements),
                    "mean_neighbor_ev": float(np.mean(neigh_ev)),
                    "outcome_agreement": float(np.mean(agreements)),
                    "scope": "within-period" if within else "pooled",
                }
            )
    return rows


def cross_period_match(
    features: pd.DataFrame,
    labels: pd.DataFrame,
    *,
    k: int = 10,
) -> list[dict[str, Any]]:
    used = coverage_names(features, min_frac=0.90)
    matrix, _used, index = standardized_matrix(features, used)
    meta = _labels_aligned(features, labels, index)
    periods = meta["period"].to_numpy()
    t40 = meta["t40"].to_numpy(dtype=bool)
    ev = meta["ev_contribution"].to_numpy(dtype=float)
    dist = np.sqrt(((matrix[:, None, :] - matrix[None, :, :]) ** 2).sum(axis=2))
    np.fill_diagonal(dist, np.inf)
    out = []
    for source, match in (("Q2", "Q3"), ("Q3", "Q2")):
        src = np.where(periods == source)[0]
        dst = np.where(periods == match)[0]
        if len(src) == 0 or len(dst) < k:
            continue
        src_t40 = []
        match_t40 = []
        src_ev = []
        match_ev = []
        for row in src:
            order = dst[np.argsort(dist[row, dst])][:k]
            src_t40.append(float(t40[row]))
            match_t40.append(float(t40[order].mean()))
            src_ev.append(float(ev[row]))
            match_ev.append(float(ev[order].mean()))
        n = len(src_t40)
        src_rate = float(np.mean(src_t40))
        match_rate = float(np.mean(match_t40))
        out.append(
            {
                "source_period": source,
                "match_period": match,
                "k": k,
                "n": n,
                "source_t40_rate": src_rate,
                "matched_t40_rate": match_rate,
                "difference": src_rate - match_rate,
                "source_ev": float(np.mean(src_ev)),
                "matched_ev": float(np.mean(match_ev)),
            }
        )
    return out


def null_agreement(features: pd.DataFrame, labels: pd.DataFrame, *, k: int = 10, seed: int = 80) -> dict[str, float]:
    used = coverage_names(features, min_frac=0.90)
    fake = labels.copy()
    rng = np.random.default_rng(seed)
    fake["s"] = rng.permutation(fake["s"].to_numpy())
    table = neighborhood_table(features, fake, used, ks=(k,), within=True)
    real = neighborhood_table(features, labels, used, ks=(k,), within=True)
    real_agree = float(np.mean([row["outcome_agreement"] for row in real])) if real else 0.0
    null_agree = float(np.mean([row["outcome_agreement"] for row in table])) if table else 0.0
    return {"k": float(k), "real_agreement": real_agree, "null_agreement": null_agree}


def stability_splits(features: pd.DataFrame, labels: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for split in ("IN_SAMPLE", "VALIDATION", "OOS"):
        mask = features["dataset_split"].eq(split)
        sub_f = features.loc[mask].reset_index(drop=True)
        sub_l = labels.loc[labels["instance_id"].isin(sub_f["instance_id"])].reset_index(drop=True)
        if len(sub_f) < 40:
            rows.append({"split": split, "n": int(len(sub_f)), "status": "n too small"})
            continue
        q2 = sub_l[sub_l["period"] == "Q2"]
        q3 = sub_l[sub_l["period"] == "Q3"]
        def ev(block: pd.DataFrame) -> float | None:
            if block.empty:
                return None
            s_n = int(block["s"].sum())
            n = int(len(block))
            return float(book_cents(s_n, n, gain=GAIN_CENTS, loss=LOSS_CENTS) / n)
        rows.append(
            {
                "split": split,
                "n": int(len(sub_f)),
                "q2_n": int(len(q2)),
                "q3_n": int(len(q3)),
                "q2_ev": ev(q2),
                "q3_ev": ev(q3),
                "q2_minus_q3": None if ev(q2) is None or ev(q3) is None else ev(q2) - ev(q3),
            }
        )
    return rows
