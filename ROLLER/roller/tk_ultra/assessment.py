"""Compose TKUltraRVAssessment. Never reads Ballhog into math."""

from __future__ import annotations

from typing import Any

from roller.tk_ultra.hedge_budget import assess_budget
from roller.tk_ultra.models import (
    ASSESSMENT_SCHEMA,
    AUSTIN_N,
    AUSTIN_UNIVERSE,
    CHOOSIN_N,
    CHOOSIN_UNIVERSE,
    LIVE_EXECUTION,
    MODEL_BINARY,
    PRODUCT,
    SYSTEM_ID,
    UNAVAILABLE,
    now_iso,
    optional_fraction,
)
from roller.tk_ultra.relationship import STRUCTURAL_BETA, assess_relationship
from roller.tk_ultra.route import assess_route


def _qty_scenario(body: dict[str, Any], sibling: dict[str, Any] | None) -> dict[str, Any]:
    raw = body.get("requested_quantity")
    source = str(body.get("quantity_source") or "").strip()
    if raw is None or raw == "" or raw == UNAVAILABLE:
        if source == "BALLHOG_CONTEXT" and isinstance(sibling, dict):
            intent = sibling.get("intent") if isinstance(sibling.get("intent"), dict) else {}
            q_star = intent.get("q_star")
            if q_star is None:
                return {"quantity_specific_assessment": UNAVAILABLE, "quantity_source": "BALLHOG_CONTEXT"}
            return {
                "quantity_specific_assessment": {
                    "requested_quantity": q_star,
                    "quantity_source": "BALLHOG_CONTEXT",
                    "note": "Counterfactual display of sibling q*. TK Ultra did not choose q*.",
                },
                "quantity_source": "BALLHOG_CONTEXT",
            }
        return {"quantity_specific_assessment": UNAVAILABLE, "quantity_source": UNAVAILABLE}
    return {
        "quantity_specific_assessment": {
            "requested_quantity": raw,
            "quantity_source": source or "MANUAL_SCENARIO",
            "note": "Scenario quantity. TK Ultra does not choose q*.",
        },
        "quantity_source": source or "MANUAL_SCENARIO",
    }


