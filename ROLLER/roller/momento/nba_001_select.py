"""Run the prespecified NBA 001 replay. Does not submit orders."""

from __future__ import annotations

import json
from bisect import bisect_right
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from roller.momento.nba_001_replay import (
    BOOTSTRAP_BLOCK,
    MARK_STALE_AFTER_SECONDS,
    Mark,
    block_bootstrap_lower,
    choose_candidate,
    claim_label,
    prepare_trade,
    replay_portfolio,
    week_grid,
    protected_hashes,
    mlb_tree_sha256,
)

SUMMARY_PATH = (
    Path(__file__).resolve().parents[3]
    / "research"
    / "vital"
    / "bots"
    / "nba-001"
    / "analysis"
    / "replay_summary.json"
)
MANIFEST_PATH = SUMMARY_PATH.parent / "SOURCE_MANIFEST.json"


def _manifest_matches() -> dict[str, Any]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    current = protected_hashes()
    mismatches = [
        rel for rel, digest in manifest["protected_sha256"].items() if current.get(rel) != digest
    ]
    tree_hash, tree_count = mlb_tree_sha256()
    tree_ok = tree_hash == manifest["mlb_tree"]["sha256"] and tree_count == manifest["mlb_tree"]["file_count"]
    return {
        "protected_mismatch": mismatches,
        "mlb_tree_match": tree_ok,
        "outcomes_accessed": False,
    }


def _mark_book(tickers: set[str]) -> dict[str, list[tuple[datetime, int]]]:
    from roller.nba_8040_reverse_features.bars import load_ticker_bars

    raw = load_ticker_bars(tickers)
    book: dict[str, list[tuple[datetime, int]]] = {}
    for ticker, rows in raw.items():
        series = []
        for stamp, close, _high, _low in rows:
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            series.append((stamp, int(round(close))))
        series.sort(key=lambda item: item[0])
        book[ticker] = series
    return book


def _lookup(book: dict[str, list[tuple[datetime, int]]]):
    def mark_at(ticker: str, when: datetime) -> Mark | None:
        series = book.get(ticker) or []
        if not series:
            return None
        stamps = [item[0] for item in series]
        index = bisect_right(stamps, when) - 1
        if index < 0:
            return None
        stamp, cents = series[index]
        stale = (when - stamp).total_seconds() > MARK_STALE_AFTER_SECONDS
        return Mark(cents, stamp, stale)

    return mark_at


def _first_close_at_or_below(
    book: dict[str, list[tuple[datetime, int]]],
    ticker: str,
    after: datetime,
    price: int,
) -> tuple[datetime, int] | None:
    for stamp, cents in book.get(ticker) or []:
        if stamp > after and cents <= price:
            return stamp, cents
    return None


def _apply_conservative_exit(
    trade: dict[str, Any],
    book: dict[str, list[tuple[datetime, int]]],
) -> dict[str, Any]:
    """Stop at the first later close at or below 40. The minimum is only a labeled proxy."""
    if trade.get("skip") or trade.get("exit_role") != "taker":
        return trade
    found = _first_close_at_or_below(book, trade["ticker"], trade["entry_ts"], 40)
    if found is None:
        trade["exit_basis"] = "POST_ENTRY_MIN_NOT_FIRST_CLOSE"
        return trade
    stamp, cents = found
    trade["exit_price_cents"] = cents
    trade["exit_ts"] = stamp
    trade["exit_basis"] = "FIRST_CLOSE_AT_OR_BELOW_40"
    return trade


def _hedge_diagnostic(rows: list[dict[str, Any]], book: dict[str, list[tuple[datetime, int]]]) -> dict[str, Any]:
    triggered = 0
    fallback = 0
    held = 0
    for row in rows:
        trade = prepare_trade(row, layer="theoretical")
        found = _first_close_at_or_below(book, trade["ticker"], trade["entry_ts"], 42)
        if found is None:
            continue
        triggered += 1
        stamp, cents = found
        if cents <= 40:
            fallback += 1
            continue
        later = _first_close_at_or_below(book, trade["ticker"], stamp, 40)
        if later is None:
            held += 1
        else:
            fallback += 1
    return {
        "fill_credited": False,
        "fill_status": "FILL_UNAVAILABLE",
        "triggers_close_at_or_below_42": triggered,
        "fallback_exits_at_later_close_at_or_below_40": fallback,
        "held_to_settlement_after_trigger": held,
        "ranking_input": False,
    }


