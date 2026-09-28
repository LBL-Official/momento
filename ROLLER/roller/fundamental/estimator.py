"""Minimal prior-only empirical win probability. No smoothing."""

from __future__ import annotations

from typing import Any

from roller.config import RollerConfig
from roller.fundamental.conditioning import (
    condition_observation,
    schema_spec,
    support_floors,
)
from roller.fundamental.corpus import filter_eligible
from roller.fundamental.orientation import y_home_win
from roller.fundamental.registry import get_fundamental
from roller.fundamental.support import fundamental_support
from roller.io_csv import sha256_json
from roller.timeutil import to_iso

DEFAULT_NAME = "fundamental_win_probability_empirical_v1"


def _row_y(row: dict[str, Any]) -> int | None:
    if row.get("y_home_win") not in (None, ""):
        try:
            return int(row["y_home_win"])
        except (TypeError, ValueError):
            pass
    return y_home_win(row.get("home_win"))


def estimate_fundamental(
    cfg: RollerConfig,
    *,
    observation: dict[str, Any],
    name: str = DEFAULT_NAME,
    conditioning_schema_version: str | None = None,
    corpus: list[dict[str, Any]],
) -> dict[str, Any]:
    spec = get_fundamental(cfg, name)
    schema = conditioning_schema_version or spec.get("conditioning_schema_version")
    schema_spec(cfg, schema)
    cutoff = observation.get("observation_time")
    sport = observation.get("sport")
    cond = condition_observation(cfg, observation, schema_version=schema)
    floors = support_floors(cfg)
    cutoff_iso = cutoff if isinstance(cutoff, str) else to_iso(cutoff) if cutoff is not None else None
    fid_payload = {
        "name": name,
        "version": spec.get("version"),
        "conditioning_schema_version": schema,
        "observation_id": observation.get("observation_id"),
        "information_cutoff": cutoff_iso,
    }
    fundamental_id = f"F_{sha256_json(fid_payload)[:16]}"
    base = {
        "observation_id": observation.get("observation_id"),
        "fundamental_id": fundamental_id,
        "fundamental_name": name,
        "fundamental_version": spec.get("version"),
        "fundamental_schema_version": cfg.fundamental_schema_version,
        "measurement_time": cutoff_iso,
        "observation_cutoff": cutoff_iso,
        "information_cutoff": cutoff_iso,
        "value": None,
        "status": "INSUFFICIENT_SUPPORT",
        "probability_wins": None,
        "probability_n": None,
        "conditioning_schema_version": cond["conditioning_schema_version"],
        "condition_id": cond["condition_id"],
        "raw_dimensions": cond["raw_dimensions"],
        "training_corpus_start": None,
        "training_corpus_end": None,
        "information_regime": "prior_only",
        "n_observations": 0,
        "n_unique_games": 0,
        "n_unique_dates": 0,
        "n_unique_teams": 0,
        "n_unique_seasons": 0,
        "repeated_observation_warning": False,
        "effective_n": None,
        "effective_n_status": "NOT_IMPLEMENTED",
        "eligible_internal_game_ids": [],
        "available_at": cutoff_iso,
        "calculated_at": cutoff_iso,
        "contains_future_information": True,
        "support": None,
    }
    if sport not in {"NBA", "WNBA", "NCAAB"}:
        base["status"] = "NOT_SUPPORTED"
        return base
    if cond["status"] != "valid":
        base["status"] = "MISSING_REQUIRED_INPUT" if cond["missing_dimensions"] else "INVALID_CONDITION"
        return base

    eligible = filter_eligible(
        corpus,
        current_game_id=str(observation.get("internal_game_id") or ""),
        cutoff=cutoff,
        condition_id=cond["condition_id"],
    )
    support = fundamental_support(eligible, floors=floors)
    base["support"] = support
    base["n_observations"] = support["n_observations"]
    base["n_unique_games"] = support["n_unique_games"]
    base["n_unique_dates"] = support["n_unique_dates"]
    base["n_unique_teams"] = support["n_unique_teams"]
    base["n_unique_seasons"] = support["n_unique_seasons"]
    base["repeated_observation_warning"] = support["repeated_observation_warning"]
    base["training_corpus_start"] = support.get("first_observation_time")
    base["training_corpus_end"] = support.get("last_observation_time")
    games = sorted({str(r.get("internal_game_id")) for r in eligible if r.get("internal_game_id")})
    base["eligible_internal_game_ids"] = games
    if not support["sufficient"]:
        base["status"] = "INSUFFICIENT_SUPPORT"
        return base

    wins = 0
    n = 0
    for row in eligible:
        y = _row_y(row)
        if y is None:
            continue
        wins += y
        n += 1
    if n == 0:
        base["status"] = "INSUFFICIENT_SUPPORT"
        return base
    base["probability_wins"] = wins
    base["probability_n"] = n
    base["value"] = {"numerator": wins, "denominator": n}
    base["status"] = "IMPLEMENTED"
    return base
