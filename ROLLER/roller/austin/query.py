"""Query-state matching against fitted Austin artifacts."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from roller.austin.config import DEFAULT
from roller.austin.errors import AustinError
from roller.austin.features import assert_same_schema, build_feature_vector
from roller.austin.knn import match_query
from roller.austin.outcomes import CHOOSIN_8040_AFTER_T, HOLD_EV_DEFINITION
from roller.austin.pca import transform_row
from roller.austin.raw_state import RawState, entry_probe, raw_from_query
from roller.austin.registry import load_registry
from roller.austin.sizing import recommend_band


def _meta_from_frame(complete: pd.DataFrame) -> list[dict[str, Any]]:
    meta = []
    for rec in complete.itertuples(index=False):
        meta.append(
            {
                "snapshot_id": rec.snapshot_id,
                "trade_id": rec.trade_id,
                "game_date": rec.game_date,
                "quarter": rec.quarter,
                "ticker": rec.ticker,
                "kind": rec.kind,
                "entry_price_cents": rec.entry_price_cents,
                "current_price_cents": rec.current_price_cents,
                "score_differential": rec.score_differential,
                "score": rec.score,
                "time_since_entry": rec.time_since_entry,
                "price_travel": rec.price_travel,
                "score_travel": getattr(rec, "score_travel", None),
                "score_differential_travel": getattr(rec, "score_differential_travel", None),
                "pnl_hold_after_t": getattr(rec, "pnl_hold_after_t", None),
                "pnl_8040_after_t": getattr(rec, "pnl_8040_after_t", None),
                "pnl_8040_after_t_status": getattr(rec, "pnl_8040_after_t_status", None),
                "t40_already": bool(getattr(rec, "t40_already", False)),
                "final_pnl_taker_8040_cents": rec.final_pnl_taker_8040_cents,
                "final_pnl_hold_cents": rec.final_pnl_hold_cents,
                "csv_t40": bool(rec.csv_t40),
                "hit_40_after": bool(rec.hit_40_after),
                "settlement": rec.settlement,
                "won": bool(rec.won),
            }
        )
    return meta


def _proximity(query_numeric: dict[str, Any], neighbors: list[dict[str, Any]], names: list[str]) -> list[dict[str, Any]]:
    rows = []
    for name in names:
        qv = query_numeric.get(name)
        vals = []
        for row in neighbors:
            val = row.get(name)
            if val is None:
                continue
            try:
                vals.append(float(val))
            except (TypeError, ValueError):
                continue
        med = None if not vals else float(np.median(vals))
        contrib = None
        if qv is not None and med is not None:
            contrib = abs(float(qv) - med)
        rows.append(
            {
                "feature": name,
                "query": qv,
                "neighbor_median": med,
                "abs_delta": contrib,
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
    registry = load_registry()
    bundle = build_feature_vector(raw)
    probe = build_feature_vector(raw)
    assert_same_schema(bundle, probe)
    registry_names = [spec.name for spec in registry["features"]]
    if set(bundle["feature_names"]) != set(registry_names):
        raise AustinError("FEATURE_SCHEMA_MISMATCH", "query feature names drifted from registry")
    base = {
        "data_mode": DEFAULT.data_mode,
        "live_feed": DEFAULT.live_feed,
        "live_execution": False,
        "submits": False,
        "query_is_training": False,
        "query_mode": raw.query_mode,
        "query_source": raw.query_source,
        "entry_source": raw.entry_source,
        "path_mode": bundle.get("path_mode"),
        "features": bundle,
        "derived": {
            "price_travel": bundle["numeric"].get("price_travel"),
            "score_travel": bundle["numeric"].get("score_travel"),
            "score_differential_travel": bundle["numeric"].get("score_differential_travel"),
            "time_since_entry": bundle["numeric"].get("time_since_entry"),
        },
        "availability": {name: cell.get("status") for name, cell in (bundle.get("features") or {}).items()},
        "feature_coverage": bundle.get("feature_coverage"),
        "missing_features": bundle.get("missing_features"),
        "model_version": DEFAULT.model_version,
        "dataset_version": DEFAULT.dataset_version,
        "feature_schema_version": DEFAULT.feature_schema_version,
        "pca_version": DEFAULT.pca_version,
        "knn_config": DEFAULT.knn_config,
        "fee_model_status": DEFAULT.fee_status,
        "fill_model_status": DEFAULT.fill_status,
        "ev_definition": HOLD_EV_DEFINITION,
        "ev_formula": "20S − 80(1−S)",
        "secondary_ev_definition": CHOOSIN_8040_AFTER_T,
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
            "note": "PRE_80 reconstructed state only. Fitted 604 KNN requires FIRST80 entry-relative features.",
        }
    names = list(model["names"])
    missing_knn = [name for name in names if bundle["numeric"].get(name) is None]
    vec = transform_row(bundle["numeric"], model)
    if vec is None or missing_knn:
        return {
            **base,
            "status": "INSUFFICIENT_SAMPLE",
            "knn_status": "INSUFFICIENT_SAMPLE",
            "reason": f"query missing a default KNN feature: {missing_knn}",
            "match": None,
            "sizing": None,
            "conditional_ev": None,
        }
    train = snapshots
    complete = train.dropna(subset=names)
    mat = complete[names].to_numpy(dtype=float)
    mu = np.array([model["mu"][n] for n in names])
    sd = np.array([model["sd"][n] for n in names])
    sd = np.where(sd == 0.0, 1.0, sd)
    z = (mat - mu) / sd
    scores = z @ np.asarray(model["components"]).T
    meta = _meta_from_frame(complete)
    match = match_query(
        vec,
        scores,
        meta,
        k=k,
        exclude_trade_id=raw.trade_id,
        exclude_snapshot_id=raw.snapshot_id,
    )
    if raw.trade_id and any(str(n.get("trade_id")) == str(raw.trade_id) for n in match.get("neighbors") or []):
        raise AustinError("LEAKAGE", "query trade_id appeared in neighbors")
    if raw.snapshot_id and any(str(n.get("snapshot_id")) == str(raw.snapshot_id) for n in match.get("neighbors") or []):
        raise AustinError("LEAKAGE", "query snapshot_id appeared in neighbors")
    sizing = recommend_band(match, calibration)
    sizing["role"] = "ENTRY_SIZING_REFERENCE"
    proximity = _proximity(bundle["numeric"], match.get("neighbors") or [], list(DEFAULT.default_knn)[:8])
    ci = match.get("ci") or {}
    conditional = {
        "label": "CONDITIONAL EV FROM CURRENT STATE",
        "conditional_ev_cents": match.get("weighted_mean_EV"),
        "ev_definition": HOLD_EV_DEFINITION,
        "ev_formula": "20S − 80(1−S)",
        "ci_level": ci.get("ci_level"),
        "ci_lower_cents": ci.get("ci_lower_cents"),
        "ci_upper_cents": ci.get("ci_upper_cents"),
        "method": ci.get("label") or ci.get("method"),
        "secondary_8040_after_t": match.get("weighted_8040_after_t"),
        "secondary_ev_definition": CHOOSIN_8040_AFTER_T,
        "secondary_ev_formula": "20S − 40(1−T40_after)",
    }
    support = {
        "label": "HISTORICAL SUPPORT",
        "k": match.get("k"),
        "effective_neighbors": match.get("effective_neighbors"),
        "effective_sample_size": match.get("effective_sample_size"),
        "median_distance": match.get("median_distance"),
        "mean_distance": match.get("mean_distance"),
        "nearest_distance": match.get("nearest_distance"),
        "feature_coverage": bundle.get("feature_coverage"),
        "support": match.get("support"),
    }
    distribution = {
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
    }
    state_change = None
    if include_entry_change and raw.entry_price_cents is not None:
        entry_raw = entry_probe(raw)
        entry_result = query_match(
            entry_raw,
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
        "pca_vector": [float(x) for x in vec],
        "match": match,
        "sizing": sizing,
        "conditional_ev": conditional,
        "support": support,
        "distribution": distribution,
        "state_change": state_change,
        "proximity": proximity,
        "internal_game_id": raw.internal_game_id,
        "ticker": raw.ticker,
    }


def query_from_body(body: dict[str, Any]) -> RawState:
    from roller.austin.raw_state import infer_query_mode

    if body.get("side") in (None, ""):
        raise AustinError("QUERY_REJECTED", "missing side")
    mode = infer_query_mode(body)
    if mode == "PRE_80":
        return raw_from_query(body)
    if body.get("entry_price_cents") in (None, ""):
        raise AustinError("QUERY_REJECTED", "missing entry_price_cents")
    if body.get("current_price_cents") in (None, ""):
        raise AustinError("QUERY_REJECTED", "missing current_price_cents")
    return raw_from_query(body)


def form_fields(raw: RawState) -> dict[str, Any]:
    return {
        "side": raw.side,
        "query_mode": raw.query_mode,
        "entry_source": raw.entry_source,
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
        "snapshot_id": raw.snapshot_id,
    }
