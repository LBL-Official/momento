"""Measured integrity audit. Facts only."""

from __future__ import annotations

from typing import Any

import pandas as pd

from roller.austin.config import DEFAULT
from roller.austin.knn import match_query
from roller.austin.locks import N_TRADES
from roller.austin.outcomes import HOLD_EV_DEFINITION
from roller.austin.pca import transform_row
from roller.austin.registry import load_registry


LADDER = (80, 70, 60, 50, 42, 41, 40)


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        try:
            return _jsonable(value.item())
        except (ValueError, AttributeError):
            pass
    if isinstance(value, float):
        return int(value) if value.is_integer() else float(value)
    if isinstance(value, (int, str, bool)):
        return value
    return str(value)


def _row_to_query(rec: pd.Series) -> dict[str, Any]:
    side = _jsonable(rec.get("side")) or "home"
    return {
        "side": side,
        "query_mode": _jsonable(rec.get("query_mode")) or "POST_80",
        "query_source": "HISTORICAL_RECONSTRUCT",
        "entry_source": _jsonable(rec.get("entry_source")) or "CHOOSIN_604_CSV",
        "entry_price_cents": _jsonable(rec.get("entry_price_cents")),
        "current_price_cents": _jsonable(rec.get("current_price_cents")),
        "home_score_entry": _jsonable(rec.get("home_score_entry", rec.get("home_score"))),
        "away_score_entry": _jsonable(rec.get("away_score_entry", rec.get("away_score"))),
        "home_score_current": _jsonable(rec.get("home_score_current", rec.get("home_score"))),
        "away_score_current": _jsonable(rec.get("away_score_current", rec.get("away_score"))),
        "entry_quarter": _jsonable(rec.get("entry_quarter", rec.get("quarter"))),
        "current_quarter": _jsonable(rec.get("current_quarter", rec.get("quarter"))),
        "entry_seconds_remaining": _jsonable(rec.get("entry_seconds_remaining")),
        "current_seconds_remaining": _jsonable(rec.get("current_seconds_remaining", rec.get("seconds_remaining"))),
        "time_since_entry_sec": _jsonable(rec.get("time_since_entry_sec", rec.get("time_since_entry"))),
        "trade_id": _jsonable(rec.get("trade_id")),
        "snapshot_id": _jsonable(rec.get("snapshot_id")),
        "ticker": _jsonable(rec.get("ticker")),
    }


def ladder_recognition(snapshots: pd.DataFrame, model: dict[str, Any]) -> list[dict[str, Any]]:
    names = list(load_registry()["default_knn"])
    complete = snapshots.dropna(subset=names)
    if complete.empty:
        return []
    mat = complete[names].to_numpy(dtype=float)
    mu = [model["mu"][n] for n in names]
    sd = [model["sd"][n] if model["sd"][n] else 1.0 for n in names]
    import numpy as np

    z = (mat - np.array(mu)) / np.array(sd)
    scores = z @ np.asarray(model["components"]).T
    from roller.austin.query import _meta_from_frame

    meta = _meta_from_frame(complete)
    rows = []
    for px in LADDER:
        if px == 80:
            pool = complete[complete["kind"] == "entry"]
        else:
            pool = complete[(complete["kind"] != "entry") & (complete["current_price_cents"] == px)]
        if pool.empty:
            pool = complete[
                (complete["kind"] != "entry")
                & (complete["current_price_cents"] >= px - 1)
                & (complete["current_price_cents"] <= px + 1)
            ]
        if pool.empty:
            rows.append({"target_price": px, "n_source": 0, "status": "UNAVAILABLE"})
            continue
        rec = pool.iloc[0]
        numeric = {n: rec.get(n) for n in names}
        vec = transform_row(numeric, model)
        if vec is None:
            rows.append({"target_price": px, "n_source": int(len(pool)), "status": "INSUFFICIENT_SAMPLE"})
            continue
        match = match_query(
            vec,
            scores,
            meta,
            exclude_trade_id=str(rec["trade_id"]),
            exclude_snapshot_id=str(rec["snapshot_id"]),
        )
        neigh = match.get("neighbors") or []
        currents = [n.get("current_price_cents") for n in neigh if n.get("current_price_cents") is not None]
        travels = [n.get("price_travel") for n in neigh if n.get("price_travel") is not None]
        rows.append(
            {
                "target_price": px,
                "n_source": int(len(pool)),
                "query_current": rec.get("current_price_cents"),
                "query_travel": rec.get("price_travel"),
                "query_time_since_entry": rec.get("time_since_entry"),
                "neighbor_median_current": None if not currents else float(pd.Series(currents).median()),
                "neighbor_median_travel": None if not travels else float(pd.Series(travels).median()),
                "weighted_mean_EV": match.get("weighted_mean_EV"),
                "median_distance": match.get("median_distance"),
                "status": match.get("status"),
            }
        )
    return rows


