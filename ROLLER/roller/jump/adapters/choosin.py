"""Jump-owned Choosin research-context adapter. STATIC. Not Ballhog."""

from __future__ import annotations

from typing import Any

from roller.dre.adapters.choosin import get_trade_context as dre_get_trade_context

CHOOSIN_ADAPTER = "roller.jump.adapters.choosin.get_trade_context"


def research_context() -> dict[str, Any]:
    try:
        body = dre_get_trade_context()
    except Exception as exc:  # noqa: BLE001
        return {
            "availability": "UNAVAILABLE",
            "source": "CHOOSIN_TEXAS",
            "adapter": CHOOSIN_ADAPTER,
            "permission": "QUERY",
            "write": "DENY",
            "detail": f"{type(exc).__name__}: {exc}",
            "n": 936,
            "universe": "derived_four_936",
            "live_execution": False,
        }
    entry = body.get("entry_definition") if isinstance(body.get("entry_definition"), dict) else {}
    return {
        "availability": body.get("availability") or "UNAVAILABLE",
        "source": "CHOOSIN_TEXAS",
        "adapter": CHOOSIN_ADAPTER,
        "permission": "QUERY",
        "write": "DENY",
        "universe": body.get("universe") or "derived_four_936",
        "n": body.get("historical_n") or 936,
        "entry_cents": entry.get("entry_cents"),
        "loss_barrier_cents": entry.get("loss_barrier_cents"),
        "historical_survival_rate": body.get("historical_survival_rate"),
        "pit_kind": "STATIC",
        "live_execution": False,
        "provenance": {"interface": "choosin.get_trade_context", "pit_kind": "STATIC"},
    }
