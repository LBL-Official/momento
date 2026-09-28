"""Read-only Fort Worth contract. Austin does not execute it."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from roller.austin.config import DEFAULT
from roller.austin.paths import contract_path
from roller.austin.store import write_json


POLICY = {
    "product": "Fort Worth",
    "role": "execution_policy_research",
    "live_execution": False,
    "live_armed": False,
    "submits": False,
    "research_registered": True,
    "note": "RESEARCH_REGISTERED != LIVE_ARMED. Fort Worth does not submit.",
    "entry": {
        "rule": "FIRST80 unfiltered. Austin does not skip.",
        "desk": "78-82 / bail-40 ledger analog",
        "size": "3-5% of $20,000 from the 80c favorite only",
        "reserve_120": False,
    },
    "hedge": {
        "when": "favorite path prints 41-42",
        "action": "rest opponent YES at 40 as maker",
        "capital": "idle cash, not reserved against the 80c sleeve",
        "wick": "never arms",
        "same_ticker_no_taker": False,
        "fallback": "hard reduce-only IOC on the favorite if 40 never fills and favorite still prints T40",
        "fill_status": DEFAULT.fill_status,
        "candle_path_not_fill": True,
    },
    "forbidden": [
        "submit from Austin or Fort Worth pages",
        "second trading engine",
        "edit apps/trading-engine",
        "treat 40c close as a fill",
        "mix N=1230 hedge V1 cents into the 604 book",
    ],
}


def contract_from_query(result: dict[str, Any]) -> dict[str, Any]:
    sizing = result.get("sizing") or {}
    match = result.get("match") or {}
    return {
        "model_version": result.get("model_version") or DEFAULT.model_version,
        "dataset_version": result.get("dataset_version") or DEFAULT.dataset_version,
        "feature_schema_version": result.get("feature_schema_version"),
        "pca_version": result.get("pca_version"),
        "knn_config": result.get("knn_config"),
        "fee_model_version": DEFAULT.fee_model_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_id": None,
        "trade_state": "QUERY",
        "entry_price": (result.get("features") or {}).get("numeric", {}).get("entry_price_cents"),
        "pca_vector": result.get("pca_vector"),
        "knn_k": match.get("k"),
        "neighbors": match.get("neighbors") or [],
        "weighted_ev": match.get("weighted_mean_EV"),
        "weighted_pnl": match.get("weighted_mean_PNL"),
        "ev_definition": result.get("ev_definition"),
        "conditional_ev": result.get("conditional_ev"),
        "ci": (match.get("ci") or (result.get("conditional_ev") or {})),
        "state_change": result.get("state_change"),
        "pnl_distribution": {
            "std": match.get("PNL_std"),
            "p25": match.get("PNL_p25"),
            "p50": match.get("PNL_p50"),
            "p75": match.get("PNL_p75"),
            "min": match.get("PNL_min"),
            "max": match.get("PNL_max"),
        },
        "evidence": {
            "effective_neighbors": match.get("effective_neighbors"),
            "median_distance": match.get("median_distance"),
            "support": match.get("support"),
            "feature_coverage": result.get("feature_coverage"),
        },
        "recommended_allocation_band": sizing.get("recommended_allocation_band"),
        "allocation_dollars": sizing.get("dollar_allocation"),
        "contract_count": sizing.get("contracts"),
        "hedge_hypothesis": {
            "trigger": [41, 42],
            "hedge_price": 40,
            "fill_model_status": DEFAULT.fill_status,
        },
        "fee_model_status": DEFAULT.fee_status,
        "fill_model_status": DEFAULT.fill_status,
        "live_execution": False,
        "submits": False,
    }


def persist_contract(result: dict[str, Any]) -> dict[str, Any]:
    payload = contract_from_query(result)
    write_json(contract_path(), payload)
    return payload


def policy_payload() -> dict[str, Any]:
    return dict(POLICY)
