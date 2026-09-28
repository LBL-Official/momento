"""Jump-owned Austin research-context adapter. persist=False. Not Ballhog."""

from __future__ import annotations

from typing import Any

from roller.dre.adapters import austin as dre_austin
from roller.jump.errors import JumpError

AUSTIN_ADAPTER = "roller.jump.adapters.austin.query_at persist=False"


def query_at(trade: dict[str, Any], as_of, persist: bool = False) -> dict[str, Any]:
    if persist:
        raise JumpError("QUERY_REJECTED", "Jump Austin queries must use persist=False")
    return dre_austin.query_at(trade, as_of)


get_trade = dre_austin.get_trade
list_trades = dre_austin.list_trades
get_replay = dre_austin.get_replay


def research_context(trade_id: str | None = None, as_of: str | None = None) -> dict[str, Any]:
    """Read-only Austin snapshot for Jump. Missing is UNAVAILABLE."""
    try:
        trades = list_trades()
    except Exception as exc:  # noqa: BLE001
        return {
            "availability": "UNAVAILABLE",
            "source": "AUSTIN",
            "adapter": AUSTIN_ADAPTER,
            "permission": "QUERY",
            "detail": f"{type(exc).__name__}: {exc}",
            "live_execution": False,
        }
    wanted = str(trade_id or "").strip()
    trade = get_trade(wanted) if wanted else (trades[0] if trades else None)
    if trade is None:
        return {
            "availability": "UNAVAILABLE",
            "source": "AUSTIN",
            "adapter": AUSTIN_ADAPTER,
            "permission": "QUERY",
            "detail": "no Austin trade",
            "live_execution": False,
            "n": 604,
            "universe": "choosin_nba_2q3q_604",
        }
    stamp = as_of
    if not stamp:
        try:
            replay = get_replay(str(trade.get("trade_id") or ""))
            path = list(replay.get("path") or [])
            usable = [row for row in path if isinstance(row, dict) and row.get("t")]
            stamp = usable[len(usable) // 2]["t"] if usable else None
        except Exception:  # noqa: BLE001
            stamp = None
    if not stamp:
        return {
            "availability": "UNAVAILABLE",
            "source": "AUSTIN",
            "adapter": AUSTIN_ADAPTER,
            "permission": "QUERY",
            "detail": "as_of unavailable",
            "trade_id": trade.get("trade_id"),
            "live_execution": False,
            "n": 604,
            "universe": "choosin_nba_2q3q_604",
        }
    try:
        query = query_at(trade, stamp, persist=False)
    except Exception as exc:  # noqa: BLE001
        return {
            "availability": "UNAVAILABLE",
            "source": "AUSTIN",
            "adapter": AUSTIN_ADAPTER,
            "permission": "QUERY",
            "detail": str(getattr(exc, "message", exc)),
            "trade_id": trade.get("trade_id"),
            "as_of": stamp,
            "live_execution": False,
            "n": 604,
            "universe": "choosin_nba_2q3q_604",
        }
    cond = query.get("conditional_ev") if isinstance(query.get("conditional_ev"), dict) else {}
    support = query.get("support") if isinstance(query.get("support"), dict) else {}
    return {
        "availability": query.get("status") or "OBSERVED",
        "source": "AUSTIN",
        "adapter": AUSTIN_ADAPTER,
        "permission": "QUERY",
        "write": "DENY",
        "trade_id": trade.get("trade_id"),
        "as_of": stamp,
        "conditional_ev_cents": cond.get("conditional_ev_cents"),
        "support": support.get("support"),
        "effective_sample_size": support.get("effective_sample_size"),
        "n": 604,
        "universe": "choosin_nba_2q3q_604",
        "live_feed": "UNAVAILABLE",
        "live_execution": False,
        "provenance": {"interface": "austin.query_at", "persist": False},
    }
