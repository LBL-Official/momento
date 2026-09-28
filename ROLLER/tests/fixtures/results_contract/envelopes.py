"""Slim Results envelopes. Counts only — no query re-execution."""

from __future__ import annotations

from typing import Any


def _meas(name: str, true_n: int, avail: int) -> dict[str, Any]:
    return {
        "name": name,
        "value": true_n / avail if avail else None,
        "detail": {"count_true": true_n, "count_available": avail},
    }


def slim_envelope(
    *,
    sport: str,
    league: str,
    basis: str,
    n: int,
    path_true: int,
    path_false: int,
    win_exit: int,
    loss_exit: int,
    terminal_yes: int,
    terminal_no: int,
    terminal_missing: int,
    entry_e4: int = 8000,
    loss_e4: int = 4000,
    n_entry: int | None = None,
    market_data: str | None = None,
    trades: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    classified = win_exit + loss_exit
    settled = terminal_yes + terminal_no
    last_trade = "LAST_TRADE" in basis
    md = market_data or ("kalshi_1m_last_trade" if last_trade else "kalshi_1m_candles")
    return {
        "observation_basis": basis,
        "summary": {"population_n": n, "population_description": f"{league} {basis}"},
        "population": {"count": n, "trades": trades or []},
        "compile": {
            "observation_basis": basis,
            "question": {
                "universe": {"sports": [sport], "leagues": [league]},
                "entry_conditions": [{"ordinal": "FIRST_TOUCH", "price_e4": entry_e4}],
                "path_conditions": [{"op": "REACH", "price_e4": loss_e4, "outcome": "loss"}],
            },
        },
        "provenance": {
            "market_data": md,
            "market_data_type": basis,
            "price_basis": basis,
            "price_rule": "last_trade_close_cross" if last_trade else "tradable_close_cross",
        },
        "identity": {
            "reported_n": n,
            "n_entry_events": n_entry or n,
            "path_true": path_true,
            "path_false": path_false,
            "terminal_yes": terminal_yes,
            "terminal_no": terminal_no,
            "terminal_missing": terminal_missing,
        },
        "measurements": [
            _meas("path_rate", path_true, n),
            _meas("win_exit_rate", win_exit, classified) if classified else _meas("path_rate", path_true, n),
            _meas("loss_exit_rate", loss_exit, classified) if classified else _meas("path_rate", path_true, n),
            _meas("kalshi_yes_rate", terminal_yes, settled) if settled else _meas("kalshi_yes_rate", 0, 0),
        ],
        "analysis": {
            "observed_returns": {
                "status": "UNAVAILABLE" if last_trade else "OBSERVED",
                "reason": "LAST TRADE ≠ EXECUTABLE PRICE" if last_trade else "E[exit_close − entry_close]",
                "mean_cents": None if last_trade else -4.0,
                "n": None if last_trade else classified,
            }
        },
    }


def mlb_last_trade_1661() -> dict[str, Any]:
    return slim_envelope(
        sport="baseball",
        league="MLB",
        basis="LAST_TRADE_PRINT",
        n=1661,
        path_true=73,
        path_false=1588,
        win_exit=73,
        loss_exit=379,
        terminal_yes=79,
        terminal_no=16,
        terminal_missing=1566,
        entry_e4=7500,
        n_entry=1846,
    )


def mlb_last_trade_554() -> dict[str, Any]:
    return slim_envelope(
        sport="baseball",
        league="MLB",
        basis="LAST_TRADE_PRINT",
        n=554,
        path_true=59,
        path_false=495,
        win_exit=59,
        loss_exit=159,
        terminal_yes=65,
        terminal_no=19,
        terminal_missing=470,
        entry_e4=7500,
        n_entry=1503,
    )


def nba_8040_candle() -> dict[str, Any]:
    return slim_envelope(
        sport="basketball",
        league="NBA",
        basis="TRADABLE_YES_BID",
        n=12,
        path_true=4,
        path_false=8,
        win_exit=4,
        loss_exit=5,
        terminal_yes=6,
        terminal_no=2,
        terminal_missing=4,
        entry_e4=8000,
        loss_e4=4000,
    )


def ncaab_8040_candle() -> dict[str, Any]:
    env = nba_8040_candle()
    env["compile"]["question"]["universe"] = {"sports": ["basketball"], "leagues": ["NCAAB"]}
    env["summary"]["population_description"] = "NCAAB TRADABLE_YES_BID"
    env["identity"]["reported_n"] = 9
    env["summary"]["population_n"] = 9
    env["population"]["count"] = 9
    env["identity"].update(
        {
            "path_true": 3,
            "path_false": 6,
            "terminal_yes": 4,
            "terminal_no": 2,
            "terminal_missing": 3,
        }
    )
    env["measurements"] = [
        _meas("path_rate", 3, 9),
        _meas("win_exit_rate", 3, 7),
        _meas("loss_exit_rate", 4, 7),
        _meas("kalshi_yes_rate", 4, 6),
    ]
    return env


def wnba_8040_candle() -> dict[str, Any]:
    env = nba_8040_candle()
    env["compile"]["question"]["universe"] = {"sports": ["basketball"], "leagues": ["WNBA"]}
    env["summary"]["population_description"] = "WNBA TRADABLE_YES_BID"
    return env


def tennis_candle() -> dict[str, Any]:
    return slim_envelope(
        sport="tennis",
        league="ATP",
        basis="TRADABLE_YES_BID",
        n=8,
        path_true=2,
        path_false=6,
        win_exit=2,
        loss_exit=3,
        terminal_yes=3,
        terminal_no=1,
        terminal_missing=4,
        entry_e4=7500,
        loss_e4=4000,
    )


def tennis_last_trade() -> dict[str, Any]:
    return slim_envelope(
        sport="tennis",
        league="ATP",
        basis="LAST_TRADE_PRINT",
        n=8,
        path_true=2,
        path_false=6,
        win_exit=2,
        loss_exit=3,
        terminal_yes=3,
        terminal_no=1,
        terminal_missing=4,
        entry_e4=7500,
        loss_e4=4000,
    )
