"""MLB 001 execution path facts. Observe the existing loop. Do not invent fills."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from roller.vital.bots import get_bot
from roller.vital.honesty import observation_unavailable, unavailable
from roller.vital.mlb_001.identity import BOT_ID, ENGINE_POINTER, FACTORY, STRATEGY_POINTER
from roller.vital.observe import observe_bot

PATH = (
    "Kalshi WS → strategies/mlb TradeIntent → crates/risk → "
    "apps/trading-engine live.rs submit_approved → Kalshi Create V2 → fill"
)

STAGES = (
    {
        "id": "MARKET_DATA",
        "owner": "Kalshi WS + crates/kalshi",
        "pointer": "crates/kalshi",
        "proposes": False,
        "submits": False,
        "invents_fills": False,
    },
    {
        "id": "NORMALIZATION",
        "owner": "crates/kalshi mapping",
        "pointer": "crates/kalshi",
        "proposes": False,
        "submits": False,
        "invents_fills": False,
    },
    {
        "id": "FEATURE_STATE",
        "owner": "MlbContext",
        "pointer": STRATEGY_POINTER,
        "proposes": False,
        "submits": False,
        "invents_fills": False,
    },
    {
        "id": "SIGNAL",
        "owner": "strategies/mlb MlbStrategy::observe",
        "pointer": STRATEGY_POINTER,
        "signal": FACTORY["signal"],
        "locked": True,
        "proposes": True,
        "submits": False,
        "invents_fills": False,
    },
    {
        "id": "RISK",
        "owner": "crates/risk PaperRiskEngine.decide_entry",
        "pointer": "crates/risk",
        "proposes": False,
        "submits": False,
        "invents_fills": False,
    },
    {
        "id": "ORDER_DECISION",
        "owner": "ApprovedTradeIntent",
        "pointer": "crates/core",
        "proposes": False,
        "submits": False,
        "invents_fills": False,
        "note": "Only Risk-approved intents may reach submit_approved.",
    },
    {
        "id": "EXECUTION",
        "owner": "apps/trading-engine live.rs submit_approved",
        "pointer": ENGINE_POINTER,
        "venue": "Kalshi Create V2",
        "proposes": False,
        "submits": True,
        "invents_fills": False,
        "note": "Browser and Vital API do not submit.",
    },
    {
        "id": "FILL",
        "owner": "venue fill_history",
        "pointer": ENGINE_POINTER,
        "proposes": False,
        "submits": False,
        "invents_fills": False,
        "fill_is_not_trade": True,
        "catalog_fills_are_not_trades": True,
        "note": "A fill is not a reconstructed trade. Phase 6 owns that table.",
    },
)


def pipeline_view(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    get_bot(bot_id, root=root)
    runtime = observe_bot(bot_id, root=root, persist=False)["runtime"]
    stages = []
    for raw in STAGES:
        row = dict(raw)
        row["observation"] = observation_unavailable("per-stage host dump unread")
        stages.append(row)
    return {
        "bot_id": BOT_ID,
        "phase": 5,
        "layer": "pipeline",
        "path": PATH,
        "model_vs_risk_vs_execution": True,
        "strategy_submits": False,
        "risk_submits": False,
        "vital_submits": False,
        "browser_submits": False,
        "signal_locked": FACTORY["signal"],
        "does_not_retune": True,
        "does_not_invent_fills": True,
        "catalog_fills_are_not_trades": True,
        "order_not_fill": True,
        "fill_not_trade": True,
        "stages": stages,
        "host_lifecycle": runtime.get("lifecycle"),
        "host_health": runtime.get("health"),
        "live_armed": runtime.get("live_armed"),
        "live_ev": unavailable("UNAVAILABLE"),
        "sharpe": unavailable("UNAVAILABLE"),
        "http_200_not_running": True,
        "note": (
            "This endpoint exposes the existing deterministic path. "
            "It does not change 80/81/83/89 and does not invent fills."
        ),
    }
