"""Northbound BallhogState from Austin HISTORICAL query + Choosin STATIC prior."""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from roller.austin.bars_join import load_paths, parse_entry, split_post
from roller.austin.clock import format_clock
from roller.austin.errors import AustinError
from roller.ballhog.adapters import austin as austin_ad
from roller.ballhog.adapters.choosin import get_trade_context
from roller.ballhog.errors import BallhogError
from roller.ballhog.models import (
    AUSTIN_N,
    AUSTIN_UNIVERSE,
    CHOOSIN_N,
    CHOOSIN_UNIVERSE,
    LIVE_EXECUTION,
    PRODUCT,
    RESEARCH_UNIT_QTY,
    STATE_SCHEMA,
)
from roller.ballhog.optimizer import decide
from roller.ballhog.policy import BallhogPolicy, load_policy
from roller.ballhog.tk_ultra_contract import build_intent
from roller.ballhog.transitions import build_transitions
from roller.dre.pit import DrePitError, Stamped, assert_all_not_after, iso, require_as_of, to_utc


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_q_dir(raw: object, policy: BallhogPolicy) -> int | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, bool):
        raise BallhogError("INVALID_QUANTITY", "q_dir must be a positive integer")
    if isinstance(raw, float):
        raise BallhogError("INVALID_QUANTITY", "q_dir must be an integer; decimal input is rejected")
    if isinstance(raw, str):
        text = raw.strip()
        if not text or text[0] == "-" or not text.isdigit():
            raise BallhogError("INVALID_QUANTITY", "q_dir must be a positive integer")
        value = int(text)
    elif isinstance(raw, int):
        value = raw
    else:
        raise BallhogError("INVALID_QUANTITY", "q_dir must be a positive integer")
    if value < 1:
        raise BallhogError("INVALID_QUANTITY", "q_dir must be a positive integer")
    if value > int(policy.max_q_dir):
        raise BallhogError("INVALID_QUANTITY", f"q_dir must be <= {policy.max_q_dir}")
    return value


def resolve_q_dir(requested: object, policy: BallhogPolicy) -> int:
    parsed = parse_q_dir(requested, policy)
    if parsed is None:
        return int(policy.default_q_dir)
    return parsed


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


