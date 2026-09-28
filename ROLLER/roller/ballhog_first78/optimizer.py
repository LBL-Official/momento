"""Two-stage optimizer for the 78/67 book. No lambda. No silent ties."""

from __future__ import annotations

from typing import Any

from roller.ballhog.frontier import build_frontier, is_admissible
from roller.ballhog.models import DECISION_SCHEMA
from roller.ballhog.policy import BallhogPolicy
from roller.ballhog.timing import timing_decision
from roller.ballhog_first78.arithmetic import RISK_METRIC
from roller.ballhog_first78.surface import build_surface

REDUCTION_INTENTS = frozenset({"BEGIN_REDUCTION", "REDUCE", "NEUTRALIZE"})


def _zero_cell(cells: list[dict[str, Any]]) -> dict[str, Any] | None:
    for cell in cells:
        if int(cell.get("q_hedge") or 0) == 0:
            return cell
    return None


def _explanation(risk_intent: str, hedge_feasibility: str, decision_status: str) -> str:
    if risk_intent == "UNAVAILABLE" or hedge_feasibility == "SOURCE_UNAVAILABLE":
        return "SOURCE_UNAVAILABLE: Austin conditional alpha is missing. Ballhog does not invent a hedge target."
    if hedge_feasibility == "NOT_REQUESTED":
        return f"{risk_intent} / NOT_REQUESTED: q*=0. The 62–72 grid is not a trigger."
    if hedge_feasibility == "NO_ADMISSIBLE_HEDGE" and decision_status == "RESOLVED":
        return "NO_ADMISSIBLE_HEDGE: reduction is indicated and no non-zero hedge keeps robust portfolio EV positive."
    if hedge_feasibility == "ADMISSIBLE_HEDGE_AVAILABLE":
        return "ADMISSIBLE_HEDGE_AVAILABLE: exactly one modeled non-zero hedge is economically admissible."
    if hedge_feasibility == "POLICY_UNRESOLVED":
        return "POLICY_UNRESOLVED: more than one admissible non-zero hedge remains. q* is null."
    if decision_status == "UNAVAILABLE":
        return "ROBUST_PORTFOLIO_NONPOSITIVE: unhedged robust portfolio economics are not positive."
    return "Ballhog decision from the 78/67 Austin neighborhood and the theoretical 62–72 surface."


