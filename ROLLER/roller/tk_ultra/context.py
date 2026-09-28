"""TK Ultra historical state from Austin + Choosin. Independent of Ballhog compose."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from roller.austin.clock import format_clock
from roller.austin.errors import AustinError
from roller.dre.pit import DrePitError, Stamped, assert_all_not_after, iso, require_as_of, to_utc
from roller.tk_ultra.adapters import austin as austin_ad
from roller.tk_ultra.adapters.choosin import extract_benchmark, get_trade_context
from roller.tk_ultra.assessment import assess_binary, attach_sibling
from roller.tk_ultra.errors import TkUltraV0Error
from roller.tk_ultra.models import (
    AUSTIN_N,
    AUSTIN_UNIVERSE,
    CHOOSIN_N,
    CHOOSIN_UNIVERSE,
    LIST_SCHEMA,
    LIVE_EXECUTION,
    PRODUCT,
    STATE_SCHEMA,
    UNAVAILABLE,
    now_iso,
)


def _path_midpoint(path: list[dict[str, Any]]) -> str | None:
    usable = [
        row
        for row in path
        if isinstance(row, dict) and row.get("t") and str(row.get("label") or "PATH") != "SETTLEMENT"
    ]
    if not usable:
        return None
    stamp = to_utc(usable[len(usable) // 2].get("t"))
    return iso(stamp)


def default_as_of_for_trade(trade_id: str) -> str | None:
    wanted = str(trade_id or "").strip()
    if not wanted:
        return None
    try:
        replay = austin_ad.get_replay(wanted)
    except Exception:  # noqa: BLE001
        return None
    return _path_midpoint(list(replay.get("path") or []))


def list_positions() -> dict[str, Any]:
    observed = austin_ad.last_observed_by_trade()
    rows = []
    for trade in austin_ad.list_trades():
        tid = str(trade.get("trade_id") or "")
        row = austin_ad.list_row(trade, observed.get(tid))
        default_as_of = default_as_of_for_trade(tid)
        display = f"{row.get('game') or ''} · {row.get('ticker') or ''}".strip(" ·")
        rows.append(
            {
                **row,
                "display_name": display or tid,
                "default_as_of": default_as_of,
                "replay_available": default_as_of is not None,
            }
        )
    return {
        "schema": LIST_SCHEMA,
        "product": PRODUCT,
        "live_execution": LIVE_EXECUTION,
        "execution_enabled": False,
        "feed_mode": "HISTORICAL",
        "live_feed": "UNAVAILABLE",
        "austin_universe": AUSTIN_UNIVERSE,
        "austin_n": AUSTIN_N,
        "choosin_universe": CHOOSIN_UNIVERSE,
        "choosin_n": CHOOSIN_N,
        "n": len(rows),
        "positions": rows,
        "generated_at": now_iso(),
    }


def compose(
    trade_id: str,
    *,
    as_of: str | None = None,
    overlay: dict[str, Any] | None = None,
    include_sibling: bool = False,
) -> dict[str, Any]:
    wanted = str(trade_id or "").strip()
    trade = austin_ad.get_trade(wanted)
    if trade is None:
        raise TkUltraV0Error("UNKNOWN_POSITION", f"unknown trade_id {wanted}", 404)
    observed = austin_ad.last_observed_by_trade().get(wanted) or {}
    entry_ts = to_utc(trade.get("entry_timestamp"))
    if as_of:
        as_of_dt = require_as_of(as_of)
        mode = "REPLAY"
    else:
        last = to_utc(observed.get("last_observed_at"))
        as_of_dt = last or entry_ts or datetime.now(timezone.utc)
        mode = "HISTORICAL"
        if as_of_dt.tzinfo is None:
            as_of_dt = as_of_dt.replace(tzinfo=timezone.utc)
    as_of_iso = iso(as_of_dt)
    replay = austin_ad.replay_clipped(wanted, as_of_dt)
    path = list(replay.get("path") or [])
    query = None
    query_error = None
    try:
        query = austin_ad.query_at(trade, as_of_dt)
        stamp = query.get("stamp")
        if isinstance(stamp, Stamped):
            assert_all_not_after(as_of_dt, [stamp])
            query.pop("stamp", None)
        if query.get("source_timestamp"):
            q_ts = to_utc(query.get("source_timestamp"))
            if q_ts is not None:
                assert_all_not_after(
                    as_of_dt,
                    [Stamped("austin_query", query.get("status"), "austin", q_ts, "QUERY")],
                )
    except (AustinError, DrePitError) as exc:
        query_error = exc.message if hasattr(exc, "message") else str(exc)
        query = None
    austin_ctx = austin_ad.extract_context(query)
    if query_error:
        austin_ctx = {**austin_ctx, "availability": "UNAVAILABLE", "detail": query_error}
    choosin_raw = get_trade_context()
    choosin_ctx = extract_benchmark(choosin_raw)
    extra = overlay if isinstance(overlay, dict) else {}
    a_price = extra.get("a_ref_cents")
    if a_price is None:
        a_price = austin_ctx.get("market_price_cents")
        if a_price is None and path:
            a_price = path[-1].get("price_cents")
    a_ref_basis = str(extra.get("a_ref_basis") or austin_ctx.get("price_basis") or "AUSTIN_QUERY_PRICE")
    e_a = extra.get("a_entry_cents")
    if e_a is None:
        e_a = trade.get("entry_price_cents")
    s_a = extra.get("a_stop_cents")
    if s_a is None:
        s_a = choosin_ctx.get("loss_barrier_cents")
    body = {
        "a_entry_cents": e_a,
        "a_stop_cents": s_a,
        "a_ref_cents": a_price,
        "a_ref_basis": a_ref_basis,
        "b_observed_cents": extra.get("b_observed_cents"),
        "b_observed_basis": extra.get("b_observed_basis") or "MID",
        "a_anchor_cents": extra.get("a_anchor_cents"),
        "b_anchor_cents": extra.get("b_anchor_cents"),
        "a_bid_cents": extra.get("a_bid_cents"),
        "b_ask_cents": extra.get("b_ask_cents"),
        "q_a": extra.get("q_a"),
        "q_b": extra.get("q_b"),
        "b_avg_existing_cents": extra.get("b_avg_existing_cents"),
        "quantity_source": extra.get("quantity_source"),
        "requested_quantity": extra.get("requested_quantity"),
        "a_contract": extra.get("a_contract") or trade.get("ticker"),
        "b_contract": extra.get("b_contract"),
        "as_of": as_of_iso,
        "trade_id": wanted,
        "internal_game_id": extra.get("internal_game_id") or trade.get("ticker"),
        "event_id": extra.get("event_id") or trade.get("ticker"),
    }
    identity = {
        "trade_id": wanted,
        "internal_game_id": body["internal_game_id"],
        "event_id": body["event_id"],
        "a_contract": body["a_contract"],
        "b_contract": body["b_contract"] or UNAVAILABLE,
        "as_of": as_of_iso,
    }
    assessment = assess_binary(
        body,
        austin_ctx=austin_ctx,
        choosin_ctx=choosin_ctx,
        identity=identity,
        feed_mode=mode,
    )
    sibling = None
    if include_sibling:
        from roller.tk_ultra.adapters.ballhog import read_intent

        sibling = read_intent(wanted, as_of=as_of_iso)
        assessment = attach_sibling(assessment, sibling)
    else:
        assessment = attach_sibling(assessment, None)
        assessment["sibling_context"]["note"] = "Not requested on this compose. Call /ballhog-context."
    form = (query or {}).get("form") if isinstance((query or {}).get("form"), dict) else {}
    return {
        "schema": STATE_SCHEMA,
        "product": PRODUCT,
        "live_execution": LIVE_EXECUTION,
        "execution_enabled": False,
        "feed_mode": mode,
        "live_feed": "UNAVAILABLE",
        "as_of": as_of_iso,
        "default_as_of": default_as_of_for_trade(wanted),
        "generated_at": now_iso(),
        "position": {
            "position_id": wanted,
            "trade_id": wanted,
            "ticker": trade.get("ticker"),
            "side": trade.get("entry_side"),
            "team": trade.get("team"),
            "game": f"{trade.get('away_team') or ''} @ {trade.get('home_team') or ''}".strip(" @"),
            "entry_price_cents": trade.get("entry_price_cents"),
            "entry_timestamp": trade.get("entry_timestamp"),
            "period": form.get("current_quarter") or trade.get("quarter"),
            "clock": format_clock(form.get("current_seconds_remaining")) if form else None,
            "austin_query_price_cents": austin_ctx.get("market_price_cents"),
            "austin_query_price_basis": austin_ctx.get("price_basis"),
        },
        "austin": assessment["austin"],
        "choosin_texas": assessment["choosin_texas"],
        "assessment": assessment,
        "sibling_context": assessment.get("sibling_context"),
        "position_management": "NOT_IMPLEMENTED",
    }
