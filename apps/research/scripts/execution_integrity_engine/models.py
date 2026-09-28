"""Level 3 execution models. Never claim an actual fill."""

from __future__ import annotations

from .enums import (
    BAND_OBSERVATION,
    E0,
    E1,
    E2,
    E3,
    E4,
    E_THEO,
    EXACT_OBSERVATION,
    GAP_THROUGH,
    L3,
    NONE,
    NOT_AVAILABLE,
)


def e0_observation_only() -> dict:
    return {
        "execution_model_id": E0,
        "execution_model_version": "1.0",
        "fill_claim": NONE,
        "hedge_filled": False,
        "hedge_price": None,
        "fill_fraction": 0.0,
        "evidence_level": L3,
        "note": "Opportunity recorded. No fill assumed.",
    }


def e1_conservative(l2: dict, fallback_pnl: float, entry: float = 80.0) -> dict:
    """Fill only if occupancy is observed in-band. Price = observed close.

    GAP_THROUGH does not receive a threshold fill.
    """
    occ_ok = l2["opportunity_class"] in (EXACT_OBSERVATION, BAND_OBSERVATION)
    px = l2.get("observed_price")
    if occ_ok and px is not None:
        locked = 100.0 - entry - float(px)
        return {
            "execution_model_id": E1,
            "execution_model_version": "1.0",
            "fill_claim": "MODELED_NOT_ACTUAL",
            "hedge_filled": True,
            "hedge_price": float(px),
            "fill_fraction": 1.0,
            "pnl": locked,
            "fallback_triggered": False,
            "evidence_level": L3,
            "note": "Conservative observed-price proxy. Not a confirmed fill.",
        }
    return {
        "execution_model_id": E1,
        "execution_model_version": "1.0",
        "fill_claim": NONE,
        "hedge_filled": False,
        "hedge_price": None,
        "fill_fraction": 0.0,
        "pnl": fallback_pnl,
        "fallback_triggered": True,
        "fallback_reason": l2["opportunity_class"],
        "evidence_level": L3,
        "note": "Miss / gap / no occupancy → explicit 80→40 fallback.",
    }


def e2_scenario(l2: dict, fallback_pnl: float, q: float, partial: float, entry: float = 80.0) -> dict:
    base = e1_conservative(l2, fallback_pnl, entry)
    if not base["hedge_filled"]:
        return {
            **base,
            "execution_model_id": E2,
            "p_fill": q,
            "partial_fill_fraction": partial,
            "pnl": fallback_pnl,
            "note": "E2: no in-band occupancy. q unused. Scenario, not observed.",
        }
    locked = base["pnl"]
    filled = q * partial
    pnl = filled * locked + (1.0 - filled) * fallback_pnl
    return {
        "execution_model_id": E2,
        "execution_model_version": "1.0",
        "fill_claim": "SCENARIO_NOT_OBSERVED",
        "hedge_filled": filled > 0,
        "hedge_price": base["hedge_price"],
        "fill_fraction": filled,
        "p_fill": q,
        "partial_fill_fraction": partial,
        "pnl": pnl,
        "fallback_triggered": filled < 1,
        "evidence_level": L3,
        "execution_assumption_set": f"q={q},partial={partial}",
        "note": "Parameterized scenario. Not an observed fill probability.",
    }


def e_theoretical_threshold(l2: dict, hold_pnl: float, h: float, entry: float = 80.0) -> dict:
    """Illegal-promotion benchmark: any close≥H fills at H."""
    if l2.get("threshold_crossing") or l2["opportunity_class"] == GAP_THROUGH:
        if l2.get("observed_price") is not None or l2.get("threshold_crossing"):
            return {
                "execution_model_id": E_THEO,
                "execution_model_version": "1.0",
                "fill_claim": "ILLEGAL_PROMOTION_BENCHMARK",
                "hedge_filled": True,
                "hedge_price": float(h),
                "fill_fraction": 1.0,
                "pnl": 100.0 - entry - float(h),
                "evidence_level": L3,
                "note": "NON-EXECUTION-AUDITED. Gap booked at H. Not E1.",
            }
    return {
        "execution_model_id": E_THEO,
        "execution_model_version": "1.0",
        "fill_claim": NONE,
        "hedge_filled": False,
        "hedge_price": None,
        "fill_fraction": 0.0,
        "pnl": hold_pnl,
        "evidence_level": L3,
        "note": "No close≥H. Hold. Still not a fill model for production.",
    }


def e3_empirical() -> dict:
    return {
        "execution_model_id": E3,
        "execution_model_version": "1.0",
        "EMPIRICAL_MODEL_STATUS": NOT_AVAILABLE,
        "fill_claim": NONE,
        "evidence_level": L3,
        "note": "No live Momento fill dataset. Coefficients not fabricated.",
    }


def e4_l2_queue() -> dict:
    return {
        "execution_model_id": E4,
        "execution_model_version": "1.0",
        "status": "NOT_AVAILABLE_WITH_CURRENT_HISTORICAL_DATA",
        "fill_claim": NONE,
        "evidence_level": L3,
        "note": "No historical L2. Queue not simulated as fact.",
    }
