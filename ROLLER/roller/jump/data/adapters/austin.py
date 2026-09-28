"""Austin read adapter. persist=False. Does not copy the 604 book."""

from __future__ import annotations

from typing import Any

from roller.jump.data.models import AUSTIN_N, AUSTIN_UNIVERSE, LIVE_EXECUTION, UNAVAILABLE
from roller.jump.errors import JumpError


def _unavailable(detail: str, **extra: Any) -> dict[str, Any]:
    return {
        "availability": UNAVAILABLE,
        "source_system": "austin",
        "source": "AUSTIN",
        "universe": AUSTIN_UNIVERSE,
        "n": AUSTIN_N,
        "permission": "QUERY",
        "write": "DENY",
        "live_execution": LIVE_EXECUTION,
        "live_feed": UNAVAILABLE,
        "detail": detail,
        **extra,
    }


def query_at_payload(params: dict[str, Any]) -> dict[str, Any]:
    from roller.jump.adapters.austin import get_replay, get_trade, list_trades, query_at

    trade_id = str(params.get("trade_id") or "").strip()
    as_of = params.get("as_of")
    try:
        trade = get_trade(trade_id) if trade_id else None
        if trade is None:
            trades = list_trades()
            trade = trades[0] if trades else None
        if trade is None:
            return _unavailable("no Austin trade", trade_id=trade_id or None)
        stamp = as_of
        if not stamp:
            replay = get_replay(str(trade.get("trade_id") or ""))
            path = [row for row in (replay.get("path") or []) if isinstance(row, dict) and row.get("t")]
            stamp = path[len(path) // 2]["t"] if path else None
        if not stamp:
            return _unavailable("as_of unavailable", trade_id=trade.get("trade_id"))
        body = query_at(trade, stamp, persist=False)
    except JumpError as exc:
        return _unavailable(exc.message, trade_id=trade_id or None, error_code=exc.code)
    except Exception as exc:  # noqa: BLE001
        return _unavailable(f"{type(exc).__name__}: {exc}", trade_id=trade_id or None)
    cond = body.get("conditional_ev") if isinstance(body.get("conditional_ev"), dict) else {}
    support = body.get("support") if isinstance(body.get("support"), dict) else {}
    source_ts = body.get("source_timestamp") or body.get("inference_timestamp")
    if as_of and source_ts and str(source_ts) > str(as_of):
        return _unavailable(
            "PIT_REJECTED source_timestamp > as_of",
            trade_id=trade.get("trade_id"),
            as_of=str(as_of),
            source_timestamp=source_ts,
            error_code="PIT_REJECTED",
        )
    return {
        "availability": body.get("status") or "OBSERVED",
        "source_system": "austin",
        "source": "AUSTIN",
        "universe": AUSTIN_UNIVERSE,
        "n": AUSTIN_N,
        "permission": "QUERY",
        "write": "DENY",
        "persist": False,
        "trade_id": trade.get("trade_id"),
        "ticker": trade.get("ticker"),
        "event_id": trade.get("event_id"),
        "game_id": trade.get("game_id"),
        "as_of": stamp,
        "data_mode": "HISTORICAL_QUERY",
        "source_timestamp": source_ts,
        "austin.conditional_ev_cents": cond.get("conditional_ev_cents"),
        "conditional_ev_cents": cond.get("conditional_ev_cents"),
        "support": support.get("support"),
        "effective_sample_size": support.get("effective_sample_size"),
        "live_feed": UNAVAILABLE,
        "live_execution": LIVE_EXECUTION,
        "raw": {
            "status": body.get("status"),
            "model_version": body.get("model_version"),
            "conditional_ev": cond,
            "support": support,
            "state_change": body.get("state_change"),
            "t40": body.get("t40") or body.get("csv_t40"),
        },
    }


def get_trade_payload(params: dict[str, Any]) -> dict[str, Any]:
    from roller.jump.adapters.austin import get_trade, list_trades

    trade_id = str(params.get("trade_id") or "").strip()
    try:
        trade = get_trade(trade_id) if trade_id else None
        if trade is None and not trade_id:
            trades = list_trades()
            trade = trades[0] if trades else None
    except Exception as exc:  # noqa: BLE001
        return _unavailable(f"{type(exc).__name__}: {exc}", trade_id=trade_id or None)
    if trade is None:
        return _unavailable("no Austin trade", trade_id=trade_id or None)
    return {
        "availability": "OBSERVED",
        "source_system": "austin",
        "universe": AUSTIN_UNIVERSE,
        "n": AUSTIN_N,
        "permission": "QUERY",
        "write": "DENY",
        "data_mode": "HISTORICAL_QUERY",
        "live_execution": LIVE_EXECUTION,
        "trade": {
            "trade_id": trade.get("trade_id"),
            "ticker": trade.get("ticker"),
            "event_id": trade.get("event_id"),
            "game_id": trade.get("game_id"),
            "entry_timestamp": trade.get("entry_timestamp"),
            "quarter": trade.get("quarter"),
        },
    }


def replay_payload(params: dict[str, Any]) -> dict[str, Any]:
    from roller.dre.adapters.austin import replay_clipped
    from roller.jump.adapters.austin import get_replay

    trade_id = str(params.get("trade_id") or "").strip()
    as_of = params.get("as_of")
    try:
        body = replay_clipped(trade_id, as_of) if as_of else get_replay(trade_id)
    except Exception as exc:  # noqa: BLE001
        return _unavailable(f"{type(exc).__name__}: {exc}", trade_id=trade_id or None)
    return {
        "availability": body.get("status") or "OBSERVED",
        "source_system": "austin",
        "universe": AUSTIN_UNIVERSE,
        "n": AUSTIN_N,
        "trade_id": body.get("trade_id"),
        "ticker": body.get("ticker"),
        "data_mode": "HISTORICAL_QUERY",
        "as_of": as_of,
        "path_n": len(body.get("path") or []),
        "candle_path_not_fill": True,
        "live_execution": LIVE_EXECUTION,
        "replay": body,
    }


def list_universe() -> dict[str, Any]:
    from roller.jump.adapters.austin import list_trades

    try:
        trades = list_trades()
    except Exception as exc:  # noqa: BLE001
        return _unavailable(f"{type(exc).__name__}: {exc}")
    return {
        "availability": "OBSERVED",
        "source_system": "austin",
        "universe": AUSTIN_UNIVERSE,
        "n": len(trades),
        "n_lock": AUSTIN_N,
        "permission": "QUERY",
        "write": "DENY",
        "owner": "austin",
        "live_execution": LIVE_EXECUTION,
        "trade_ids": [str(row.get("trade_id") or "") for row in trades],
    }
