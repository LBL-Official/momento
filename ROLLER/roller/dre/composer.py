"""DREComposer — deterministic V1 synthesis. No frontend inference."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from roller.austin.clock import format_clock
from roller.austin.errors import AustinError
from roller.choosin_texas.models import ChoosinTexasError
from roller.dre.adapters.austin import (
    get_replay,
    get_trade,
    last_observed_by_trade,
    list_row,
    list_trades,
    normalize_live_state,
    query_at,
)
from roller.dre.pit import DrePitError, Stamped, assert_all_not_after, clip_path, iso, require_as_of, to_utc
from roller.dre.adapters.choosin import get_trade_context
from roller.dre.mapping import assert_observation_state, hold_reason_v1, observation_from_austin
from roller.dre.models import (
    AUSTIN_EV_DEFINITION,
    CT_EV_DEFINITION,
    DYNAMIC_RISK_CLASS_V1,
    LIST_SCHEMA_VERSION,
    LIVE_EXECUTION,
    PRODUCT,
    SCHEMA_VERSION,
    future_state_legend,
    intervention_stub,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _empty_envelope(
    *,
    position_id: str,
    mode: Literal["HISTORICAL", "REPLAY"],
    as_of: str | None,
    detail: str,
) -> dict[str, Any]:
    stamp = iso(_now())
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "position_id": position_id,
        "as_of": as_of,
        "generated_at": stamp,
        "product": PRODUCT,
        "live_execution": LIVE_EXECUTION,
        "submits": False,
        "live_feed": "UNAVAILABLE",
        "position": None,
        "trade_context": None,
        "live_state": {
            "source": "AUSTIN",
            "availability": "UNAVAILABLE",
            "live_feed": "UNAVAILABLE",
            "detail": detail,
        },
        "dynamic_risk": {
            "observation_state": "UNAVAILABLE",
            "insufficient_support": False,
            "hold_reason_status": hold_reason_v1(),
            "dynamic_risk_class": DYNAMIC_RISK_CLASS_V1,
            "austin_conditional_ev": None,
            "change_from_entry": None,
            "historical_support": None,
            "unresolved": [
                "dynamic_risk_class",
                "pit_deterioration_state",
                "authorized_policy",
            ],
            "reason": detail,
        },
        "intervention": intervention_stub(),
        "evidence_timeline": [],
        "future_state_legend": future_state_legend(),
        "history": [],
        "freshness": {
            "choosin_texas": "STATIC",
            "austin": "UNAVAILABLE",
            "live_feed": "UNAVAILABLE",
        },
        "provenance": {
            "choosin_texas_source": None,
            "austin_source": None,
            "jump_source": "NOT_WIRED",
            "generated_at": stamp,
            "as_of": as_of,
            "detail": detail,
        },
        "phase3_is_execution_policy": False,
    }


def list_positions(
    *,
    slice_name: str | None = None,
    q: str | None = None,
    dataset_split: str | None = None,
) -> dict[str, Any]:
    trades = list_trades()
    observed = last_observed_by_trade()
    needle = str(q or "").strip().lower()
    slice_f = str(slice_name or "").strip().upper()
    split_f = str(dataset_split or "").strip()
    rows: list[dict[str, Any]] = []
    for trade in trades:
        if slice_f and str(trade.get("slice") or "").upper() != slice_f and str(trade.get("quarter") or "") != slice_f:
            continue
        if split_f and str(trade.get("dataset_split") or "") != split_f:
            continue
        row = list_row(trade, observed.get(str(trade.get("trade_id"))))
        if needle:
            blob = " ".join(
                str(row.get(key) or "")
                for key in ("game", "ticker", "team", "position_label", "position_id")
            ).lower()
            if needle not in blob:
                continue
        rows.append(row)
    rows.sort(key=lambda row: (str(row.get("game_date") or ""), str(row.get("ticker") or "")), reverse=True)
    return _jsonable(
        {
            "schema_version": LIST_SCHEMA_VERSION,
            "mode": "HISTORICAL",
            "live_feed": "UNAVAILABLE",
            "live_execution": LIVE_EXECUTION,
            "submits": False,
            "book_n": 604,
            "universe": "nba_2q_3q_604",
            "n": len(rows),
            "positions": rows,
            "note": "Austin 604 historical book. Last Observed is artifact snapshot, not a live quote.",
            "generated_at": iso(_now()),
        }
    )


def compose_position(
    position_id: str,
    *,
    as_of: str | None = None,
    mode: Literal["HISTORICAL", "REPLAY"] = "HISTORICAL",
) -> dict[str, Any]:
    wanted = str(position_id or "").strip()
    generated = _now()
    trade = get_trade(wanted)
    if trade is None:
        return _empty_envelope(
            position_id=wanted or "UNKNOWN",
            mode=mode,
            as_of=as_of,
            detail=f"unknown trade_id {wanted}",
        )
    entry_ts = to_utc(trade.get("entry_timestamp"))
    try:
        replay = get_replay(wanted)
    except AustinError as exc:
        replay = {"path": [], "status": "UNAVAILABLE", "detail": str(exc)}
    full_path = list(replay.get("path") or [])
    if as_of:
        as_of_dt = require_as_of(as_of)
    elif full_path:
        as_of_dt = to_utc(full_path[-1].get("t")) or entry_ts or generated
    else:
        as_of_dt = entry_ts or generated
    as_of_iso = iso(as_of_dt)
    path = clip_path(as_of_dt, full_path, time_key="t")
    replay = {**replay, "path": path}

    stamps: list[Stamped] = []
    trade_context: dict[str, Any] | None
    try:
        trade_context = get_trade_context()
        ctx_stamp = trade_context.pop("stamp", None)
        if isinstance(ctx_stamp, Stamped):
            stamps.append(ctx_stamp)
    except (ChoosinTexasError, Exception) as exc:  # noqa: BLE001 — fail closed
        trade_context = {
            "source": "CHOOSIN_TEXAS",
            "availability": "UNAVAILABLE",
            "detail": f"{type(exc).__name__}: {exc}",
        }

    query: dict[str, Any] | None = None
    query_error: str | None = None
    if entry_ts is not None and as_of_dt < entry_ts:
        query_error = "as_of is before entry"
    else:
        try:
            query = query_at(trade, as_of_dt)
            q_stamp = query.get("stamp")
            if isinstance(q_stamp, Stamped):
                stamps.append(q_stamp)
                query.pop("stamp", None)
        except (AustinError, DrePitError) as exc:
            query_error = exc.message if isinstance(exc, (AustinError, DrePitError)) else str(exc)
            query = None

    try:
        assert_all_not_after(as_of_dt, stamps)
        for row in path:
            stamp = to_utc(row.get("t"))
            if stamp is not None:
                assert_all_not_after(
                    as_of_dt,
                    [Stamped("replay_path", row.get("price_cents"), "austin_replay", stamp, "PATH")],
                )
        if query and query.get("source_timestamp"):
            q_ts = to_utc(query.get("source_timestamp"))
            if q_ts is not None:
                assert_all_not_after(
                    as_of_dt,
                    [Stamped("austin_query", query.get("status"), "austin", q_ts, "QUERY")],
                )
    except DrePitError as exc:
        return _empty_envelope(
            position_id=wanted,
            mode=mode,
            as_of=as_of_iso,
            detail=exc.message,
        )

    point = path[-1] if path else None
    form = (query or {}).get("form") if isinstance((query or {}).get("form"), dict) else {}
    current_price = None
    if point and point.get("price_cents") is not None:
        current_price = int(point["price_cents"])
    elif form.get("current_price_cents") is not None:
        try:
            current_price = int(form["current_price_cents"])
        except (TypeError, ValueError):
            current_price = None
    entry_price = trade.get("entry_price_cents")
    change = None
    unrealized = None
    if entry_price is not None and current_price is not None:
        change = int(current_price) - int(entry_price)
        unrealized = change  # 1-lot candle-path mark
    home = point.get("home_score") if point else form.get("home_score_current")
    away = point.get("away_score") if point else form.get("away_score_current")
    period = form.get("current_quarter") if form.get("current_quarter") is not None else trade.get("quarter")
    clock = format_clock(form.get("current_seconds_remaining")) if form else None
    live_state = normalize_live_state(query, point)
    if query_error and query is None:
        live_state = {
            "source": "AUSTIN",
            "availability": "UNAVAILABLE" if "before entry" in query_error else "UNAVAILABLE",
            "live_feed": "UNAVAILABLE",
            "data_mode": "HISTORICAL_QUERY",
            "detail": query_error,
        }
    mapped = observation_from_austin(query if query_error is None else None)
    if query_error:
        mapped = {
            "observation_state": "UNAVAILABLE" if "unknown" in query_error.lower() else (
                "UNKNOWN" if "before entry" in query_error else "UNAVAILABLE"
            ),
            "insufficient_support": "INSUFFICIENT" in query_error.upper() or "before entry" in query_error,
            "reason": query_error,
        }
    observation_state = assert_observation_state(mapped["observation_state"])
    cond = (live_state or {}).get("conditional_ev") if isinstance(live_state, dict) else None
    change_block = (live_state or {}).get("state_change") if isinstance(live_state, dict) else None
    support = (live_state or {}).get("model_support") if isinstance(live_state, dict) else None

    evidence = _evidence_timeline(trade, entry_ts, as_of_dt, query, point, current_price)
    home_team = trade.get("home_team") or ""
    away_team = trade.get("away_team") or ""
    position = {
        "position_id": wanted,
        "trade_id": wanted,
        "game_id": trade.get("game_id"),
        "market_id": trade.get("event_id"),
        "ticker": trade.get("ticker"),
        "sport": "NBA",
        "side": trade.get("entry_side"),
        "team": trade.get("team"),
        "opponent": trade.get("opponent"),
        "home_team": home_team,
        "away_team": away_team,
        "game": f"{away_team} @ {home_team}".strip(" @"),
        "position_label": f"{trade.get('team') or ''} YES".strip(),
        "entry_price_cents": entry_price,
        "entry_timestamp": iso(entry_ts) or trade.get("entry_timestamp"),
        "quantity": 1,
        "current_price_cents": current_price,
        "current_timestamp": as_of_iso,
        "price_change_cents": change,
        "unrealized_pnl_cents": unrealized,
        "unrealized_pnl_basis": "CANDLE_PATH_NOT_FILL",
        "period": period,
        "clock": clock,
        "home_score": home,
        "away_score": away,
        "position_status": "HISTORICAL",
        "slice": trade.get("slice"),
        "quarter": trade.get("quarter"),
        "game_date": trade.get("game_date"),
        "dataset_split": trade.get("dataset_split"),
        "mode": mode,
        "live_feed": "UNAVAILABLE",
        "as_of": as_of_iso,
    }
    ev_blocks = {
        "choosin_texas_prior": {
            "title": "CHOOSIN TEXAS PRIOR",
            "label": "80→40 population EV",
            "definition": CT_EV_DEFINITION,
            "estimand": "CHOOSIN_TEXAS_POPULATION_EV",
            "ev_display": (trade_context or {}).get("historical_ev", {}).get("ev_display")
            if isinstance(trade_context, dict)
            else None,
            "ev_cents": (trade_context or {}).get("historical_ev", {}).get("ev_cents")
            if isinstance(trade_context, dict)
            else None,
            "note": "Historical trade prior. Not a before/after versus Austin.",
        },
        "austin_conditional": {
            "title": "AUSTIN CONDITIONAL",
            "label": "Conditional EV at as_of",
            "definition": AUSTIN_EV_DEFINITION,
            "estimand": "AUSTIN_CONDITIONAL_EV",
            "conditional_ev_cents": None if not isinstance(cond, dict) else cond.get("conditional_ev_cents"),
            "note": "Historical nearest-state estimate.",
        },
        "austin_state_change": {
            "title": "AUSTIN STATE CHANGE",
            "label": "Δ conditional EV",
            "estimand": "AUSTIN_CONDITIONAL_EV_CHANGE",
            "ev_at_entry": None if not isinstance(change_block, dict) else change_block.get("ev_at_entry"),
            "ev_now": None if not isinstance(change_block, dict) else change_block.get("ev_now"),
            "ev_change": None if not isinstance(change_block, dict) else change_block.get("ev_change"),
            "note": "The only source-backed dynamic EV change. Not CT population EV.",
        },
    }
    chart_path = [
        {
            "t": row.get("t"),
            "price_cents": row.get("price_cents"),
            "home_score": row.get("home_score"),
            "away_score": row.get("away_score"),
        }
        for row in path
    ]
    return _jsonable({
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "position_id": wanted,
        "as_of": as_of_iso,
        "generated_at": iso(generated),
        "product": PRODUCT,
        "live_execution": LIVE_EXECUTION,
        "submits": False,
        "live_feed": "UNAVAILABLE",
        "phase3_is_execution_policy": False,
        "position": position,
        "trade_context": trade_context,
        "live_state": live_state,
        "dynamic_risk": {
            "observation_state": observation_state,
            "insufficient_support": bool(mapped.get("insufficient_support")),
            "hold_reason_status": hold_reason_v1(),
            "dynamic_risk_class": DYNAMIC_RISK_CLASS_V1,
            "austin_conditional_ev": None if not isinstance(cond, dict) else cond.get("conditional_ev_cents"),
            "change_from_entry": None if not isinstance(change_block, dict) else change_block.get("ev_change"),
            "historical_support": None if not isinstance(support, dict) else support.get("support"),
            "reason": mapped.get("reason"),
            "unresolved": [
                "dynamic_risk_class",
                "pit_deterioration_state",
                "authorized_policy",
            ],
            "ev_blocks": ev_blocks,
            "note": (
                "DRE V1 has no risk classifier. Observation is Austin historical query. "
                "Hold reason is model observation only."
            ),
        },
        "intervention": intervention_stub(),
        "evidence_timeline": evidence,
        "future_state_legend": future_state_legend(),
        "chart": {
            "entry_cents": 80,
            "loss_barrier_cents": 40,
            "as_of": as_of_iso,
            "path": chart_path,
            "candle_path_not_fill": True,
        },
        "history": evidence,
        "freshness": {
            "choosin_texas": "STATIC",
            "austin": "HISTORICAL" if query else "UNAVAILABLE",
            "austin_inference_timestamp": None if not query else query.get("inference_timestamp"),
            "live_feed": "UNAVAILABLE",
            "as_of": as_of_iso,
        },
        "provenance": {
            "choosin_texas_source": None if not isinstance(trade_context, dict) else trade_context.get("source_object_id"),
            "choosin_texas_version": None if not isinstance(trade_context, dict) else trade_context.get("source_version"),
            "austin_source": "austin_historical_query",
            "austin_trade_id": wanted,
            "austin_model_version": None if not query else query.get("model_version"),
            "austin_dataset_version": None if not query else query.get("dataset_version"),
            "jump_source": "NOT_WIRED",
            "generated_at": iso(generated),
            "as_of": as_of_iso,
            "mode": mode,
        },
    })


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items() if not isinstance(item, Stamped)}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, datetime):
        return iso(value)
    if isinstance(value, Stamped):
        return None
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return _jsonable(item())
        except Exception:  # noqa: BLE001
            return str(value)
    return value


def _evidence_timeline(
    trade: dict[str, Any],
    entry_ts: datetime | None,
    as_of_dt: datetime,
    query: dict[str, Any] | None,
    point: dict[str, Any] | None,
    current_price: int | None,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    events.append(
        {
            "event": "ENTRY",
            "timestamp": iso(entry_ts) or trade.get("entry_timestamp"),
            "market_price_cents": trade.get("entry_price_cents"),
            "source": "AUSTIN_REPLAY",
            "note": "FIRST80 entry. Candle path ≠ fill.",
        }
    )
    change = None if not query else query.get("state_change")
    if isinstance(change, dict) and change.get("ev_at_entry") is not None:
        events.append(
            {
                "event": "ENTRY_QUERY",
                "timestamp": iso(entry_ts) or trade.get("entry_timestamp"),
                "market_price_cents": trade.get("entry_price_cents"),
                "austin_conditional_ev_cents": change.get("ev_at_entry"),
                "source": "AUSTIN_QUERY",
                "note": "Austin conditional EV at entry probe.",
            }
        )
    if query is not None:
        events.append(
            {
                "event": "AS_OF_QUERY",
                "timestamp": query.get("inference_timestamp") or iso(as_of_dt),
                "market_price_cents": current_price,
                "austin_conditional_ev_cents": ((query.get("conditional_ev") or {}) or {}).get("conditional_ev_cents")
                if isinstance(query.get("conditional_ev"), dict)
                else None,
                "source": "AUSTIN_QUERY",
                "note": "Austin historical query at as_of.",
            }
        )
    events.append(
        {
            "event": "CURRENT_AS_OF",
            "timestamp": iso(as_of_dt),
            "market_price_cents": current_price if current_price is not None else None if not point else point.get("price_cents"),
            "game_clock": None if not point else point.get("t"),
            "source": "DRE",
            "note": "Current at as_of. Not live.",
        }
    )
    return events
