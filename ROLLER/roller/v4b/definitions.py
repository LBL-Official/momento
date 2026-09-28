"""Load V4B definitions and registry. No measurement engines."""

from __future__ import annotations

from typing import Any

from roller.config import RollerConfig

REQUIRED_FAMILY_FIELDS = (
    "name",
    "family",
    "version",
    "definition",
    "formula",
    "required_inputs",
    "information_boundary",
    "contains_future_information",
    "implementation_status",
)

OBSERVED_FAMILIES = (
    "market_delta_1m",
    "fundamental_delta",
    "response_delta",
    "market_fundamental_basis",
    "basis_delta",
    "score_delta",
    "discrete_gamma",
    "theta_observed",
    "pure_theta",
    "candle_range",
    "absolute_return",
    "realized_market_volatility",
    "directional_efficiency",
)


def load_v4b_definitions(cfg: RollerConfig) -> dict[str, Any]:
    body = cfg.greek_v4b_definitions or {}
    if not body.get("families"):
        raise FileNotFoundError("config/greek_v4b_definitions.json missing or empty")
    return body


def load_v4b_registry(cfg: RollerConfig) -> dict[str, Any]:
    body = cfg.greek_v4b_registry or {}
    if not body.get("families"):
        raise FileNotFoundError("meta/greek_v4b_registry.json missing or empty")
    return body


def get_v4b_family(cfg: RollerConfig, name: str) -> dict[str, Any]:
    for row in load_v4b_registry(cfg).get("families", []):
        if row.get("name") == name:
            return row
    raise KeyError(name)


def expected_interval_seconds(cfg: RollerConfig) -> int:
    return int(load_v4b_definitions(cfg).get("expected_interval_seconds") or 60)


def realized_vol_window_closes(cfg: RollerConfig) -> int:
    block = load_v4b_definitions(cfg).get("realized_market_volatility") or {}
    return int(block.get("window_closes") or 10)


def v4b_support_floors(cfg: RollerConfig) -> dict[str, int]:
    block = (load_v4b_definitions(cfg).get("support") or {})
    return {
        "minimum_observations": int(block.get("minimum_observations") or 3),
        "minimum_unique_games": int(block.get("minimum_unique_games") or 2),
        "minimum_unique_dates": int(block.get("minimum_unique_dates") or 1),
        "minimum_unique_seasons": int(block.get("minimum_unique_seasons") or 1),
    }