def _midpoint_from_times(times: list) -> str | None:
    if not times:
        return None
    stamp = to_utc(times[len(times) // 2])
    return iso(stamp)


@lru_cache(maxsize=1)
def default_as_of_index() -> dict[str, str | None]:
    """UX-only replay-path midpoint per trade. Not a second Austin evidence definition."""
    trades = austin_ad.list_trades()
    out: dict[str, str | None] = {str(row.get("trade_id") or ""): None for row in trades}
    try:
        packed = load_paths(trades)
    except Exception:  # noqa: BLE001 — missing replay is UNAVAILABLE, not $0
        return out
    favorite = packed.get("favorite") or {}
    for trade in trades:
        tid = str(trade.get("trade_id") or "")
        ticker = str(trade.get("ticker") or "")
        entry = parse_entry(trade)
        bars = favorite.get(ticker) or []
        times = []
        if entry is not None:
            times.append(entry)
            times.extend(row[0] for row in split_post(list(bars), entry))
        out[tid] = _midpoint_from_times(times)
    return out


def default_as_of_for_trade(trade_id: str) -> str | None:
    wanted = str(trade_id or "").strip()
    if not wanted:
        return None
    indexed = default_as_of_index().get(wanted)
    if indexed:
        return indexed
    try:
        replay = austin_ad.get_replay(wanted)
    except Exception:  # noqa: BLE001
        return None
    return _path_midpoint(list(replay.get("path") or []))


def _enrich_list_row(row: dict[str, Any]) -> dict[str, Any]:
    tid = str(row.get("trade_id") or row.get("position_id") or "")
    default_as_of = default_as_of_index().get(tid)
    display = f"{row.get('game') or ''} · {row.get('ticker') or ''}".strip(" ·")
    return {
        **row,
        "display_name": display or tid,
        "default_as_of": default_as_of,
        "replay_available": default_as_of is not None,
    }


def list_positions() -> dict[str, Any]:
    observed = austin_ad.last_observed_by_trade()
    rows = [
        _enrich_list_row(austin_ad.list_row(trade, observed.get(str(trade.get("trade_id")))))
        for trade in austin_ad.list_trades()
    ]
    return {
        "schema": "ballhog.position_list.v1",
        "product": PRODUCT,
        "live_execution": LIVE_EXECUTION,
        "execution_enabled": False,
        "feed_mode": "HISTORICAL",
        "live_feed": "UNAVAILABLE",
        "austin_universe": AUSTIN_UNIVERSE,
        "austin_n": AUSTIN_N,
        "choosin_universe": CHOOSIN_UNIVERSE,
        "choosin_n": CHOOSIN_N,
        "research_unit_qty": RESEARCH_UNIT_QTY,
        "default_as_of_rule": "austin_replay_path_midpoint",
        "n": len(rows),
        "positions": rows,
        "generated_at": _now_iso(),
    }


def compose(
    trade_id: str,
    *,
    as_of: str | None = None,
    q_dir: object | None = None,
    policy: BallhogPolicy | None = None,
) -> dict[str, Any]:
    policy = policy or load_policy()
    wanted = str(trade_id or "").strip()
    trade = austin_ad.get_trade(wanted)
    if trade is None:
        raise BallhogError("UNKNOWN_POSITION", f"unknown trade_id {wanted}", 404)
    n = resolve_q_dir(q_dir, policy)
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
    for row in path:
        stamp = to_utc(row.get("t"))
        if stamp is not None:
            assert_all_not_after(
                as_of_dt,
                [Stamped("replay_path", row.get("price_cents"), "austin_replay", stamp, "PATH")],
            )
    choosin = get_trade_context()
    alpha = austin_ad.extract_alpha(query)
    if query_error:
        alpha = {**alpha, "availability": "UNAVAILABLE", "detail": query_error}
    live = austin_ad.normalize_live_state(query, path[-1] if path else None)
    form = (query or {}).get("form") if isinstance((query or {}).get("form"), dict) else {}
    decision = decide(
        q_dir=n,
        alpha=alpha,
        policy=policy,
        research_unit_qty=policy.research_unit_qty,
    )
    transitions = build_transitions(alpha)
    intent = build_intent(
        trade_id=wanted,
        as_of=as_of_iso,
        decision=decision,
        austin_universe=AUSTIN_UNIVERSE,
        choosin_universe=CHOOSIN_UNIVERSE,
    )
    default_as_of = default_as_of_for_trade(wanted)
    return {
        "schema": STATE_SCHEMA,
        "product": PRODUCT,
        "live_execution": LIVE_EXECUTION,
        "execution_enabled": False,
        "feed_mode": mode,
        "live_feed": "UNAVAILABLE",
        "as_of": as_of_iso,
        "default_as_of": default_as_of,
        "replay_available": default_as_of is not None,
        "generated_at": _now_iso(),
        "research_unit_qty": policy.research_unit_qty,
        "q_dir": n,
        "q_hedge": decision.get("q_hedge"),
        "rho": decision.get("rho"),
        "explanation": decision.get("explanation"),
        "position": {
            "position_id": wanted,
            "trade_id": wanted,
            "ticker": trade.get("ticker"),
            "side": trade.get("entry_side"),
            "team": trade.get("team"),
            "game": f"{trade.get('away_team') or ''} @ {trade.get('home_team') or ''}".strip(" @"),
            "display_name": f"{trade.get('away_team') or ''} @ {trade.get('home_team') or ''} · {trade.get('ticker') or ''}".strip(
                " ·"
            ),
            "entry_price_cents": trade.get("entry_price_cents"),
            "entry_timestamp": trade.get("entry_timestamp"),
            "period": form.get("current_quarter") or trade.get("quarter"),
            "clock": format_clock(form.get("current_seconds_remaining")) if form else None,
            "current_price_cents": live.get("market_price_cents"),
            "quantity_research_unit": policy.research_unit_qty,
            "q_dir": n,
        },
        "austin": {
            "universe": AUSTIN_UNIVERSE,
            "n": AUSTIN_N,
            "dataset_version": alpha.get("dataset_version"),
            "model_version": alpha.get("model_version"),
            "availability": alpha.get("availability"),
            "a_t": alpha.get("a_t"),
            "a_l": alpha.get("a_l"),
            "alpha_ci": decision.get("alpha_ci"),
            "support": alpha.get("support"),
            "effective_sample_size": alpha.get("effective_sample_size"),
            "alpha_delta_from_entry": alpha.get("alpha_delta_from_entry"),
            "weighted_t40_rate": alpha.get("weighted_t40_rate"),
            "weighted_survival_rate": alpha.get("weighted_survival_rate"),
            "query_status": alpha.get("query_status"),
            "detail": alpha.get("detail") or query_error,
            "note": "Austin owns a_t. Not Ballhog alpha.",
        },
        "choosin_texas": {
            "universe": CHOOSIN_UNIVERSE,
            "n": CHOOSIN_N,
            "availability": choosin.get("availability"),
            "pit_kind": "STATIC",
            "historical_ev": choosin.get("historical_ev"),
            "historical_survival_rate": choosin.get("historical_survival_rate"),
            "baseline_path_profile": choosin.get("baseline_path_profile"),
            "per_ticker_path_economics": choosin.get("per_ticker_path_economics"),
            "note": "Population prior N=936. Not Austin 604. Not as_of path EV.",
        },
        "current_hedge_price": "UNAVAILABLE",
        "decision": decision,
        "transitions": transitions,
        "intent": intent,
        "live_state": live,
    }
