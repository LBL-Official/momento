"""Compose one Vital desk payload. Read-only. Does not observe Kalshi."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from roller.vital.versions import BOT_ID, CAVEATS, HONESTY

SURFACES = ("list", "full")
SPORTS_SHARD_LABEL = "sports shard 3 (baseball / basketball / tennis)"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _book_header(account: dict[str, Any] | None, *, environment: str) -> dict[str, Any]:
    row = account if isinstance(account, dict) else {}
    return {
        "environment": environment,
        "top_level_cents": row.get("top_level_cents"),
        "sports_shard_cents": row.get("mlb_shard_cents"),
        "catch_all_shard_cents": row.get("catch_all_shard_cents"),
        "day_delta_cents": row.get("day_delta_cents"),
        "week_delta_cents": row.get("week_delta_cents"),
        "origin_pnl_cents": row.get("origin_pnl_cents"),
        "shard_label": row.get("shard_label") or SPORTS_SHARD_LABEL,
        "source": row.get("source"),
        "observed_at": row.get("observed_at"),
    }


def build_desk(
    bot_id: str | None = None,
    surface: str = "list",
    *,
    root=None,
) -> dict[str, Any]:
    from roller.vital import api as vapi
    from roller.vital.errors import VitalError

    wanted = str(surface or "list").strip().lower()
    if wanted not in SURFACES:
        raise VitalError("REJECTED", f"desk surface must be list or full, not {surface}")
    health = vapi.handle_health(root=root)
    bankroll = vapi.handle_bankroll_get(root=root)
    raw_id = str(bot_id or "").strip() or BOT_ID
    selected = vapi.handle_bots_get(raw_id, root=root)
    selected_id = str(selected.get("bot_id") or raw_id)
    focus = {
        "bot": selected,
        "status": vapi.handle_status(selected_id, root=root),
        "runtime": vapi.handle_runtime(selected_id, root=root),
        "kalshi": vapi.handle_kalshi(selected_id, root=root),
        "strategy": vapi.handle_strategy(selected_id, root=root),
        "controls": vapi.handle_controls(selected_id, root=root),
        "integration": vapi.handle_integration(selected_id, root=root),
    }
    listed = vapi.handle_bots_list(root=root)
    selected = next((row for row in listed.get("bots") or [] if row.get("bot_id") == selected_id), selected)
    focus["bot"] = selected
    surfaces: dict[str, Any] = {}
    if wanted == "full":
        surfaces = {
            "parameters": vapi.handle_parameters(selected_id, root=root),
            "kalshi_health": vapi.handle_kalshi_health(selected_id, root=root),
            "logs": vapi.handle_logs(selected_id, root=root),
            "execution": vapi.handle_execution(selected_id, root=root),
        }
        if selected_id == BOT_ID or selected.get("kind") == "grandfathered":
            events = vapi.handle_events(selected_id, root=root)
            surfaces["events"] = list(events.get("events") or [])[-40:]
            surfaces["orders"] = vapi.handle_orders(selected_id, root=root)
            surfaces["positions"] = vapi.handle_positions(selected_id, root=root)
            surfaces["diagnose"] = vapi.handle_diagnose(selected_id, root=root)
        else:
            surfaces["events"] = []
            surfaces["orders"] = None
            surfaces["positions"] = None
            surfaces["diagnose"] = None
    return {
        "product": "Vital",
        "surface": wanted,
        "selected_id": selected_id,
        "built_at": _utc_now(),
        "observe_included": False,
        "http_200_not_running": True,
        "health": health,
        "bots": listed.get("bots") or [],
        "n": listed.get("n") or 0,
        "bankroll": bankroll,
        "header": {
            "PRODUCTION": _book_header(bankroll.get("account") if isinstance(bankroll, dict) else None, environment="PRODUCTION"),
            "DEMO": _book_header(
                bankroll.get("demo_account") if isinstance(bankroll, dict) else None,
                environment="DEMO",
            ),
        },
        "focus": focus,
        "surfaces": surfaces,
        "honesty": dict(HONESTY),
        "caveats": list(CAVEATS),
    }