def run_integrity(
    *,
    snapshots: pd.DataFrame,
    model: dict[str, Any],
    coverage: dict[str, Any],
    hedge: dict[str, Any],
    calibration: dict[str, Any],
) -> dict[str, Any]:
    ladder = ladder_recognition(snapshots, model)
    res = (coverage.get("hedge_trigger_resolution") or hedge.get("resolution") or {})
    return {
        "model_version": DEFAULT.model_version,
        "dataset_version": DEFAULT.dataset_version,
        "ev_definition": HOLD_EV_DEFINITION,
        "n_trades": coverage.get("n_trades"),
        "lock_n": N_TRADES,
        "identity_lock_status": "PASS" if coverage.get("n_trades") == N_TRADES else "FAIL",
        "path_coverage": {
            "n_path_complete": coverage.get("n_path_complete"),
            "n_path_partial": coverage.get("n_path_partial"),
            "n_path_unavailable": coverage.get("n_path_unavailable"),
            "definition": coverage.get("path_complete_definition"),
        },
        "hedge_41_vs_42": res,
        "ladder": ladder,
        "calibration": {
            "status": calibration.get("status"),
            "reason": calibration.get("reason"),
            "table": calibration.get("table") or [],
            "oos_n": calibration.get("oos_n"),
        },
        "knn_target": "pnl_hold_after_t",
        "note": "POST-80 estimates outcomes after t. Not a replay of the original 80/40 ledger.",
    }


def example_fixtures(snapshots: pd.DataFrame) -> dict[str, Any]:
    if snapshots.empty:
        return {}
    entry = snapshots[snapshots["kind"] == "entry"]
    path42 = snapshots[
        (snapshots["kind"] != "entry")
        & (pd.to_numeric(snapshots["current_price_cents"], errors="coerce") == 42)
    ]
    scored = path42.dropna(subset=["home_score_current", "away_score_current"])
    scored = scored[pd.to_numeric(scored["home_score_current"], errors="coerce").fillna(0) > 0]
    if "home_score_entry" in scored.columns:
        with_entry = scored[pd.to_numeric(scored["home_score_entry"], errors="coerce").fillna(0) > 0]
        if not with_entry.empty:
            scored = with_entry
    if not scored.empty:
        path42 = scored
    if path42.empty:
        path42 = snapshots[
            (snapshots["kind"] != "entry")
            & (pd.to_numeric(snapshots["current_price_cents"], errors="coerce").between(41, 43))
        ]
    out: dict[str, Any] = {}
    if not entry.empty:
        rec = entry.iloc[0]
        out["entry"] = _row_to_query(rec)
        out["entry"]["note"] = "Historical FIRST80 entry. Not live."
    if not path42.empty:
        rec = path42.iloc[0]
        body = _row_to_query(rec)
        body["query_mode"] = "POST_80"
        body["note"] = "Historical POST-80 ~42¢ fixture. Not live."
        out["post80_42"] = body
    return out
