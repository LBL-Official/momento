"""PHASE 8–12 — KNN, matching, distance geometry, homogeneity, permutation null."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from roller.nba_8040_reverse_features.deep_quant.util import (
    KS,
    NULL_SEED,
    PERMUTATIONS,
    binary_entropy,
    pairwise_euclidean,
)


def _neighbor_take(order: np.ndarray, row: int, k: int) -> np.ndarray:
    return np.array([idx for idx in order if idx != row][:k], dtype=int)


def knn_tables(
    z: np.ndarray,
    aligned: pd.DataFrame,
    *,
    ks: tuple[int, ...] = KS,
) -> dict[str, Any]:
    dist = pairwise_euclidean(z)
    np.fill_diagonal(dist, np.inf)
    n = len(aligned)
    periods = aligned["period"].to_numpy()
    t40 = aligned["t40"].to_numpy(dtype=bool)
    survive = aligned["s"].to_numpy(dtype=bool)
    ids = aligned["instance_id"].to_numpy()
    summaries = []
    long_rows = []
    max_k = max(ks)
    for row in range(n):
        order = np.argsort(dist[row])
        take_all = _neighbor_take(order, row, max_k)
        for rank, nbr in enumerate(take_all, start=1):
            long_rows.append(
                {
                    "instance_id": ids[row],
                    "period": periods[row],
                    "own_t40": bool(t40[row]),
                    "own_s": bool(survive[row]),
                    "neighbor_rank": rank,
                    "neighbor_id": ids[nbr],
                    "neighbor_period": periods[nbr],
                    "neighbor_t40": bool(t40[nbr]),
                    "neighbor_s": bool(survive[nbr]),
                    "distance": float(dist[row, nbr]),
                    "cross_period": periods[nbr] != periods[row],
                }
            )
        for k in ks:
            take = take_all[:k]
            summaries.append(
                {
                    "instance_id": ids[row],
                    "period": periods[row],
                    "k": k,
                    "mean_distance": float(dist[row, take].mean()),
                    "neighbor_q2_share": float((periods[take] == "Q2").mean()),
                    "neighbor_t40_rate": float(t40[take].mean()),
                    "neighbor_s_rate": float(survive[take].mean()),
                    "outcome_agreement": float((t40[take] == t40[row]).mean()),
                    "cross_period_share": float((periods[take] != periods[row]).mean()),
                    "entropy": binary_entropy(float(t40[take].mean())),
                }
            )
    summary = pd.DataFrame(summaries)
    agreement = []
    for k in ks:
        block = summary[summary["k"] == k]
        agreement.append(
            {
                "k": k,
                "n": int(len(block)),
                "mean_agreement": float(block["outcome_agreement"].mean()),
                "mean_entropy": float(block["entropy"].mean()),
                "mean_neighbor_t40": float(block["neighbor_t40_rate"].mean()),
                "mean_cross_period_share": float(block["cross_period_share"].mean()),
                "mean_distance": float(block["mean_distance"].mean()),
            }
        )
    return {
        "distance": dist,
        "neighbors": pd.DataFrame(long_rows),
        "summary": summary,
        "agreement": agreement,
    }


def cross_period_match(dist: np.ndarray, aligned: pd.DataFrame, *, k: int = 10) -> pd.DataFrame:
    periods = aligned["period"].to_numpy()
    t40 = aligned["t40"].to_numpy(dtype=bool)
    survive = aligned["s"].to_numpy(dtype=bool)
    ids = aligned["instance_id"].to_numpy()
    rows = []
    for source, target in (("Q2", "Q3"), ("Q3", "Q2")):
        src = np.where(periods == source)[0]
        dst = np.where(periods == target)[0]
        for row in src:
            order = dst[np.argsort(dist[row, dst])]
            take = order[:k]
            for rank, nbr in enumerate(take, start=1):
                rows.append(
                    {
                        "instance_id": ids[row],
                        "source_period": source,
                        "match_period": target,
                        "k": k,
                        "neighbor_rank": rank,
                        "neighbor_id": ids[nbr],
                        "distance": float(dist[row, nbr]),
                        "own_t40": bool(t40[row]),
                        "neighbor_t40": bool(t40[nbr]),
                        "own_s": bool(survive[row]),
                        "neighbor_s": bool(survive[nbr]),
                    }
                )
    return pd.DataFrame(rows)


def match_summary(matches: pd.DataFrame, k: int = 10) -> list[dict[str, Any]]:
    rows = []
    for source in ("Q2", "Q3"):
        block = matches[(matches["source_period"] == source) & (matches["neighbor_rank"] <= k)]
        if block.empty:
            continue
        grouped = block.groupby("instance_id", sort=False)
        own = grouped["own_t40"].first()
        neigh = grouped["neighbor_t40"].mean()
        rows.append(
            {
                "source_period": source,
                "match_period": "Q3" if source == "Q2" else "Q2",
                "k": k,
                "n": int(len(own)),
                "source_t40": float(own.mean()),
                "matched_t40": float(neigh.mean()),
                "difference": float(own.mean() - neigh.mean()),
                "source_s": float(grouped["own_s"].first().mean()),
                "matched_s": float(grouped["neighbor_s"].mean().mean()),
                "median_nearest_distance": float(block[block["neighbor_rank"] == 1]["distance"].median()),
            }
        )
    return rows


def distance_geometry(dist: np.ndarray, aligned: pd.DataFrame) -> dict[str, Any]:
    periods = aligned["period"].to_numpy()
    q2 = np.where(periods == "Q2")[0]
    q3 = np.where(periods == "Q3")[0]
    within_q2 = dist[np.ix_(q2, q2)].copy()
    within_q3 = dist[np.ix_(q3, q3)].copy()
    np.fill_diagonal(within_q2, np.inf)
    np.fill_diagonal(within_q3, np.inf)
    q2_to_q3 = dist[np.ix_(q2, q3)].min(axis=1)
    q3_to_q2 = dist[np.ix_(q3, q2)].min(axis=1)
    q2_to_q2 = within_q2.min(axis=1)
    q3_to_q3 = within_q3.min(axis=1)
    ratio_q2 = q2_to_q3 / np.maximum(q2_to_q2, 1e-12)
    ratio_q3 = q3_to_q2 / np.maximum(q3_to_q3, 1e-12)
    med_ratio = float(np.median(np.concatenate([ratio_q2, ratio_q3])))
    if med_ratio < 1.15:
        support = "largely_overlapping"
    elif med_ratio < 1.75:
        support = "partially_separated"
    else:
        support = "strongly_separated"
    def _q(arr: np.ndarray) -> dict[str, float]:
        return {
            "p10": float(np.quantile(arr, 0.10)),
            "p25": float(np.quantile(arr, 0.25)),
            "p50": float(np.quantile(arr, 0.50)),
            "p75": float(np.quantile(arr, 0.75)),
            "p90": float(np.quantile(arr, 0.90)),
            "mean": float(arr.mean()),
        }
    return {
        "support": support,
        "median_cross_over_within": med_ratio,
        "q2_to_q3": _q(q2_to_q3),
        "q3_to_q2": _q(q3_to_q2),
        "within_q2": _q(q2_to_q2),
        "within_q3": _q(q3_to_q3),
        "ratio_q2": _q(ratio_q2),
        "ratio_q3": _q(ratio_q3),
        "nearest_q2_to_q3": q2_to_q3,
        "nearest_q3_to_q2": q3_to_q2,
    }


def permutation_null(
    summary: pd.DataFrame,
    aligned: pd.DataFrame,
    matches: pd.DataFrame,
    *,
    seed: int = NULL_SEED,
    n_perm: int = PERMUTATIONS,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    t40 = aligned["t40"].to_numpy(dtype=bool)
    ids = aligned["instance_id"].to_numpy()
    id_to_pos = {iid: i for i, iid in enumerate(ids)}
    observed_agree = {
        int(k): float(summary.loc[summary["k"] == k, "outcome_agreement"].mean())
        for k in summary["k"].unique()
    }
    # Rebuild agreement from neighbor table would need neighbors; use summary's
    # instance-level neighbors via stored rates? We recompute from matches + k=10
    # For KNN agreement we need neighbor identities. Caller passes neighbors.
    return {
        "seed": seed,
        "n_perm": n_perm,
        "observed_agreement": observed_agree,
        "t40": t40,
        "id_to_pos": id_to_pos,
        "rng_ready": True,
    }


def permutation_from_neighbors(
    neighbors: pd.DataFrame,
    aligned: pd.DataFrame,
    matches: pd.DataFrame,
    *,
    seed: int = NULL_SEED,
    n_perm: int = PERMUTATIONS,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    ids = aligned["instance_id"].to_numpy()
    t40 = aligned["t40"].to_numpy(dtype=bool)
    pos = {iid: i for i, iid in enumerate(ids)}
    observed = {}
    for k in KS:
        block = neighbors[neighbors["neighbor_rank"] <= k]
        agree = []
        for iid, grp in block.groupby("instance_id", sort=False):
            own = bool(t40[pos[iid]])
            agree.append(float((grp["neighbor_t40"].to_numpy() == own).mean()))
        observed[k] = float(np.mean(agree))
    null_agree = {k: [] for k in KS}
    null_match_diff = []
    for _ in range(n_perm):
        shuffled = rng.permutation(t40)
        for k in KS:
            block = neighbors[neighbors["neighbor_rank"] <= k]
            agree = []
            for iid, grp in block.groupby("instance_id", sort=False):
                own = bool(shuffled[pos[iid]])
                nbr = np.array([shuffled[pos[nid]] for nid in grp["neighbor_id"]])
                agree.append(float((nbr == own).mean()))
            null_agree[k].append(float(np.mean(agree)))
        q2 = matches[(matches["source_period"] == "Q2") & (matches["neighbor_rank"] <= 10)]
        own = q2.groupby("instance_id")["instance_id"].first()
        src_rate = np.mean([shuffled[pos[iid]] for iid in own.index])
        matched = []
        for iid, grp in q2.groupby("instance_id"):
            matched.append(np.mean([shuffled[pos[nid]] for nid in grp["neighbor_id"]]))
        q3_ids = aligned.loc[aligned["period"].eq("Q3"), "instance_id"]
        q3_rate = float(np.mean([shuffled[pos[iid]] for iid in q3_ids]))
        null_match_diff.append(float(src_rate - np.mean(matched)))
    rows = []
    for k in KS:
        arr = np.array(null_agree[k])
        obs = observed[k]
        rows.append(
            {
                "k": k,
                "observed_agreement": obs,
                "null_mean": float(arr.mean()),
                "null_p50": float(np.median(arr)),
                "null_p025": float(np.quantile(arr, 0.025)),
                "null_p975": float(np.quantile(arr, 0.975)),
                "percentile_of_observed": float((arr <= obs).mean()),
            }
        )
    nd = np.array(null_match_diff)
    return {
        "seed": seed,
        "n_perm": n_perm,
        "agreement": rows,
        "match_diff_null": {
            "null_mean": float(nd.mean()),
            "null_p025": float(np.quantile(nd, 0.025)),
            "null_p975": float(np.quantile(nd, 0.975)),
        },
    }
