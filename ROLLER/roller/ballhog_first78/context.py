"""Austin 78/67 query and the derived-four static prior. persist is false."""

from __future__ import annotations

from typing import Any

from roller.austin.clock import parse_utc
from roller.austin_first78.api import handle_health as austin_health
from roller.austin_first78.api import handle_replay
from roller.austin_first78.reconstruct import build_historical_query_state
from roller.austin_first78.store import load_snapshots, load_trades_frame
from roller.choosin_texas.first78.artifact import load_derived
from roller.choosin_texas.first78.desk import present_derived
from roller.dre.pit import iso


def austin_counts() -> dict[str, Any]:
    health = austin_health()
    return {
        "universe": "choosin_nba_2q3q_first78_67",
        "model_version": health.get("model_version"),
        "n": None,
        "health": health,
    }


def list_trades() -> list[dict[str, Any]]:
    frame = load_trades_frame()
    return frame.to_dict("records")


def get_trade(trade_id: str) -> dict[str, Any] | None:
    wanted = str(trade_id or "").strip()
    for row in list_trades():
        if str(row.get("trade_id")) == wanted:
            return row
    return None


def last_observed_by_trade() -> dict[str, dict[str, Any]]:
    snaps = load_snapshots()
    if snaps.empty or "trade_id" not in snaps.columns:
        return {}
    ordered = snaps.sort_values("available_at")
    last = ordered.groupby("trade_id", as_index=False).tail(1)
    out: dict[str, dict[str, Any]] = {}
    for rec in last.itertuples(index=False):
        tid = str(getattr(rec, "trade_id", "") or "")
        stamp = parse_utc(getattr(rec, "available_at", None))
        price = getattr(rec, "current_price_cents", None)
        out[tid] = {
            "last_observed_price_cents": None if price is None else int(round(float(price))),
            "last_observed_at": iso(stamp),
            "source": "austin_first78_snapshots",
        }
    return out


def query_at(trade: dict[str, Any], as_of) -> dict[str, Any]:
    from roller.austin_first78.api import _run_query
    from roller.austin_first78.query import form_fields

    when = as_of if hasattr(as_of, "isoformat") else parse_utc(as_of)
    recon = build_historical_query_state(
        game_id=str(trade.get("ticker") or ""),
        side=str(trade.get("entry_side") or "home"),
        timestamp_utc=iso(when) if when is not None else str(as_of),
        query_mode="POST_78",
    )
    result = _run_query(recon["raw"])
    result["form"] = form_fields(recon["raw"])
    result["entry_source"] = recon.get("entry_source")
    result["model_version"] = result.get("model_version")
    result["source_timestamp"] = iso(parse_utc(getattr(recon["raw"], "availability_timestamp", None)) or when)
    return result


def extract_alpha(query: dict[str, Any] | None) -> dict[str, Any]:
    if not query:
        return {"availability": "UNAVAILABLE", "a_t": None, "a_l": None, "weighted_t67_rate": None}
    cond = query.get("conditional_ev") if isinstance(query.get("conditional_ev"), dict) else {}
    support = query.get("support") if isinstance(query.get("support"), dict) else {}
    match = query.get("match") if isinstance(query.get("match"), dict) else {}
    change = query.get("state_change") if isinstance(query.get("state_change"), dict) else {}
    a_t = cond.get("conditional_ev_cents")
    a_l = cond.get("ci_lower_cents")
    status = str(query.get("status") or "")
    availability = "OBSERVED" if a_t is not None and status in {"OBSERVED", "QUERY_PARTIAL"} else "UNAVAILABLE"
    return {
        "availability": availability,
        "a_t": None if a_t is None else float(a_t),
        "a_l": None if a_l is None else float(a_l),
        "ci_upper": cond.get("ci_upper_cents"),
        "ci_level": cond.get("ci_level"),
        "ci_method": cond.get("method"),
        "support": support.get("support") or match.get("support"),
        "effective_sample_size": support.get("effective_sample_size") or match.get("effective_sample_size"),
        "k": support.get("k") or match.get("k"),
        "weighted_t67_rate": match.get("weighted_T40_rate"),
        "weighted_survival_rate": match.get("weighted_survival_rate"),
        "alpha_delta_from_entry": change.get("ev_change"),
        "dataset_version": query.get("dataset_version"),
        "model_version": query.get("model_version"),
        "query_status": query.get("status"),
    }


def choosin_prior() -> dict[str, Any]:
    body = load_derived()
    if body.get("status") != "OBSERVED":
        return {
            "availability": "UNAVAILABLE",
            "universe": "DERIVED_FOUR_FIRST78",
            "n": None,
            "pit_kind": "STATIC",
            "detail": body.get("message"),
        }
    desk = present_derived(body)
    universe = desk["universe"]
    trade = universe["trade"]
    n = int(universe["n"])
    survive = trade.get("S_display")
    return {
        "availability": "STATIC",
        "source": "CHOOSIN_TEXAS",
        "universe": "DERIVED_FOUR_FIRST78",
        "population_id": "DERIVED_FOUR_FIRST78",
        "n": n,
        "membership_n": desk.get("membership_n"),
        "pit_kind": "STATIC",
        "historical_ev": trade.get("ev_display") or trade.get("ev_per_trade_display"),
        "historical_survival_rate": survive,
        "entry_cents": 78,
        "stop_cents": 67,
        "gain_cents": 22,
        "baseline_path_profile": {"key": trade.get("key"), "S": survive, "n": n},
        "per_ticker_path_economics": "UNAVAILABLE",
        "note": "Official 78/67 prior on the derived four. Qualified N is not the Austin training N.",
    }


def replay(trade_id: str) -> dict[str, Any]:
    return handle_replay(trade_id)