def _bound(result: dict[str, Any], *, block: int) -> dict[str, Any]:
    if any(item is None for item in result["weekly_returns"]):
        return {"status": "UNAVAILABLE", "reason": "INCOMPLETE_WEEKLY_SERIES", "block": block}
    returns = [Decimal(item) for item in result["weekly_returns"]]
    return block_bootstrap_lower(returns, block=block)


def run() -> dict[str, Any]:
    from roller.nba_8040_reverse_features.instances import load_instances

    preservation = _manifest_matches()
    if preservation["protected_mismatch"] or not preservation["mlb_tree_match"]:
        raise SystemExit(f"protected hashes changed before ranking: {preservation}")
    rows = load_instances()
    tickers = {str(row["ticker"]) for row in rows}
    book = _mark_book(tickers)
    mark_at = _lookup(book)
    prepared = {
        "conservative": [
            _apply_conservative_exit(prepare_trade(row, layer="conservative"), book) for row in rows
        ],
        "theoretical": [prepare_trade(row, layer="theoretical") for row in rows],
    }
    stamps = [trade["entry_ts"] for trade in prepared["theoretical"]]
    stamps.extend(trade["exit_ts"] for trade in prepared["theoretical"] if trade.get("exit_ts"))
    weeks = week_grid(min(stamps), max(stamps))
    layers: dict[str, Any] = {}
    for layer, trades in prepared.items():
        layers[layer] = {}
        for name, subset in (
            ("union", trades),
            ("q2", [trade for trade in trades if trade["slice"] == "Q2"]),
            ("q3", [trade for trade in trades if trade["slice"] == "Q3"]),
        ):
            result = replay_portfolio(subset, mark_at=mark_at, week_starts=weeks, maker_multiplier=1)
            primary = _bound(result, block=BOOTSTRAP_BLOCK)
            observed = [Decimal(item) for item in result["weekly_returns"] if item is not None]
            layers[layer][name] = {
                "weeks_at_or_above_1_5pct": sum(1 for item in observed if item >= Decimal("0.015")),
                "weeks_observed": len(observed),
                "exit_basis": {
                    basis: sum(1 for trade in subset if trade.get("exit_basis") == basis and not trade.get("skip"))
                    for basis in ("FIRST_CLOSE_AT_OR_BELOW_40", "POST_ENTRY_MIN_NOT_FIRST_CLOSE", "THEORETICAL_EXIT_AT_40", "CANDLE_SETTLEMENT")
                },
                "entries": result["entries"],
                "skip_reasons": result["skip_reasons"],
                "phase_realized_cents": result["phase_realized_cents"],
                "ending_cash_cents": result["ending_cash_cents"],
                "open_positions": result["open_positions"],
                "fill_observed": result["fill_observed"],
                "basis": result["basis"],
                "weeks": len(result["weekly_returns"]),
                "missing_weeks": sum(1 for item in result["weekly_returns"] if item is None),
                "bootstrap_4": primary,
                "bootstrap_1": _bound(result, block=1),
                "bootstrap_8": _bound(result, block=8),
            }
    conservative = layers["conservative"]
    bounds = {
        name: None
        if conservative[name]["bootstrap_4"].get("status") != "OK"
        else Decimal(conservative[name]["bootstrap_4"]["lower"])
        for name in ("union", "q2", "q3")
    }
    decision = choose_candidate(bounds, fill_executable=False)
    chosen_name = decision.get("candidate") or "union"
    chosen_boot = conservative[chosen_name]["bootstrap_4"]
    union_boot = conservative["union"]["bootstrap_4"]
    if chosen_boot.get("status") != "OK":
        decision["mean_claim"] = "UNAVAILABLE"
        decision["status"] = "NO_SELECTION"
        decision["reason"] = chosen_boot.get("reason", "UNION_BOUND_UNAVAILABLE")
    else:
        decision["mean_claim"] = claim_label(Decimal(chosen_boot["point"]), Decimal(chosen_boot["lower"]))
        decision["point"] = chosen_boot["point"]
        decision["union_point"] = union_boot.get("point")
        decision["union_lower"] = union_boot.get("lower")
    summary = {
        "submits": False,
        "live_execution": False,
        "fill_executable": False,
        "fill_status": "FILL_UNAVAILABLE",
        "maker_multiplier_selection": 1,
        "maker_multiplier_source": "UNAVAILABLE",
        "preservation": preservation,
        "decision": decision,
        "layers": layers,
        "hedge": _hedge_diagnostic(rows, book),
        "n": len(rows),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    payload = run()
    decision = payload["decision"]
    print(json.dumps({"decision": decision, "union": payload["layers"]["conservative"]["union"]["bootstrap_4"]}, indent=2))
