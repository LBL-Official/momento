"""Correlation, ablation, and bucket labs. Batch artifacts, not live tuners."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from roller.austin.mathutil import pearson, spearman
from roller.austin.registry import load_registry


TARGETS = (
    "pnl_hold_after_t",
    "final_pnl_taker_8040_cents",
    "final_pnl_hold_cents",
    "won",
    "csv_t40",
    "hit_40_after",
    "max_adverse_excursion_after",
    "max_favorable_excursion_after",
)

TRAVEL_FEATURES = {
    "price_travel",
    "score_travel",
    "score_differential_travel",
    "time_since_entry",
    "current_price_cents",
}

ABLATIONS = {
    "price_only": ["entry_price_cents", "current_price_cents", "price_travel"],
    "price_time": ["entry_price_cents", "current_price_cents", "price_travel", "time_since_entry", "seconds_remaining"],
    "price_score": ["entry_price_cents", "score_differential", "score_travel"],
    "price_score_diff_time": [
        "entry_price_cents",
        "score_differential",
        "time_since_entry",
        "seconds_remaining",
    ],
    "price_score_score_diff_time": [
        "entry_price_cents",
        "score",
        "score_differential",
        "time_since_entry",
    ],
    "full_default": None,
}


def _corr_status(x: np.ndarray, y: np.ndarray) -> str:
    mask = np.isfinite(x) & np.isfinite(y)
    if int(mask.sum()) < 3:
        return "INSUFFICIENT_SAMPLE"
    if float(np.nanstd(x[mask])) <= 1e-12 or float(np.nanstd(y[mask])) <= 1e-12:
        return "ZERO_VARIANCE"
    return "VALUE"


def correlations(snapshots: pd.DataFrame) -> list[dict[str, Any]]:
    names = list(load_registry()["default_knn"])
    path = snapshots[snapshots["kind"] != "entry"].copy()
    entry = snapshots[snapshots["kind"] == "entry"].copy()
    rows = []
    for name in names:
        work = path if name in TRAVEL_FEATURES else entry
        x = pd.to_numeric(work[name], errors="coerce").to_numpy() if name in work.columns else np.array([])
        for target in TARGETS:
            if target not in work.columns:
                continue
            y = pd.to_numeric(work[target], errors="coerce").to_numpy()
            mask = np.isfinite(x) & np.isfinite(y)
            status = _corr_status(x, y)
            rows.append(
                {
                    "feature": name,
                    "target": target,
                    "pearson": None if status != "VALUE" else pearson(x, y),
                    "spearman": None if status != "VALUE" else spearman(x, y),
                    "sample_count": int(mask.sum()),
                    "status": status,
                    "snapshot_kind": "path" if name in TRAVEL_FEATURES else "entry",
                    "note": "CORRELATION ≠ CAUSATION",
                }
            )
    return rows


def buckets(snapshots: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    path = snapshots[snapshots["kind"] != "entry"].copy()
    entry = snapshots[snapshots["kind"] == "entry"].copy()
    out: dict[str, list[dict[str, Any]]] = {}
    out["entry_price"] = _bucket(
        entry,
        "entry_price_cents",
        [(-1, 70), (70, 75), (75, 80), (80, 85), (85, 10_000)],
        labels=["<70", "70-75", "75-80", "80-85", "85+"],
    )
    out["snapshot_price"] = _bucket(
        path,
        "current_price_cents",
        [(-1, 40), (40, 42), (42, 50), (50, 60), (60, 70), (70, 80), (80, 10_000)],
        labels=["<=40", "41-42", "43-50", "51-60", "61-70", "71-80", "80+"],
    )
    out["price_travel"] = _bucket(
        path,
        "price_travel",
        [(-10_000, -40), (-39, -20), (-19, -10), (-9, -1), (0, 0), (1, 10_000)],
        labels=["<=-40", "-39--20", "-19--10", "-9--1", "0", ">0"],
    )
    out["score_differential"] = _bucket(
        entry,
        "score_differential",
        [(-10_000, -10), (-9, -5), (-4, -1), (0, 0), (1, 4), (5, 9), (10, 10_000)],
        labels=["<=-10", "-9--5", "-4--1", "0", "+1-+4", "+5-+9", ">=+10"],
    )
    out["time"] = _bucket(
        entry,
        "quarter_progress",
        [(-0.01, 0.33), (0.33, 0.66), (0.66, 1.01)],
        labels=["early", "middle", "late"],
    )
    return out


def _bucket(
    frame: pd.DataFrame,
    col: str,
    edges: list[tuple[float, float]],
    labels: list[str],
) -> list[dict[str, Any]]:
    if col not in frame.columns:
        return []
    x = pd.to_numeric(frame[col], errors="coerce")
    rows = []
    for (lo, hi), lab in zip(edges, labels):
        if lo == hi:
            mask = x == lo
        else:
            mask = (x >= lo) & (x <= hi)
        sub = frame.loc[mask]
        n = int(len(sub))
        pnl = pd.to_numeric(sub.get("pnl_hold_after_t", sub.get("final_pnl_taker_8040_cents")), errors="coerce")
        rows.append(
            {
                "bucket": lab,
                "n": n,
                "mean_PNL": None if n == 0 else float(pnl.mean()),
                "median_PNL": None if n == 0 else float(pnl.median()),
                "EV": None if n == 0 else float(pnl.mean()),
                "win_rate": None if n == 0 else float(pd.to_numeric(sub.get("won"), errors="coerce").mean()),
                "MAE": None
                if n == 0
                else float(pd.to_numeric(sub.get("max_adverse_excursion_after"), errors="coerce").mean()),
                "MFE": None
                if n == 0
                else float(pd.to_numeric(sub.get("max_favorable_excursion_after"), errors="coerce").mean()),
            }
        )
    return rows


def interactions(snapshots: pd.DataFrame) -> list[dict[str, Any]]:
    path = snapshots[snapshots["kind"] != "entry"].copy()
    entry = snapshots[snapshots["kind"] == "entry"].copy()
    pairs = (
        (entry, "entry_price_cents", "score_differential"),
        (path, "current_price_cents", "score_differential"),
        (path, "price_travel", "score_travel"),
        (path, "price_travel", "time_since_entry"),
    )
    rows = []
    for work, a, b in pairs:
        if a not in work.columns or b not in work.columns:
            continue
        xa = pd.to_numeric(work[a], errors="coerce")
        xb = pd.to_numeric(work[b], errors="coerce")
        pnl = pd.to_numeric(work.get("pnl_hold_after_t", work.get("final_pnl_taker_8040_cents")), errors="coerce")
        mask = xa.notna() & xb.notna() & pnl.notna()
        rows.append(
            {
                "pair": f"{a} x {b}",
                "n": int(mask.sum()),
                "mean_PNL": None if int(mask.sum()) == 0 else float(pnl[mask].mean()),
                "note": "CORRELATION ≠ CAUSATION",
            }
        )
    return rows


def ablation_note() -> dict[str, Any]:
    return {
        "sets": list(ABLATIONS),
        "note": "Ablation compares declared subsets. Default KNN uses full_default only.",
        "default": load_registry()["default_knn"],
    }
