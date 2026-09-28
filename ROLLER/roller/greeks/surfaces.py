"""Deterministic grouped response surfaces. Not predictive."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from roller.config import RollerConfig
from roller.measurement.distributions import summarize_values
from roller.measurement.eligibility import baseline_eligible
from roller.measurement.integers import parse_e4
from roller.measurement.support import support_object


def response_surface(
    cfg: RollerConfig,
    rows: list[dict[str, Any]],
    *,
    measurement: str,
    horizon: str,
    observation_time_t,
    cutoff_t=None,
    surface_name: str = "conditional_expected_response",
    surface_version: str = "v1",
) -> list[dict[str, Any]]:
    min_games = int(((cfg.conditioning or {}).get("support") or {}).get("min_unique_games") or 2)
    min_obs = int(((cfg.conditioning or {}).get("support") or {}).get("min_observations") or 3)
    by_cond: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("measurement_name") != measurement:
            continue
        if row.get("horizon") != horizon:
            continue
        if not baseline_eligible(row, observation_time_t=observation_time_t, cutoff_t=cutoff_t):
            continue
        val = parse_e4(row.get("value"))
        if val is None:
            continue
        by_cond[str(row.get("condition_id") or "")].append(row)
    out = []
    for cond, group in sorted(by_cond.items()):
        values = [parse_e4(r["value"]) for r in group]
        values_i = [v for v in values if v is not None]
        support = support_object(group, min_unique_games=min_games, min_observations=min_obs)
        dist = summarize_values(values_i, measurement=measurement, horizon=horizon, condition_id=cond)
        out.append(
            {
                "surface_name": surface_name,
                "surface_version": surface_version,
                "measurement_name": measurement,
                "conditioning_schema_version": (cfg.conditioning or {}).get("conditioning_schema_version"),
                "condition_id": cond,
                "value": dist["mean"] if support["sufficient"] else None,
                "status": "valid" if support["sufficient"] else "INSUFFICIENT_SUPPORT",
                "support": support,
                "note": "conditional expectation is not a prediction",
            }
        )
    return out
