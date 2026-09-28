"""Drevo position state for the 78/67 book."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from roller.austin.clock import format_clock
from roller.austin.errors import AustinError
from roller.austin_first78.config import EV_DEFINITION, EV_FORMULA
from roller.dre.adapters.austin import normalize_live_state
from roller.dre.composer import _jsonable
from roller.dre.mapping import assert_observation_state, hold_reason_v1, observation_from_austin
from roller.dre.models import DYNAMIC_RISK_CLASS_V1, LIST_SCHEMA_VERSION, LIVE_EXECUTION, SCHEMA_VERSION, future_state_legend, intervention_stub
from roller.dre.pit import DrePitError, Stamped, assert_all_not_after, clip_path, iso, require_as_of, to_utc
from roller.dre_first78.context import AUSTIN_UNIVERSE, CHOOSIN_UNIVERSE, austin_n, get_trade, last_observed_by_trade, list_trades, query_at, replay, trade_context

PRODUCT = "DRE"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def list_row(trade: dict[str, Any], observed: dict[str, Any] | None) -> dict[str, Any]:
    last = observed or {}
    ticker = str(trade.get("ticker") or "")
    return {
        "position_id": trade.get("trade_id"),
        "trade_id": trade.get("trade_id"),
        "ticker": ticker,
        "sport": "NBA",
        "game": ticker,
        "side": trade.get("entry_side"),
        "position_label": f"{ticker} YES",
        "entry_price_cents": trade.get("entry_price_cents"),
        "entry_timestamp": trade.get("entry_timestamp"),
        "last_observed_price_cents": last.get("last_observed_price_cents"),
        "last_observed_at": last.get("last_observed_at"),
        "slice": trade.get("slice"),
        "quarter": trade.get("quarter"),
        "game_date": trade.get("game_date"),
        "mode": "HISTORICAL",
        "live_feed": "UNAVAILABLE",
        "position_status": "HISTORICAL",
    }


def list_positions(*, slice_name: str | None = None, q: str | None = None, dataset_split: str | None = None) -> dict[str, Any]:
    observed = last_observed_by_trade()
    needle = str(q or "").strip().lower()
    slice_f = str(slice_name or "").strip().upper()
    rows = []
    for trade in list_trades():
        if dataset_split:
            continue
        if slice_f and str(trade.get("slice") or "").upper() != slice_f and str(trade.get("quarter") or "") != slice_f:
            continue
        row = list_row(trade, observed.get(str(trade.get("trade_id"))))
        if needle and needle not in " ".join(str(row.get(key) or "") for key in ("game", "ticker", "position_label", "position_id")).lower():
            continue
        rows.append(row)
    rows.sort(key=lambda row: (str(row.get("game_date") or ""), str(row.get("ticker") or "")), reverse=True)
    return _jsonable(
        {
            "schema_version": LIST_SCHEMA_VERSION,
            "book": "FIRST78_67",
            "mode": "HISTORICAL",
            "live_feed": "UNAVAILABLE",
            "live_execution": LIVE_EXECUTION,
            "submits": False,
            "book_n": austin_n(),
            "universe": AUSTIN_UNIVERSE,
            "choosin_universe": CHOOSIN_UNIVERSE,
            "n": len(rows),
            "positions": rows,
            "note": "Austin 78/67 historical book. Last Observed is an artifact snapshot, not a live quote.",
            "generated_at": iso(_now()),
        }
    )


def _empty(position_id: str, mode: str, as_of: str | None, detail: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "book": "FIRST78_67",
        "mode": mode,
        "position_id": position_id,
        "as_of": as_of,
        "product": PRODUCT,
        "live_execution": LIVE_EXECUTION,
        "submits": False,
        "live_feed": "UNAVAILABLE",
        "position": None,
        "trade_context": None,
        "live_state": {"source": "AUSTIN", "availability": "UNAVAILABLE", "detail": detail},
        "dynamic_risk": {
            "observation_state": "UNAVAILABLE",
            "hold_reason_status": hold_reason_v1(),
            "dynamic_risk_class": DYNAMIC_RISK_CLASS_V1,
            "reason": detail,
        },
        "intervention": intervention_stub(),
        "evidence_timeline": [],
        "future_state_legend": future_state_legend(),
    }


def compose_position(position_id: str, *, as_of: str | None = None, mode: Literal["HISTORICAL", "REPLAY"] = "HISTORICAL") -> dict[str, Any]:
    wanted = str(position_id or "").strip()
    generated = _now()
    trade = get_trade(wanted)
    if trade is None:
        return _empty(wanted or "UNKNOWN", mode, as_of, f"unknown trade_id {wanted}")
    entry_ts = to_utc(trade.get("entry_timestamp"))
    try:
        replay_body = replay(wanted)
    except AustinError as exc:
        replay_body = {"path": [], "detail": str(exc)}
    full_path = [row for row in (replay_body.get("path") or []) if isinstance(row, dict)]
    if as_of:
        as_of_dt = require_as_of(as_of)
    elif full_path:
        as_of_dt = to_utc(full_path[-1].get("t")) or entry_ts or generated
    else:
        as_of_dt = entry_ts or generated
    as_of_iso = iso(as_of_dt)
    path = clip_path(as_of_dt, full_path, time_key="t")
    try:
        context = trade_context()
        ctx_stamp = context.pop("stamp", None)
        stamps = [ctx_stamp] if isinstance(ctx_stamp, Stamped) else []
    except Exception as exc:  # noqa: BLE001
        context = {"source": "CHOOSIN_TEXAS", "availability": "UNAVAILABLE", "detail": f"{type(exc).__name__}: {exc}"}
        stamps = []
    query = None
    query_error = None
    if entry_ts is not None and as_of_dt < entry_ts:
        query_error = "as_of is before entry"
    else:
        try:
            query = query_at(trade, as_of_dt)
        except (AustinError, DrePitError) as exc:
            query_error = exc.message if hasattr(exc, "message") else str(exc)
    try:
        assert_all_not_after(as_of_dt, stamps)
    except DrePitError as exc:
        return _empty(wanted, mode, as_of_iso, exc.message)
    point = path[-1] if path else None
    form = (query or {}).get("form") if isinstance((query or {}).get("form"), dict) else {}
    current_price = None
    if point and point.get("price_cents") is not None:
        current_price = int(point["price_cents"])
    elif form.get("current_price_cents") is not None:
        current_price = int(form["current_price_cents"])
    entry_price = trade.get("entry_price_cents")
    change = None if entry_price is None or current_price is None else int(current_price) - int(entry_price)
    live_state = normalize_live_state(query, point)
    cond = live_state.get("conditional_ev") if isinstance(live_state.get("conditional_ev"), dict) else {}
    cond["definition"] = EV_DEFINITION
    cond["formula"] = EV_FORMULA
    cond["note"] = "78/67 nearest-state estimate. Neighbor stop rate is the 67¢ stop."
    live_state["conditional_ev"] = cond
    if query_error and query is None:
        live_state = {"source": "AUSTIN", "availability": "UNAVAILABLE", "live_feed": "UNAVAILABLE", "detail": query_error}
    mapped = observation_from_austin(query if query_error is None else None)
    if query_error:
        mapped = {"observation_state": "UNAVAILABLE", "insufficient_support": "before entry" in query_error, "reason": query_error}
    observation_state = assert_observation_state(str(mapped["observation_state"]))
    change_block = live_state.get("state_change") if isinstance(live_state.get("state_change"), dict) else {}
    support = live_state.get("model_support") if isinstance(live_state.get("model_support"), dict) else {}
    hist = context.get("historical_ev") if isinstance(context.get("historical_ev"), dict) else {}
    return _jsonable(
        {
            "schema_version": SCHEMA_VERSION,
            "book": "FIRST78_67",
            "mode": mode,
            "position_id": wanted,
            "as_of": as_of_iso,
            "generated_at": iso(generated),
            "product": PRODUCT,
            "live_execution": LIVE_EXECUTION,
            "submits": False,
            "live_feed": "UNAVAILABLE",
            "phase3_is_execution_policy": False,
            "position": {
                "position_id": wanted,
                "trade_id": wanted,
                "ticker": trade.get("ticker"),
                "sport": "NBA",
                "side": trade.get("entry_side"),
                "game": str(trade.get("ticker") or ""),
                "position_label": f"{trade.get('ticker') or ''} YES",
                "entry_price_cents": entry_price,
                "entry_timestamp": iso(entry_ts) or trade.get("entry_timestamp"),
                "quantity": 1,
                "current_price_cents": current_price,
                "price_change_cents": change,
                "unrealized_pnl_cents": change,
                "unrealized_pnl_basis": "CANDLE_PATH_NOT_FILL",
                "period": form.get("current_quarter") or trade.get("quarter"),
                "clock": format_clock(form.get("current_seconds_remaining")) if form else None,
                "home_score": None if not point else point.get("home_score"),
                "away_score": None if not point else point.get("away_score"),
                "slice": trade.get("slice"),
                "quarter": trade.get("quarter"),
                "game_date": trade.get("game_date"),
                "mode": mode,
                "live_feed": "UNAVAILABLE",
                "as_of": as_of_iso,
            },
            "trade_context": context,
            "live_state": live_state,
            "dynamic_risk": {
                "observation_state": observation_state,
                "insufficient_support": bool(mapped.get("insufficient_support")),
                "hold_reason_status": hold_reason_v1(),
                "dynamic_risk_class": DYNAMIC_RISK_CLASS_V1,
                "austin_conditional_ev": cond.get("conditional_ev_cents"),
                "change_from_entry": change_block.get("ev_change"),
                "historical_support": support.get("support"),
                "reason": mapped.get("reason"),
                "risk_metric_name": "T67_RISK_PROXY",
                "unresolved": ["dynamic_risk_class", "pit_deterioration_state", "authorized_policy"],
                "ev_blocks": {
                    "choosin_texas_prior": {
                        "title": "CHOOSIN TEXAS PRIOR",
                        "label": "78→67 population EV",
                        "definition": hist.get("definition"),
                        "ev_display": hist.get("ev_display"),
                        "note": "Historical trade prior. Not a before/after versus Austin.",
                    },
                    "austin_conditional": {
                        "title": "AUSTIN CONDITIONAL",
                        "label": "Conditional EV at as_of",
                        "definition": EV_DEFINITION,
                        "conditional_ev_cents": cond.get("conditional_ev_cents"),
                        "note": "Historical nearest-state estimate on the 78/67 fit.",
                    },
                    "austin_state_change": {
                        "title": "AUSTIN STATE CHANGE",
                        "ev_at_entry": change_block.get("ev_at_entry"),
                        "ev_now": change_block.get("ev_now"),
                        "ev_change": change_block.get("ev_change"),
                        "note": "The only source-backed dynamic EV change. Not the derived-four population EV.",
                    },
                },
                "note": "Drevo V1 has no risk classifier. Observation is the 78/67 Austin query.",
            },
            "intervention": intervention_stub(),
            "evidence_timeline": [
                {
                    "event": "ENTRY",
                    "timestamp": iso(entry_ts) or trade.get("entry_timestamp"),
                    "market_price_cents": entry_price,
                    "source": "AUSTIN_REPLAY",
                    "note": "FIRST78 entry. Candle path ≠ fill.",
                },
                {
                    "event": "CURRENT_AS_OF",
                    "timestamp": as_of_iso,
                    "market_price_cents": current_price,
                    "source": "DRE",
                    "note": "Current at as_of. Not live.",
                },
            ],
            "future_state_legend": future_state_legend(),
            "chart": {"entry_cents": 78, "loss_barrier_cents": 67, "as_of": as_of_iso, "path": path, "candle_path_not_fill": True},
            "freshness": {"choosin_texas": "STATIC", "austin": "HISTORICAL" if query else "UNAVAILABLE", "live_feed": "UNAVAILABLE", "as_of": as_of_iso},
            "provenance": {
                "choosin_texas_source": context.get("source_object_id"),
                "austin_source": "austin_first78_historical_query",
                "austin_universe": AUSTIN_UNIVERSE,
                "austin_n": austin_n(),
                "choosin_universe": CHOOSIN_UNIVERSE,
                "choosin_n": context.get("historical_n"),
                "austin_model_version": None if not query else query.get("model_version"),
                "austin_dataset_version": None if not query else query.get("dataset_version"),
                "as_of": as_of_iso,
                "mode": mode,
            },
        }
    )