def assess_binary(
    body: dict[str, Any] | None,
    *,
    austin_ctx: dict[str, Any] | None = None,
    choosin_ctx: dict[str, Any] | None = None,
    identity: dict[str, Any] | None = None,
    feed_mode: str = "MANUAL_INPUT",
) -> dict[str, Any]:
    payload = body if isinstance(body, dict) else {}
    e_a = optional_fraction(payload.get("a_entry_cents") if payload.get("a_entry_cents") is not None else payload.get("a_entry"))
    s_a = optional_fraction(payload.get("a_stop_cents") if payload.get("a_stop_cents") is not None else payload.get("a_stop"))
    a_bid = optional_fraction(payload.get("a_bid_cents") if payload.get("a_bid_cents") is not None else payload.get("a_bid"))
    b_ask = optional_fraction(payload.get("b_ask_cents") if payload.get("b_ask_cents") is not None else payload.get("b_ask"))
    a_anchor = optional_fraction(
        payload.get("a_anchor_cents") if payload.get("a_anchor_cents") is not None else payload.get("a_anchor")
    )
    b_anchor = optional_fraction(
        payload.get("b_anchor_cents") if payload.get("b_anchor_cents") is not None else payload.get("b_anchor")
    )
    a_ref = optional_fraction(payload.get("a_ref_cents") if payload.get("a_ref_cents") is not None else payload.get("a_ref"))
    b_obs = optional_fraction(
        payload.get("b_observed_cents") if payload.get("b_observed_cents") is not None else payload.get("b_observed")
    )
    q_a = optional_fraction(payload.get("q_a") if payload.get("q_a") is not None else payload.get("current_a_qty"))
    q_b = optional_fraction(payload.get("q_b") if payload.get("q_b") is not None else payload.get("current_b_qty"))
    b_existing = optional_fraction(
        payload.get("b_avg_existing_cents")
        if payload.get("b_avg_existing_cents") is not None
        else payload.get("current_avg_b_price")
    )
    a_ref_basis = str(payload.get("a_ref_basis") or "MID")
    b_obs_basis = str(payload.get("b_observed_basis") or "MID")
    transform = payload.get("price_basis_transform")
    beta = optional_fraction(payload.get("beta")) or STRUCTURAL_BETA

    rel = assess_relationship(
        a_anchor=a_anchor,
        b_anchor=b_anchor,
        a_ref=a_ref,
        b_observed=b_obs,
        a_ref_basis=a_ref_basis,
        b_observed_basis=b_obs_basis,
        a_bid=a_bid,
        b_ask=b_ask,
        beta=beta,
        price_basis_transform=str(transform) if transform else None,
    )
    route = assess_route(a_bid=a_bid, b_ask=b_ask)
    budget = assess_budget(
        e_a=e_a,
        s_a=s_a,
        q_a=q_a,
        q_b=q_b,
        b_existing=b_existing,
        b_ask=b_ask,
    )
    reasons: list[str] = []
    for block in (rel, route, budget):
        reasons.extend(list(block.get("reason_codes") or []))
    ident = identity if isinstance(identity, dict) else {}
    austin = austin_ctx if isinstance(austin_ctx, dict) else {}
    choosin = choosin_ctx if isinstance(choosin_ctx, dict) else {}
    qty = _qty_scenario(payload, None)
    return {
        "schema": ASSESSMENT_SCHEMA,
        "system_id": SYSTEM_ID,
        "product": PRODUCT,
        "live_execution": LIVE_EXECUTION,
        "execution_enabled": False,
        "binary_formula_is_truth": False,
        "model_mode": MODEL_BINARY,
        "status": rel.get("status") or "RESEARCH_ONLY",
        "generated_at": now_iso(),
        "as_of": ident.get("as_of") or payload.get("as_of") or UNAVAILABLE,
        "feed_mode": feed_mode,
        "live_feed": "UNAVAILABLE",
        "identity": {
            "trade_id": ident.get("trade_id") or payload.get("trade_id") or UNAVAILABLE,
            "internal_game_id": ident.get("internal_game_id") or payload.get("internal_game_id") or UNAVAILABLE,
            "event_id": ident.get("event_id") or payload.get("event_id") or UNAVAILABLE,
            "a_contract": ident.get("a_contract") or payload.get("a_contract") or UNAVAILABLE,
            "b_contract": ident.get("b_contract") or payload.get("b_contract") or UNAVAILABLE,
        },
        "base_contract": ident.get("a_contract") or payload.get("a_contract") or "A",
        "wing_contract": ident.get("b_contract") or payload.get("b_contract") or "B",
        "relationship": rel,
        "route": route,
        "hedge_budget": budget,
        "expected_wing": rel.get("expected_wing"),
        "tk_residual": rel.get("tk_residual"),
        "rv_state": rel.get("rv_state"),
        "relationship_route_collinear": rel.get("relationship_route_collinear"),
        "direct_exit_price": route.get("direct_exit_price"),
        "synthetic_exit_price": route.get("synthetic_exit_price"),
        "gross_route_edge": route.get("gross_route_edge"),
        "route_preference": route.get("route_preference"),
        "a_entry": budget.get("a_entry"),
        "a_stop_benchmark": budget.get("a_stop_benchmark"),
        "stop_pnl_benchmark": budget.get("stop_pnl_benchmark"),
        "stop_equivalent_b_avg": budget.get("stop_equivalent_b_avg"),
        "current_a_qty": budget.get("current_a_qty"),
        "current_b_qty": budget.get("current_b_qty"),
        "current_hedge_fraction": budget.get("hedge_fraction"),
        "current_avg_b_price": budget.get("current_avg_b_price"),
        "max_remaining_avg_price": budget.get("max_remaining_avg_price"),
        "hedge_runway_vs_ask": budget.get("hedge_runway_vs_ask"),
        "cost_cushion_vs_existing_avg": budget.get("cost_cushion_vs_existing_avg"),
        "completed_now_b_avg": budget.get("completed_now_b_avg"),
        "locked_pnl_if_completed_now": budget.get("locked_pnl_if_completed_now"),
        "gross_improvement_vs_stop_if_completed_now": budget.get("gross_improvement_vs_stop_if_completed_now"),
        "fees": UNAVAILABLE,
        "slippage": UNAVAILABLE,
        "fill": UNAVAILABLE,
        "depth": UNAVAILABLE,
        "austin": {
            "universe": AUSTIN_UNIVERSE,
            "n": AUSTIN_N,
            "availability": austin.get("availability") or UNAVAILABLE,
            "conditional_ev_cents": austin.get("conditional_ev_cents"),
            "ci_lower_cents": austin.get("ci_lower_cents"),
            "support": austin.get("support"),
            "effective_sample_size": austin.get("effective_sample_size"),
            "ev_change": austin.get("ev_change"),
            "weighted_t40_rate": austin.get("weighted_t40_rate"),
            "weighted_survival_rate": austin.get("weighted_survival_rate"),
            "adapter": "roller.tk_ultra.adapters.austin",
        },
        "choosin_texas": {
            "universe": CHOOSIN_UNIVERSE,
            "n": CHOOSIN_N,
            "availability": choosin.get("availability") or UNAVAILABLE,
            "entry_cents": choosin.get("entry_cents"),
            "loss_barrier_cents": choosin.get("loss_barrier_cents"),
            "historical_survival_rate": choosin.get("historical_survival_rate"),
            "pit_kind": choosin.get("pit_kind") or "STATIC",
            "adapter": "roller.tk_ultra.adapters.choosin",
        },
        "sibling_context": UNAVAILABLE,
        "position_management": "NOT_IMPLEMENTED",
        "quantity_specific_assessment": qty["quantity_specific_assessment"],
        "reason_codes": reasons,
        "provenance": {
            "austin_universe": AUSTIN_UNIVERSE,
            "austin_n": AUSTIN_N,
            "choosin_universe": CHOOSIN_UNIVERSE,
            "choosin_n": CHOOSIN_N,
            "model_mode": MODEL_BINARY,
            "beta_source": rel.get("beta_source"),
            "a_ref_basis": rel.get("a_ref_basis"),
            "route_a_bid_basis": route.get("a_bid_basis") or "YES_BID",
            "route_b_ask_basis": route.get("b_ask_basis") or "YES_ASK",
        },
    }


