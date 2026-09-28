"""Bucket assignment: frozen score bins + TRAIN-only quantile edges."""

from __future__ import annotations

import math

from common import MIN_BUCKET_N_TRAIN, frozen_score_bucket, split_rows


def _finite(xs):
    out = []
    for x in xs:
        if x is None:
            continue
        try:
            v = float(x)
        except (TypeError, ValueError):
            continue
        if math.isnan(v) or math.isinf(v):
            continue
        out.append(v)
    return out


def train_quantiles(train_rows, col: str, probs):
    xs = _finite(r.get(col) for r in train_rows)
    if len(xs) < MIN_BUCKET_N_TRAIN:
        return None
    xs.sort()
    edges = []
    n = len(xs)
    for p in probs:
        i = min(n - 1, max(0, int(round(p * (n - 1)))))
        edges.append(xs[i])
    # ensure strictly increasing by jittering duplicates
    for i in range(1, len(edges)):
        if edges[i] <= edges[i - 1]:
            edges[i] = edges[i - 1]
    return edges


def apply_edges(value, edges, labels):
    if value is None or edges is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    for i, e in enumerate(edges):
        if v <= e:
            return labels[i]
    return labels[-1]


def pace_bucket(ppm, edges) -> str | None:
    """edges = [p25, p75, p90] from TRAIN."""
    if ppm is None or edges is None or len(edges) < 3:
        return "PACE_UNKNOWN"
    v = float(ppm)
    if v <= edges[0]:
        return "LOW"
    if v <= edges[1]:
        return "NORMAL"
    if v <= edges[2]:
        return "HIGH"
    return "EXTREME"


def assign(rows: list[dict], edges: dict) -> list[dict]:
    out = []
    for r in rows:
        rec = {
            "observation_id": r["observation_id"],
            "dataset_split": r.get("dataset_split"),
            "alignment_confidence": r.get("alignment_confidence"),
            "Y_40_CLOSE": r.get("Y_40_CLOSE"),
            "Y_40_WICK": r.get("Y_40_WICK"),
            "maker_fill_confidence": r.get("maker_fill_confidence"),
            "score_diff_frozen_bucket": frozen_score_bucket(r.get("score_differential")),
            "quarter_bucket": None
            if r.get("quarter") is None
            else (f"OT" if int(r["quarter"]) >= 5 else f"Q{int(r['quarter'])}"),
            "path_state": r.get("path_state"),
            "GAME_MARKET_ALIGNMENT": r.get("GAME_MARKET_ALIGNMENT"),
            "pace_bucket": pace_bucket(r.get("points_per_game_minute"), edges.get("pace")),
        }
        qe = edges.get("quantiles") or {}
        for col, (ed, labs) in qe.items():
            rec[f"{col}_qbucket"] = apply_edges(r.get(col), ed, labs)
        out.append(rec)
    return out


def fit_edges(train_rows: list[dict]) -> dict:
    quint_cols = [
        "score_differential",
        "number_of_lead_changes",
        "current_lead_duration_s",
        "score_differential_stdev",
        "comeback_magnitude",
        "lead_decay",
        "vol_5m_cents",
        "momentum_5m_cents",
        "minutes_from_50_to_80",
        "total_points",
        "maximum_deficit_overcome",
        "distance_from_max_lead",
    ]
    quantiles = {}
    labels = ["Q1", "Q2", "Q3", "Q4", "Q5"]
    for col in quint_cols:
        ed = train_quantiles(train_rows, col, [0.2, 0.4, 0.6, 0.8])
        quantiles[col] = (ed, labels)
    pace = train_quantiles(train_rows, "points_per_game_minute", [0.25, 0.75, 0.90])
    return {"quantiles": quantiles, "pace": pace}
