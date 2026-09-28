"""Capability → registered adapter. No LLM. Missing is UNAVAILABLE."""

from __future__ import annotations

from importlib import import_module
from typing import Any, Callable

from roller.systimo.models import UNAVAILABLE

CapabilityFn = Callable[[], dict[str, Any]]


def _call(module: str, attr: str, **kwargs: Any) -> dict[str, Any]:
    try:
        mod = import_module(module)
        fn = getattr(mod, attr)
        result = fn(**kwargs) if kwargs else fn()
        if isinstance(result, dict):
            return result
        return {"availability": "OBSERVED", "value": result, "adapter": f"{module}.{attr}"}
    except Exception as exc:  # noqa: BLE001
        return {
            "availability": UNAVAILABLE,
            "capability_status": UNAVAILABLE,
            "adapter": f"{module}.{attr}",
            "detail": f"{type(exc).__name__}: {exc}",
            "live_execution": False,
        }


def _import_only(module: str) -> dict[str, Any]:
    try:
        import_module(module)
        return {
            "availability": "HEALTHY",
            "adapter": module,
            "permission": "QUERY",
            "live_execution": False,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "availability": UNAVAILABLE,
            "adapter": module,
            "detail": f"{type(exc).__name__}: {exc}",
            "live_execution": False,
        }


def invoke_capability(name: str) -> dict[str, Any]:
    fn = CAPABILITIES.get(name)
    if fn is None:
        return {
            "availability": UNAVAILABLE,
            "capability": name,
            "error_code": "UNREGISTERED_INTERFACE",
            "detail": f"no adapter registered for {name}",
            "live_execution": False,
        }
    body = fn()
    body.setdefault("capability", name)
    body.setdefault("live_execution", False)
    return body


CAPABILITIES: dict[str, CapabilityFn] = {
    "AUSTIN_QUERY_AT": lambda: _call("roller.jump.adapters.austin", "research_context"),
    "CHOOSIN_TRADE_CONTEXT": lambda: _call("roller.jump.adapters.choosin", "research_context"),
    "VITAL_BOT_STATUS": lambda: _import_only("roller.jump.vital_client"),
    "WAREHOUSE_QUERY": lambda: _import_only("roller.jump.warehouse.registry"),
    "SUPERASI_ITI": lambda: _import_only("roller.jump.iti"),
    "BALLHOG_INTENT": lambda: _import_only("roller.ballhog.api"),
    "TK_ULTRA_ASSESSMENT": lambda: _import_only("roller.tk_ultra.api"),
    "LS_HEALTH": lambda: _import_only("roller.systimo.adapters.ls"),
    "AUSTIN_GET_TRADE": lambda: _import_only("roller.dre.adapters.austin"),
    "AUSTIN_REPLAY": lambda: _import_only("roller.dre.adapters.austin"),
    "AUSTIN_UNIVERSE": lambda: _import_only("roller.jump.data.adapters.austin"),
    "ROLLER_GAME_IDENTITY": lambda: _import_only("roller.jump.data.adapters.roller"),
    "ROLLER_OBSERVATIONS": lambda: _import_only("roller.jump.data.adapters.roller"),
    "ROLLER_PBP": lambda: _import_only("roller.jump.data.adapters.roller"),
    "ROLLER_SETTLEMENT": lambda: _import_only("roller.jump.data.adapters.roller"),
    "SYSTIMO_CATALOG": lambda: _import_only("roller.jump.data.adapters.systimo"),
    "POSITMAN_PLAN": lambda: _import_only("roller.positman.api"),
    "DREVO_DECISION": lambda: _import_only("roller.dre.decision"),
    "TRANSITION_TRACE": lambda: _import_only("roller.systimo.transitions"),
    "ORCHESTRA_CONTEXT": lambda: _import_only("roller.systimo.orchestra"),
}
