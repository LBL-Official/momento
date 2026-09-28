"""Northbound state for the 78/67 Ballhog desk."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from roller.austin.clock import format_clock
from roller.austin.errors import AustinError
from roller.austin_first78.store import load_json
from roller.austin_first78.paths import summary_path
from roller.ballhog.errors import BallhogError
from roller.ballhog.models import LIVE_EXECUTION, PRODUCT, RESEARCH_UNIT_QTY, STATE_SCHEMA
from roller.ballhog.policy import BallhogPolicy
from roller.ballhog.tk_ultra_contract import build_intent
from roller.ballhog_first78 import context as src
from roller.ballhog_first78.optimizer import decide
from roller.ballhog_first78.policy import load_policy
from roller.ballhog_first78.transitions import build_transitions
from roller.dre.pit import DrePitError, Stamped, assert_all_not_after, clip_path, iso, require_as_of, to_utc

AUSTIN_UNIVERSE = "choosin_nba_2q3q_first78_67"
CHOOSIN_UNIVERSE = "DERIVED_FOUR_FIRST78"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def austin_n() -> int | None:
    summary = load_json(summary_path()) or {}
    coverage = summary.get("coverage") if isinstance(summary.get("coverage"), dict) else {}
    value = coverage.get("n_trades")
    return None if value is None else int(value)


def choosin_n() -> int | None:
    prior = src.choosin_prior()
    value = prior.get("n")
    return None if value is None else int(value)


def parse_q_dir(raw: object, policy: BallhogPolicy) -> int | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, bool) or isinstance(raw, float):
        raise BallhogError("INVALID_QUANTITY", "q_dir must be a positive integer")
    if isinstance(raw, str):
        text = raw.strip()
        if not text.isdigit():
            raise BallhogError("INVALID_QUANTITY", "q_dir must be a positive integer")
        value = int(text)
    elif isinstance(raw, int):
        value = raw
    else:
        raise BallhogError("INVALID_QUANTITY", "q_dir must be a positive integer")
    if value < 1 or value > int(policy.max_q_dir):
        raise BallhogError("INVALID_QUANTITY", f"q_dir must be in 1..{policy.max_q_dir}")
    return value


def resolve_q_dir(requested: object, policy: BallhogPolicy) -> int:
    parsed = parse_q_dir(requested, policy)
    return int(policy.default_q_dir) if parsed is None else parsed


def list_row(trade: dict[str, Any], observed: dict[str, Any] | None) -> dict[str, Any]:
    last = observed or {}
    ticker = str(trade.get("ticker") or "")
    stamp = last.get("last_observed_at") or trade.get("entry_timestamp")
    return {
        "position_id": trade.get("trade_id"),
        "trade_id": trade.get("trade_id"),
        "ticker": ticker,
        "sport": "NBA",
        "game": ticker,
        "side": trade.get("entry_side"),
        "slice": trade.get("slice"),
        "quarter": trade.get("quarter"),
        "entry_price_cents": trade.get("entry_price_cents"),
        "entry_timestamp": trade.get("entry_timestamp"),
        "last_observed_price_cents": last.get("last_observed_price_cents"),
        "last_observed_at": last.get("last_observed_at"),
        "display_name": f"{ticker} · {trade.get('slice') or ''}".strip(" ·"),
        "default_as_of": stamp,
        "replay_available": stamp is not None,
    }


def list_positions() -> dict[str, Any]:
    observed = src.last_observed_by_trade()
    rows = [list_row(trade, observed.get(str(trade.get("trade_id")))) for trade in src.list_trades()]
    return {
        "schema": "ballhog.position_list.v1",
        "product": PRODUCT,
        "book": "FIRST78_67",
        "live_execution": LIVE_EXECUTION,
        "execution_enabled": False,
        "feed_mode": "HISTORICAL",
        "live_feed": "UNAVAILABLE",
        "austin_universe": AUSTIN_UNIVERSE,
        "austin_n": austin_n(),
        "choosin_universe": CHOOSIN_UNIVERSE,
        "choosin_n": choosin_n(),
        "research_unit_qty": RESEARCH_UNIT_QTY,
        "default_as_of_rule": "austin_last_snapshot_or_entry",
        "n": len(rows),
        "positions": rows,
        "generated_at": _now_iso(),
    }


def replay_clipped(trade_id: str, as_of) -> dict[str, Any]:
    body = src.replay(trade_id)
    path = []
    for row in body.get("path") or []:
        if isinstance(row, dict):
            path.append(row)
    body["path"] = clip_path(as_of, path, time_key="t")
    return body


def compose(
    trade_id: str,
    *,
    as_of: str | None = None,
    q_dir: object | None = None,
    policy: BallhogPolicy | None = None,
) -> dict[str, Any]:
    policy = policy or load_policy()
    wanted = str(trade_id or "").strip()
    trade = src.get_trade(wanted)
    if trade is None:
        raise BallhogError("UNKNOWN_POSITION", f"unknown trade_id {wanted}", 404)
    n = resolve_q_dir(q_dir, policy)
    observed = src.last_observed_by_trade().get(wanted) or {}
    if as_of:
        as_of_dt = require_as_of(as_of)
        mode = "REPLAY"
    else:
        as_of_dt = to_utc(observed.get("last_observed_at")) or to_utc(trade.get("entry_timestamp"))
        mode = "HISTORICAL"
        if as_of_dt is None:
            raise BallhogError("SOURCE_UNAVAILABLE", "no as_of on this Austin 78/67 trade")
    as_of_iso = iso(as_of_dt)
    replay = replay_clipped(wanted, as_of_dt)
    path = list(replay.get("path") or [])
    query = None
    query_error = None
    try:
        query = src.query_at(trade, as_of_dt)
    except (AustinError, DrePitError) as exc:
        query_error = exc.message if hasattr(exc, "message") else str(exc)
    if query is not None and query.get("source_timestamp"):
        q_ts = to_utc(query.get("source_timestamp"))
        if q_ts is not None:
            assert_all_not_after(as_of_dt, [Stamped("austin_query", query.get("status"), "austin", q_ts, "QUERY")])
    choosin = src.choosin_prior()
    alpha = src.extract_alpha(query)
    if query_error:
        alpha = {**alpha, "availability": "UNAVAILABLE", "detail": query_error}
    form = (query or {}).get("form") if isinstance((query or {}).get("form"), dict) else {}
    point = path[-1] if path else {}
    decision = decide(q_dir=n, alpha=alpha, policy=policy, research_unit_qty=policy.research_unit_qty)
    transitions = build_transitions(alpha)
    intent = build_intent(
        trade_id=wanted,
        as_of=as_of_iso,
        decision=decision,
        austin_universe=AUSTIN_UNIVERSE,
        choosin_universe=CHOOSIN_UNIVERSE,
    )
    return {
        "schema": STATE_SCHEMA,
        "product": PRODUCT,
        "book": "FIRST78_67",
        "live_execution": LIVE_EXECUTION,
        "execution_enabled": False,
        "feed_mode": mode,
        "live_feed": "UNAVAILABLE",
        "as_of": as_of_iso,
        "default_as_of": observed.get("last_observed_at") or trade.get("entry_timestamp"),
        "replay_available": True,
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
            "display_name": f"{trade.get('ticker') or ''} · {trade.get('slice') or ''}".strip(" ·"),
            "entry_price_cents": trade.get("entry_price_cents"),
            "entry_timestamp": trade.get("entry_timestamp"),
            "period": form.get("current_quarter") or trade.get("quarter"),
            "clock": format_clock(form.get("current_seconds_remaining")) if form else None,
            "current_price_cents": point.get("price_cents") or form.get("current_price_cents"),
            "q_dir": n,
        },
        "austin": {
            "universe": AUSTIN_UNIVERSE,
            "n": austin_n(),
            "dataset_version": alpha.get("dataset_version") or AUSTIN_UNIVERSE,
            "model_version": alpha.get("model_version"),
            "availability": alpha.get("availability"),
            "a_t": alpha.get("a_t"),
            "a_l": alpha.get("a_l"),
            "alpha_ci": decision.get("alpha_ci"),
            "support": alpha.get("support"),
            "effective_sample_size": alpha.get("effective_sample_size"),
            "alpha_delta_from_entry": alpha.get("alpha_delta_from_entry"),
            "weighted_t67_rate": alpha.get("weighted_t67_rate"),
            "weighted_survival_rate": alpha.get("weighted_survival_rate"),
            "query_status": alpha.get("query_status"),
            "detail": alpha.get("detail") or query_error,
            "note": "Austin owns a_t on the 78/67 fit. The neighbor stop rate is T67_RISK_PROXY.",
        },
        "choosin_texas": {
            "universe": CHOOSIN_UNIVERSE,
            "n": choosin.get("n"),
            "availability": choosin.get("availability"),
            "pit_kind": "STATIC",
            "historical_ev": choosin.get("historical_ev"),
            "historical_survival_rate": choosin.get("historical_survival_rate"),
            "baseline_path_profile": choosin.get("baseline_path_profile"),
            "entry_cents": 78,
            "stop_cents": 67,
            "gain_cents": 22,
            "note": "Official 78/67 prior. Qualified N is not the Austin training N.",
        },
        "current_hedge_price": "UNAVAILABLE",
        "decision": decision,
        "transitions": transitions,
        "intent": intent,
    }
