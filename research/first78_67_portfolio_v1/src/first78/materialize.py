"""Turn scanned games into portfolio candidates under one named rule."""

from __future__ import annotations

from typing import Any

from first78.clocks import align, window_ok
from first78.select import select_game
from first78.timeutil import in_historical_entry_window, local_date


def _hold_clock(contract: dict[str, Any], cash_mode: str) -> tuple[int | None, int | None, str | None]:
    settlement = contract.get("settlement_time_ts")
    close = contract.get("close_time_ts")
    signal = int(contract["signal_ts"])
    if cash_mode == "close_time":
        clock = close
        label = "HYPOTHETICAL_CASH_AT_CLOSE_TIME"
    else:
        clock = settlement
        label = "HYPOTHETICAL_CASH_AT_SETTLEMENT_TIME"
    if clock is None or int(clock) < signal:
        return None, None, "CASH_CLOCK_BEFORE_SIGNAL_OR_MISSING"
    if cash_mode == "close_time" and settlement is not None and int(clock) < int(settlement):
        # Trading close is earlier than the settlement record. Still a named hypothesis.
        label = "HYPOTHETICAL_CASH_AT_CLOSE_TIME_BEFORE_SETTLEMENT_RECORD"
    exit_ts = int(clock)
    cash_ts = exit_ts + 86400 if cash_mode == "settlement_cash_plus_1d" else exit_ts
    return exit_ts, cash_ts, label


def candidate_from_contract(
    game: dict[str, Any],
    contract: dict[str, Any],
    *,
    cash_mode: str = "settlement",
    delay_one_bar: bool = False,
    use_next_bar_price: bool = False,
    force_hold: bool = False,
) -> dict[str, Any] | None:
    signal_ts = int(contract["signal_ts"])
    clock = contract.get("clock") or {}
    if delay_one_bar:
        nxt = contract.get("next_bar_ts")
        if nxt is None:
            return None
        signal_ts = int(nxt)
        clock = align(game["sport"], game["event_id"], signal_ts)
        if not window_ok(game["sport"], clock.get("bucket") or "") or not in_historical_entry_window(signal_ts):
            return None
    reason = "WIN_SETTLEMENT" if contract.get("result") == "yes" else "LOSS_SETTLEMENT"
    if contract.get("result") not in {"yes", "no"}:
        reason = "UNRESOLVED"
    if contract.get("stop_ts") is not None and not force_hold:
        reason = "STOP"
    row: dict[str, Any] = {
        "game_id": game["game_id"],
        "event_id": game["event_id"],
        "contract_id": contract["contract_id"],
        "sport": game["sport"],
        "slice": game["slice"],
        "matchup": game["matchup"],
        "first80_ticker": game["first80_ticker"],
        "signal_ts": signal_ts,
        "exit_reason": reason,
        "local_day": local_date(signal_ts).isoformat(),
        "observed_close_cents": contract.get("observed_close_cents"),
        "overshoot_cents": contract.get("overshoot_cents"),
        "stop_close_cents": contract.get("stop_close_cents"),
        "stop_gap_cents": contract.get("stop_gap_cents"),
        "spread_cents": contract.get("spread_cents"),
        "ambiguous_entry_bar": contract.get("ambiguous_entry_bar"),
        "clock_bucket": (clock or {}).get("bucket"),
        "clock_quality": (clock or {}).get("clock_quality"),
        "period": (clock or {}).get("period"),
        "period_remaining_s": (clock or {}).get("period_remaining_s"),
        "clock_source": (clock or {}).get("clock_source"),
        "seconds_are_modeled": (clock or {}).get("seconds_are_modeled"),
        "result": contract.get("result"),
        "settlement_value_e4": contract.get("settlement_value_e4"),
        "close_time_ts": contract.get("close_time_ts"),
        "settlement_time_ts": contract.get("settlement_time_ts"),
        "expiration_time_ts": contract.get("expiration_time_ts"),
        "team": contract.get("team"),
        "dataset_split": game.get("dataset_split"),
        "game_date": game.get("game_date"),
        "path": contract.get("path") or [],
        "next_bar_bid_cents": contract.get("next_bar_bid_cents"),
        "depth_available": contract.get("depth_available"),
    }
    if use_next_bar_price:
        price = contract.get("next_bar_bid_cents")
        if price is None or not (1 <= int(price) <= 99):
            return None
        row["entry_price_cents"] = int(price)
        row["evidence"] = "NEXT_BAR_PRICE_PROXY"
    else:
        row["evidence"] = "FIRST78_CLOSE_PROXY"
    if reason == "STOP":
        row["exit_ts"] = int(contract["stop_ts"])
        row["cash_ts"] = row["exit_ts"] + (86400 if cash_mode == "stop_cash_plus_1d" else 0)
        row["cash_label"] = "ASSUMED_STOP_SALE_CASH_AT_SIGNAL"
    elif reason in {"WIN_SETTLEMENT", "LOSS_SETTLEMENT"}:
        exit_ts, cash_ts, label = _hold_clock(contract, cash_mode)
        if exit_ts is None or cash_ts is None:
            row["exit_reason"] = "UNRESOLVED"
            row["exit_ts"] = signal_ts + 1
            row["cash_ts"] = signal_ts + 1
            row["cash_label"] = label
        else:
            if cash_mode == "stop_cash_plus_1d":
                row["exit_ts"] = exit_ts
                row["cash_ts"] = cash_ts
            else:
                row["exit_ts"] = exit_ts
                row["cash_ts"] = cash_ts
            row["cash_label"] = label
    else:
        row["exit_ts"] = signal_ts + 1
        row["cash_ts"] = signal_ts + 1
        row["cash_label"] = "UNRESOLVED"
    if int(row["exit_ts"]) < int(row["signal_ts"]) or int(row["cash_ts"]) < int(row["exit_ts"]):
        return None
    return row


def build_candidates(
    games: list[dict[str, Any]],
    rule: str,
    **kwargs: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    chosen_rows: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    for game in games:
        decision = select_game(game["contracts"], rule)
        base = {
            "game_id": game["game_id"],
            "event_id": game["event_id"],
            "sport": game["sport"],
            "slice": game["slice"],
            "matchup": game["matchup"],
            "first80_ticker": game["first80_ticker"],
            "rule": rule,
        }
        if decision["chosen"] is None:
            audit.append({**base, "status": "EXCLUDED", "reason": decision["rejection_reason"]})
            continue
        row = candidate_from_contract(game, decision["chosen"], **kwargs)
        if row is None:
            audit.append({**base, "status": "EXCLUDED", "reason": "DELAY_OR_PROXY_UNAVAILABLE"})
            continue
        row["selection_rule"] = rule
        if row["exit_reason"] == "UNRESOLVED":
            audit.append({**base, "status": "UNRESOLVED", "reason": row.get("cash_label")})
            continue
        chosen_rows.append(row)
        audit.append({**base, "status": "CANDIDATE", "reason": None, "contract_id": row["contract_id"]})
    return chosen_rows, audit
