"""PIT-safe conditional baselines. Both clocks required."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from roller.config import RollerConfig
from roller.measurement.conditioning import condition_observation
from roller.measurement.distributions import summarize_values
from roller.measurement.eligibility import baseline_eligible
from roller.measurement.integers import parse_e4
from roller.measurement.support import support_object
from roller.timeutil import parse_utc, to_iso

BASELINE_CONSTRUCTION_VERSION = "prior_eligible_v1"


def support_floors(cfg: RollerConfig) -> tuple[int, int]:
    block = (cfg.conditioning or {}).get("support") or {}
    return int(block.get("min_unique_games") or 2), int(block.get("min_observations") or 3)


def compute_baseline(
    cfg: RollerConfig,
    *,
    observation: dict[str, Any],
    measurement: str,
    horizon: str,
    corpus: list[dict[str, Any]],
    cutoff=None,
) -> dict[str, Any]:
    cond = condition_observation(cfg, observation)
    obs_time = observation.get("observation_time")
    cut = cutoff or obs_time
    min_games, min_obs = support_floors(cfg)
    eligible = []
    for row in corpus:
        if row.get("measurement_name") != measurement:
            continue
        if row.get("horizon") not in (None, "", horizon) and measurement.startswith("market_response"):
            continue
        if measurement.startswith("market_response") and row.get("horizon") != horizon:
            continue
        if not baseline_eligible(row, observation_time_t=obs_time, cutoff_t=cut):
            continue
        if row.get("condition_id") and row.get("condition_id") != cond["condition_id"]:
            continue
        if row.get("status") not in (None, "", "valid"):
            continue
        if parse_e4(row.get("value")) is None:
            continue
        eligible.append(row)

    support = support_object(eligible, min_unique_games=min_games, min_observations=min_obs)
    times = [parse_utc(r.get("observation_time")) for r in eligible]
    times = [t for t in times if t is not None]
    values = [parse_e4(r["value"]) for r in eligible]
    values_i = [v for v in values if v is not None]
    dist = summarize_values(
        values_i,
        measurement=measurement,
        horizon=horizon,
        condition_id=cond["condition_id"],
    )
    out = {
        "observation_id": observation.get("observation_id"),
        "observation_time": obs_time,
        "measurement_name": measurement,
        "horizon": horizon,
        "condition": cond,
        "contains_future_information": True,
        "information_boundary": "forward",
        "baseline_construction_version": BASELINE_CONSTRUCTION_VERSION,
        "baseline_start": to_iso(min(times)) if times else None,
        "baseline_end": to_iso(max(times)) if times else None,
        "support": support,
        "distribution": dist,
        "expected": None,
        "status": "INSUFFICIENT_SUPPORT",
    }
    if not support["sufficient"]:
        return out
    out["expected"] = dist["mean"]
    out["status"] = "valid"
    return out
