"""V4C constructibility and no-proxy audit."""

from __future__ import annotations

from typing import Any

from roller.config import RollerConfig
from roller.state.capabilities import REAL, capability
from roller.v4c.capability import (
    ProxyProhibitedError,
    possession_delta_authorized,
    refuse_proxy,
)
from roller.v4c.registry import get_v4c_object, v4c_objects
from roller.v4c.validation import audit_registry


def audit_no_proxy() -> list[str]:
    errors: list[str] = []
    cases = (
        ("OHLC", "microprice"),
        ("OHLC", "order_book"),
        ("candle_volume", "signed_flow_lambda"),
        ("volume", "psi_resilience"),
        ("candle_sequence", "market_delta_1s"),
        ("possession_data", "possession_delta"),
    )
    for source, target in cases:
        try:
            refuse_proxy(source, target)
        except ProxyProhibitedError:
            continue
        errors.append(f"proxy {source} → {target} was not refused")
    return errors


def audit_possession_not_implemented() -> list[str]:
    errors: list[str] = []
    if capability("NBA", "possessions") != REAL:
        errors.append("expected NBA possessions=REAL as data capability")
    if possession_delta_authorized("NBA"):
        errors.append("NBA possessions=REAL must not authorize possession_delta")
    return errors


def audit_reserved_nulls(cfg: RollerConfig) -> list[str]:
    errors: list[str] = []
    for name in (
        "microprice",
        "order_book_imbalance",
        "signed_flow_lambda",
        "possession_delta",
        "sigma_K",
        "score_surface_gamma",
        "no_event_theta",
        "conditional_score_surface_delta",
    ):
        row = get_v4c_object(cfg, name)
        if row.get("status") in {"IMPLEMENTED", "PARTIAL"}:
            errors.append(f"{name} must not be implemented in V4C")
        if row.get("definition_version") is not None:
            errors.append(f"{name} must not carry a definition_version")
    return errors


def audit_not_yet_vs_not_constructible(cfg: RollerConfig) -> list[str]:
    errors: list[str] = []
    beta = get_v4c_object(cfg, "response_beta")
    micro = get_v4c_object(cfg, "microprice")
    if beta.get("status") != "NOT_YET_IMPLEMENTED":
        errors.append("response_beta must be NOT_YET_IMPLEMENTED")
    if micro.get("status") != "NOT_CONSTRUCTIBLE":
        errors.append("microprice must be NOT_CONSTRUCTIBLE")
    return errors


def audit_measurement_classes(cfg: RollerConfig) -> list[str]:
    errors: list[str] = []
    vol = get_v4c_object(cfg, "realized_market_volatility")
    if vol.get("canonical_identity") != "market_absolute_variation":
        errors.append("realized_market_volatility must map to market_absolute_variation")
    if vol.get("measurement_class") != "PATH_DESCRIPTOR":
        errors.append("realized_market_volatility must be PATH_DESCRIPTOR")
    gamma = get_v4c_object(cfg, "discrete_gamma")
    surface = get_v4c_object(cfg, "score_surface_gamma")
    if gamma.get("measurement_class") == surface.get("measurement_class"):
        errors.append("discrete_gamma class must differ from score_surface_gamma")
    return errors


def run_v4c_constructibility_validate(cfg: RollerConfig) -> dict[str, Any]:
    errors: list[str] = []
    errors.extend(audit_registry(cfg))
    errors.extend(audit_no_proxy())
    errors.extend(audit_possession_not_implemented())
    errors.extend(audit_reserved_nulls(cfg))
    errors.extend(audit_not_yet_vs_not_constructible(cfg))
    errors.extend(audit_measurement_classes(cfg))
    for row in v4c_objects(cfg):
        if row.get("edge_claim"):
            errors.append(f"{row.get('measurement_name')} claims edge")
    return {"status": "FAIL" if errors else "PASS", "errors": errors}
