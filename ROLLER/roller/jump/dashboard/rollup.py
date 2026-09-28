"""Portfolio rollup from tracks. Never sum unavailable into zero."""

from __future__ import annotations

from typing import Any

from roller.jump.dashboard.heartbeat import confirmed, unavailable


def _confirmed_values(tracks: list[dict[str, Any]], side: str, key: str) -> list[Any] | None:
    if not tracks:
        return None
    values: list[Any] = []
    for row in tracks:
        metric = ((row.get(side) or {}).get(key)) or {}
        if metric.get("status") != "CONFIRMED" or metric.get("value") is None:
            return None
        values.append(metric["value"])
    return values


def _sum_or_unavailable(tracks: list[dict[str, Any]], side: str, key: str) -> dict[str, Any]:
    values = _confirmed_values(tracks, side, key)
    if values is None:
        return unavailable("UNAVAILABLE")
    if all(isinstance(v, bool) for v in values):
        return confirmed(any(values))
    try:
        return confirmed(sum(int(v) for v in values))
    except (TypeError, ValueError):
        return unavailable("UNAVAILABLE")


def _side_metrics(tracks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "bankroll": _sum_or_unavailable(tracks, "actual", "bankroll"),
        "pnl": _sum_or_unavailable(tracks, "actual", "pnl"),
        "origin_pnl": _sum_or_unavailable(tracks, "actual", "origin_pnl"),
        "sharpe": unavailable(),
        "day_pnl": _sum_or_unavailable(tracks, "actual", "day_pnl"),
        "week_pnl": _sum_or_unavailable(tracks, "actual", "week_pnl"),
        "open_mlb_positions": _sum_or_unavailable(tracks, "actual", "open_mlb_positions"),
        "trades": _sum_or_unavailable(tracks, "actual", "trades"),
        "weekly_trades": _sum_or_unavailable(tracks, "actual", "weekly_trades"),
    }


def _expected() -> dict[str, Any]:
    return {
        "day_ev": unavailable(),
        "week_ev": unavailable(),
        "day_pnl": unavailable(),
        "week_pnl": unavailable(),
        "pnl": unavailable(),
        "sharpe": unavailable(),
    }


def _env_tracks(tracks: list[dict[str, Any]], environment: str) -> list[dict[str, Any]]:
    wanted = environment.upper()
    return [row for row in tracks if str(row.get("environment") or "").upper() == wanted]


def rollup_tracks(tracks: list[dict[str, Any]]) -> dict[str, Any]:
    demo = _env_tracks(tracks, "DEMO")
    live = [
        row
        for row in tracks
        if str(row.get("environment") or "").upper() == "PRODUCTION" or row.get("kind") == "grandfathered"
    ]
    return {
        "track_n": len(tracks),
        "actual": _side_metrics(live),
        "expected": _expected(),
        "demo": {"track_n": len(demo), "actual": _side_metrics(demo), "expected": _expected()},
        "live": {"track_n": len(live), "actual": _side_metrics(live), "expected": _expected()},
        "honesty": {
            "actual_not_expected": True,
            "sum_skips_unavailable": True,
            "demo_not_added_to_live": True,
            "live_ev": "UNAVAILABLE",
        },
    }