def decide(
    *,
    q_dir: int,
    alpha: dict[str, Any],
    policy: BallhogPolicy,
    research_unit_qty: int,
) -> dict[str, Any]:
    a_t = alpha.get("a_t")
    a_l = alpha.get("a_l")
    timing = timing_decision(alpha, policy)
    timing["note"] = "62–72 is a counterfactual hedge-price grid around the 67 stop, not an observed print."
    risk_intent = str(timing.get("timing_state") or "UNAVAILABLE")
    reasons = list(timing.get("reason_codes") or [])
    if a_t is None:
        return {
            "schema": DECISION_SCHEMA,
            "decision_status": "SOURCE_UNAVAILABLE",
            "risk_intent": risk_intent,
            "hedge_feasibility": "SOURCE_UNAVAILABLE",
            "rho_star": None,
            "q_star": None,
            "delta_star": None,
            "target_residual_qty": None,
            "reason_codes": ["SOURCE_UNAVAILABLE"],
            "explanation": _explanation(risk_intent, "SOURCE_UNAVAILABLE", "SOURCE_UNAVAILABLE"),
            "execution_enabled": False,
            "research_unit_qty": research_unit_qty,
            "q_dir": q_dir,
            "risk_metric_name": RISK_METRIC,
            "current_hedge_price": "UNAVAILABLE",
        }
    surface = build_surface(
        q_dir=q_dir,
        a_t=float(a_t),
        a_l=None if a_l is None else float(a_l),
        weighted_t67_rate=alpha.get("weighted_t67_rate"),
        policy=policy,
        research_unit_qty=research_unit_qty,
    )
    frontier = build_frontier(list(surface["cells"]), require_positive_robust=policy.positive_robust_portfolio_ev)
    frontier.setdefault("axes", {})["y_metric"] = RISK_METRIC
    admissible = [
        row
        for row in frontier["admissible_frontier"]
        if is_admissible(row, require_positive_robust=policy.positive_robust_portfolio_ev)
    ]
    nonzero = [row for row in admissible if int(row.get("q_hedge") or 0) > 0]
    zero = _zero_cell(list(surface["cells"]))
    unhedged_robust = None if a_l is None else int(q_dir) * float(a_l)
    status = "RESOLVED"
    feasibility = "NOT_REQUESTED"
    chosen: dict[str, Any] | None = zero
    if risk_intent in {"RETAIN", "WATCH"}:
        feasibility = "NOT_REQUESTED"
        chosen = zero
    elif risk_intent in REDUCTION_INTENTS:
        if len(nonzero) == 1:
            chosen = nonzero[0]
            feasibility = "ADMISSIBLE_HEDGE_AVAILABLE"
        elif len(nonzero) > 1:
            chosen = None
            feasibility = "POLICY_UNRESOLVED"
            status = "POLICY_UNRESOLVED"
            reasons.append("POLICY_UNRESOLVED")
        elif unhedged_robust is not None and unhedged_robust > 0:
            chosen = zero
            feasibility = "NO_ADMISSIBLE_HEDGE"
            reasons.append("NO_ADMISSIBLE_HEDGE")
        else:
            chosen = None
            feasibility = "NO_ADMISSIBLE_HEDGE"
            status = "UNAVAILABLE"
            reasons.extend(["ROBUST_PORTFOLIO_NONPOSITIVE", "NO_ADMISSIBLE_HEDGE"])
    else:
        chosen = None
        feasibility = "SOURCE_UNAVAILABLE"
        status = "SOURCE_UNAVAILABLE"
    residual = None if chosen is None else chosen.get("residual_qty")
    q_star = None if chosen is None else chosen.get("q_hedge")
    rho_star = None if chosen is None else chosen.get("rho")
    return {
        "schema": DECISION_SCHEMA,
        "decision_status": status,
        "risk_intent": risk_intent,
        "hedge_feasibility": feasibility,
        "policy_version": policy.version,
        "research_unit_qty": research_unit_qty,
        "q_dir": q_dir,
        "current_exposure": q_dir,
        "q_hedge": q_star,
        "rho": rho_star,
        "rho_star": rho_star,
        "q_star": q_star,
        "delta_star": residual,
        "target_residual_qty": residual,
        "target_exposure": residual,
        "target_exposure_qty": residual,
        "desired_exposure_removed": q_star,
        "chosen_frontier_point": chosen,
        "chosen_candidate": chosen,
        "admissible_frontier": admissible,
        "nonzero_admissible_frontier": nonzero,
        "frontier": frontier,
        "surface": surface,
        "timing": timing,
        "reason_codes": reasons,
        "explanation": _explanation(risk_intent, feasibility, status),
        "austin_alpha_cents": a_t,
        "austin_alpha_per_unit": a_t,
        "austin_robust_alpha_cents": a_l,
        "austin_robust_alpha_per_unit": a_l,
        "current_alpha": a_t,
        "robust_alpha": a_l,
        "alpha_delta_from_entry": alpha.get("alpha_delta_from_entry"),
        "alpha_ci": {
            "lower": a_l,
            "upper": alpha.get("ci_upper"),
            "level": alpha.get("ci_level"),
            "method": alpha.get("ci_method"),
            "note": "Austin bootstrap. Not a Ballhog CI.",
        },
        "alpha_n": alpha.get("effective_sample_size"),
        "risk_metric_name": RISK_METRIC,
        "risk_before": None if chosen is None else chosen.get("risk_before"),
        "risk_after": None if chosen is None else chosen.get("risk_after"),
        "risk_removed": None if chosen is None else chosen.get("risk_removed"),
        "execution_enabled": False,
        "execution_assumption": "THEORETICAL",
        "current_hedge_price": "UNAVAILABLE",
        "acceptable_hedge_price_region": {"grid": list(policy.price_grid), "role": "COUNTERFACTUAL"},
        "buy_skip": False,
    }
