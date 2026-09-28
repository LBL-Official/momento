"""Pareto frontier on economic_EV_cost_of_hedge vs T40_RISK_PROXY removed."""

from __future__ import annotations

from typing import Any

from roller.ballhog.models import FRONTIER_SCHEMA


def _num(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def is_admissible(cell: dict[str, Any], *, require_positive_robust: bool) -> bool:
    if not require_positive_robust:
        return cell.get("robust_portfolio_EV_after") is not None
    robust = _num(cell.get("robust_portfolio_EV_after"))
    return robust is not None and robust > 0


def pareto_front(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scored: list[tuple[float, float, dict[str, Any]]] = []
    for cell in cells:
        cost = _num(cell.get("economic_EV_cost_of_hedge"))
        removed = _num(cell.get("risk_removed"))
        if cost is None or removed is None:
            continue
        scored.append((cost, removed, cell))
    front: list[dict[str, Any]] = []
    for cost, removed, cell in scored:
        dominated = False
        for other_cost, other_removed, _other in scored:
            if other_cost <= cost and other_removed >= removed and (other_cost < cost or other_removed > removed):
                dominated = True
                break
        row = dict(cell)
        row["dominated"] = dominated
        row["on_frontier"] = not dominated
        row["is_frontier"] = not dominated
        if not dominated:
            front.append(row)
    front.sort(key=lambda row: (_num(row.get("risk_removed")) or 0.0, _num(row.get("economic_EV_cost_of_hedge")) or 0.0))
    return front


def marginal_curve(front: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(front, key=lambda row: int(row.get("q_hedge") or 0))
    out: list[dict[str, Any]] = []
    prev: dict[str, Any] | None = None
    for row in ordered:
        if prev is None:
            out.append(
                {
                    **row,
                    "delta_risk_removed": None,
                    "delta_economic_ev_cost": None,
                    "marginal_ev_cost_per_unit_risk_removed": None,
                    "marginal_cost_per_risk": None,
                }
            )
            prev = row
            continue
        d_cost = (_num(row.get("economic_EV_cost_of_hedge")) or 0.0) - (
            _num(prev.get("economic_EV_cost_of_hedge")) or 0.0
        )
        d_risk = (_num(row.get("risk_removed")) or 0.0) - (_num(prev.get("risk_removed")) or 0.0)
        slope = None if d_risk == 0 else d_cost / d_risk
        out.append(
            {
                **row,
                "delta_risk_removed": d_risk,
                "delta_economic_ev_cost": d_cost,
                "marginal_ev_cost_per_unit_risk_removed": slope,
                "marginal_cost_per_risk": slope,
            }
        )
        prev = row
    return out


def build_frontier(
    cells: list[dict[str, Any]],
    *,
    require_positive_robust: bool,
) -> dict[str, Any]:
    labeled = []
    for cell in cells:
        row = dict(cell)
        row["admissible"] = is_admissible(row, require_positive_robust=require_positive_robust)
        row["is_admissible"] = row["admissible"]
        row["is_robust_positive"] = is_admissible(row, require_positive_robust=True)
        labeled.append(row)
    front = pareto_front(labeled)
    admissible_front = [row for row in front if row.get("admissible")]
    return {
        "schema": FRONTIER_SCHEMA,
        "axes": {
            "x": "economic_EV_cost_of_hedge",
            "y": "risk_removed",
            "y_metric": "T40_RISK_PROXY",
        },
        "points": labeled,
        "frontier": front,
        "admissible_frontier": admissible_front,
        "marginal": marginal_curve(admissible_front or front),
    }