def attach_sibling(assessment: dict[str, Any], sibling: dict[str, Any] | None) -> dict[str, Any]:
    """Display-only. Must not change math fields."""
    out = dict(assessment)
    if not sibling or sibling.get("availability") == UNAVAILABLE:
        out["sibling_context"] = {
            "availability": UNAVAILABLE,
            "note": "SIBLING CONTEXT — NOT MODEL INPUT",
            "position_management": "NOT_IMPLEMENTED",
            "reason_codes": ["BALLHOG_CONTEXT_UNAVAILABLE"],
        }
        codes = list(out.get("reason_codes") or [])
        if "BALLHOG_CONTEXT_UNAVAILABLE" not in codes:
            codes.append("BALLHOG_CONTEXT_UNAVAILABLE")
        out["reason_codes"] = codes
        return out
    intent = sibling.get("intent") if isinstance(sibling.get("intent"), dict) else {}
    compact = dict(sibling)
    compact["q_star"] = intent.get("q_star")
    compact["rho_star"] = intent.get("rho_star")
    compact["risk_intent"] = intent.get("risk_intent")
    compact["decision_status"] = intent.get("decision_status")
    compact["intent_status"] = intent.get("intent_status")
    compact["note"] = sibling.get("note") or "SIBLING CONTEXT — NOT MODEL INPUT"
    out["sibling_context"] = compact
    qty_source = assessment.get("quantity_specific_assessment")
    if qty_source == UNAVAILABLE:
        patched = _qty_scenario({"quantity_source": "BALLHOG_CONTEXT"}, sibling)
        out["quantity_specific_assessment"] = patched["quantity_specific_assessment"]
    return out


MATH_KEYS = (
    "expected_wing",
    "tk_residual",
    "rv_state",
    "synthetic_exit_price",
    "gross_route_edge",
    "route_preference",
    "stop_equivalent_b_avg",
    "max_remaining_avg_price",
    "hedge_runway_vs_ask",
    "relationship_route_collinear",
)
