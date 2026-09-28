"""Query the 78/67 fit. PRE_78 stays out of the KNN."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from roller.austin.errors import AustinError
from roller.austin.features import build_feature_vector
from roller.austin.knn import match_query
from roller.austin.pca import transform_row
from roller.austin.raw_state import RawState, entry_probe, raw_from_query
from roller.austin.sizing import recommend_band
from roller.austin_first78.config import CFG, EV_DEFINITION, EV_FORMULA, distance_from_78


def public_mode(mode: str) -> str:
    return {"PRE_80": "PRE_78", "INTRA_80": "INTRA_78", "POST_80": "POST_78"}.get(str(mode), str(mode))


def _internal_mode(mode: str) -> str:
    text = str(mode or "POST_78").strip().upper().replace("-", "_")
    if text in {"PRE_78", "PRE_80"}:
        return "PRE_80"
    if text in {"INTRA_78", "INTRA_80"}:
        return "INTRA_80"
    return "POST_80"


def attach_distance(bundle: dict[str, Any]) -> dict[str, Any]:
    entry = (bundle.get("numeric") or {}).get("entry_price_cents")
    dist = distance_from_78(None if entry is None else float(entry))
    bundle.setdefault("numeric", {})["distance_from_78"] = dist
    bundle.setdefault("features", {})["distance_from_78"] = {
        "value": dist,
        "status": "NOT_APPLICABLE" if dist is None else "VALUE",
    }
    return bundle


def query_from_body(body: dict[str, Any]) -> RawState:
    if body.get("side") in (None, ""):
        raise AustinError("QUERY_REJECTED", "missing side")
    translated = dict(body)
    translated["query_mode"] = _internal_mode(str(body.get("query_mode") or "POST_78"))
    if translated["query_mode"] == "PRE_80":
        translated["entry_price_cents"] = None
        return raw_from_query(translated)
    if translated.get("entry_price_cents") in (None, ""):
        raise AustinError("QUERY_REJECTED", "missing entry_price_cents")
    if translated.get("current_price_cents") in (None, ""):
        raise AustinError("QUERY_REJECTED", "missing current_price_cents")
    return raw_from_query(translated)


def _meta(complete: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for rec in complete.itertuples(index=False):
        rows.append(
            {
                "snapshot_id": rec.snapshot_id,
                "trade_id": rec.trade_id,
                "game_date": rec.game_date,
                "quarter": rec.quarter,
                "ticker": rec.ticker,
                "kind": rec.kind,
                "entry_price_cents": rec.entry_price_cents,
                "current_price_cents": rec.current_price_cents,
                "score_differential": getattr(rec, "score_differential", None),
                "time_since_entry": getattr(rec, "time_since_entry", None),
                "price_travel": getattr(rec, "price_travel", None),
                "pnl_hold_after_t": getattr(rec, "pnl_hold_after_t", None),
                "pnl_8040_after_t": getattr(rec, "pnl_7867_after_t", None),
                "pnl_8040_after_t_status": getattr(rec, "pnl_7867_after_t_status", None),
                "csv_t40": bool(getattr(rec, "t67", False)),
                "hit_40_after": bool(getattr(rec, "hit_67_after", False)),
                "final_pnl_hold_cents": getattr(rec, "final_pnl_hold_cents", None),
                "final_pnl_taker_8040_cents": getattr(rec, "final_pnl_taker_7867_cents", None),
                "settlement": rec.settlement,
                "won": bool(rec.won),
            }
        )
    return rows


def query_match(
    raw: RawState,
    *,
    snapshots: pd.DataFrame,
    model: dict[str, Any],
    calibration: dict[str, Any],
    k: int | None = None,
    include_entry_change: bool = True,
) -> dict[str, Any]:
    bundle = attach_distance(build_feature_vector(raw))
    mode = public_mode(raw.query_mode)
    base = {
        "data_mode": CFG.data_mode,
        "live_feed": "UNAVAILABLE",
        "live_execution": False,
        "submits": False,
        "query_is_training": False,
        "query_mode": mode,
        "decision": None,
        "buy_skip": False,
        "path_mode": bundle.get("path_mode"),
        "features": bundle,
        "derived": {
            "price_travel": bundle["numeric"].get("price_travel"),
            "score_travel": bundle["numeric"].get("score_travel"),
            "score_differential_travel": bundle["numeric"].get("score_differential_travel"),
            "time_since_entry": bundle["numeric"].get("time_since_entry"),
            "distance_from_78": bundle["numeric"].get("distance_from_78"),
        },
        "availability": {name: cell.get("status") for name, cell in (bundle.get("features") or {}).items()},
        "feature_coverage": bundle.get("feature_coverage"),
        "model_version": CFG.model_version,
        "dataset_version": CFG.dataset_version,
        "ev_definition": EV_DEFINITION,
        "ev_formula": EV_FORMULA,
        "fee_model_status": "UNAVAILABLE",
        "fill_model_status": "FILL_UNAVAILABLE",
    }
    if raw.query_mode == "PRE_80" or raw.entry_price_cents is None:
        return {
            **base,
            "status": "INSUFFICIENT_SAMPLE",
            "knn_status": "INSUFFICIENT_SAMPLE",
            "reason": "NO_ENTRY_IN_FITTED_SPACE",
            "match": None,
            "sizing": None,
            "conditional_ev": None,
            "note": "PRE_78 state only. The fitted KNN requires a 78¢ entry.",
        }
    names = list(model["names"])
    missing = [name for name in names if bundle["numeric"].get(name) is None]
    vec = transform_row(bundle["numeric"], model)
    if vec is None or missing:
        return {
            **base,
            "status": "INSUFFICIENT_SAMPLE",
            "knn_status": "INSUFFICIENT_SAMPLE",
            "reason": f"query missing a KNN feature: {missing}",
            "match": None,
            "sizing": None,
            "conditional_ev": None,
        }
    complete = snapshots.dropna(subset=names)
    mat = complete[names].to_numpy(dtype=float)
    mu = np.array([model["mu"][n] for n in names])
    sd = np.array([model["sd"][n] for n in names])
    sd = np.where(sd == 0.0, 1.0, sd)
    scores = (mat - mu) / sd @ np.asarray(model["components"]).T
    match = match_query(
        vec,
        scores,
        _meta(complete),
        k=k,
        cfg=CFG,
        exclude_trade_id=raw.trade_id,
        exclude_snapshot_id=raw.snapshot_id,
    )
    sizing = recommend_band(match, calibration, cfg=CFG)
    sizing["role"] = "ENTRY_SIZING_REFERENCE"
    sizing["decision"] = None
    ci = match.get("ci") or {}
    conditional = {
        "label": "CONDITIONAL EV FROM CURRENT STATE",
        "conditional_ev_cents": match.get("weighted_mean_EV"),
        "ev_definition": EV_DEFINITION,
        "ev_formula": EV_FORMULA,
        "ci_level": ci.get("ci_level"),
        "ci_lower_cents": ci.get("ci_lower_cents"),
        "ci_upper_cents": ci.get("ci_upper_cents"),
        "method": ci.get("label") or ci.get("method"),
        "secondary_8040_after_t": match.get("weighted_8040_after_t"),
        "secondary_7867_after_t": match.get("weighted_8040_after_t"),
        "secondary_ev_definition": EV_DEFINITION,
        "secondary_ev_formula": EV_FORMULA,
    }
    state_change = None
    if include_entry_change and raw.entry_price_cents is not None:
        entry_result = query_match(
            entry_probe(raw),
            snapshots=snapshots,
            model=model,
            calibration=calibration,
            k=k,
            include_entry_change=False,
        )
        ev_entry = ((entry_result.get("conditional_ev") or {}).get("conditional_ev_cents"))
        ev_now = match.get("weighted_mean_EV")
        state_change = {
            "label": "STATE CHANGE FROM ENTRY",
            "ev_at_entry": ev_entry,
            "ev_now": ev_now,
            "ev_change": None if ev_entry is None or ev_now is None else float(ev_now) - float(ev_entry),
            "note": "Research comparison only. Not an exit instruction.",
        }
    return {
        **base,
        "status": match.get("status") or "OBSERVED",
        "knn_status": match.get("status"),
        "match": match,
        "sizing": sizing,
        "conditional_ev": conditional,
        "support": {
            "label": "HISTORICAL SUPPORT",
            "k": match.get("k"),
            "effective_neighbors": match.get("effective_neighbors"),
            "effective_sample_size": match.get("effective_sample_size"),
            "median_distance": match.get("median_distance"),
            "mean_distance": match.get("mean_distance"),
            "nearest_distance": match.get("nearest_distance"),
            "support": match.get("support"),
        },
        "distribution": {
            "mean": match.get("weighted_mean_PNL"),
            "median": match.get("weighted_median_PNL"),
            "std": match.get("PNL_std"),
            "p10": match.get("PNL_p10"),
            "p25": match.get("PNL_p25"),
            "p50": match.get("PNL_p50"),
            "p75": match.get("PNL_p75"),
            "p90": match.get("PNL_p90"),
            "min": match.get("PNL_min"),
            "max": match.get("PNL_max"),
        },
        "state_change": state_change,
        "ticker": raw.ticker,
        "internal_game_id": raw.internal_game_id,
    }


def form_fields(raw: RawState) -> dict[str, Any]:
    return {
        "side": raw.side,
        "query_mode": public_mode(raw.query_mode),
        "entry_price_cents": raw.entry_price_cents,
        "current_price_cents": raw.current_price_cents,
        "home_score_entry": raw.home_score_entry,
        "away_score_entry": raw.away_score_entry,
        "home_score_current": raw.home_score_current,
        "away_score_current": raw.away_score_current,
        "entry_quarter": raw.entry_quarter,
        "current_quarter": raw.current_quarter,
        "entry_seconds_remaining": raw.entry_seconds_remaining,
        "current_seconds_remaining": raw.current_seconds_remaining,
        "time_since_entry_sec": raw.time_since_entry_sec,
        "trade_id": raw.trade_id,
        "ticker": raw.ticker,
        "internal_game_id": raw.internal_game_id,
    }
