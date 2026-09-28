"""Locks WIN% / YES% / N denominators. Does not edit first80.py or frozen tests."""

from __future__ import annotations

from datetime import datetime

from roller.base_terminal_efficiency.exits import classify_first_exit
from roller.base_terminal_efficiency.models import AMBIGUOUS, TIE_EXACT_TIMESTAMP, WIN
from roller.research_query.compiler import compile_draft
from roller.research_query.entry_engine import TouchEvent, TradableBar
from roller.research_query.execute import apply_te_population_scope, evaluate_ticker, _classify_exits
from roller.research_query.measurements import measure_rows
from roller.research_query.models import TouchOrdinal
from roller.results_math.analyze import analyze_result
from tests.test_research_query_engine import _snap_quarter


def _universe() -> dict:
    return {
        "sports": ["basketball"],
        "leagues": ["NBA"],
        "markets": ["kalshi"],
        "marketData": ["candles"],
    }


def _q_90_55_hold_yes():
    return compile_draft(
        {
            "universe": _universe(),
            "entryConditions": [
                {"id": "e1", "family": "first_touch", "priceCents": 80, "period": "Q3"}
            ],
            "exitConditions": [
                {"id": "p-win", "kind": "path", "family": "reach", "priceCents": 90, "outcome": "win"},
                {"id": "p-loss", "kind": "path", "family": "reach", "priceCents": 55, "outcome": "loss"},
                {"id": "h-win", "kind": "terminal", "family": "hold_expiration_win", "outcome": "win"},
            ],
        }
    ).question


def _candle(ts: str, bid: int, *, ticker: str = "T-A") -> dict:
    return {
        "available_at": ts,
        "yes_bid_close": bid,
        "yes_ask_close": bid + 400,
        "volume": 10,
        "ticker": ticker,
        "internal_game_id": "G1",
        "is_valid": True,
    }


def _tb(ts: str, bid: int) -> TradableBar:
    return TradableBar(
        ts=datetime.fromisoformat(ts.replace("Z", "+00:00")),
        bid=bid,
        ask=bid + 400,
        volume=10,
        ticker="T-A",
        game_id="G1",
        raw={},
    )


def _entry_event(ts: str = "2025-12-20T20:01:00Z") -> TouchEvent:
    return TouchEvent(
        ordinal=TouchOrdinal.FIRST_TOUCH,
        touch_index=1,
        price_e4=8000,
        bar=_tb(ts, 8000),
        snap={"status": "REAL", "slice": "Q3", "period": 3, "clock": "08:00", "period_remaining_s": 480},
        alignment="ALIGNED",
    )


def test_same_minute_90_and_55_is_tie_excluded_and_win_pct_uses_classified():
    q = _q_90_55_hold_yes()
    candles = [
        _candle("2025-12-20T20:00:00Z", 7900),
        _candle("2025-12-20T20:01:00Z", 8000),
        _candle("2025-12-20T20:02:10Z", 9000),
        _candle("2025-12-20T20:02:40Z", 5500),
    ]
    row, _ = evaluate_ticker(candles, q, snap_fn=_snap_quarter("Q3"))
    assert row is not None
    assert row["exit_outcome"] == "TIE_EXCLUDED"
    classified = [
        row,
        {
            "ticker": "T-WIN",
            "exit_outcome": "WIN_EXIT",
            "path_true": True,
            "win_exit": True,
            "loss_exit": False,
            "terminal_yes": True,
        },
        {
            "ticker": "T-LOSS",
            "exit_outcome": "LOSS_EXIT",
            "path_true": False,
            "win_exit": False,
            "loss_exit": True,
            "terminal_yes": False,
        },
    ]
    measured = measure_rows(classified)
    assert measured["n"] == 3
    assert measured["win_exit"] == 1
    assert measured["loss_exit"] == 1
    assert measured["exit_classified"] == 2
    assert measured["win_exit_rate"] == 0.5
    assert measured["win_exit_rate"] != 1 / 3


def test_path_loss_then_official_w_yes_stays_loss_exit():
    q = _q_90_55_hold_yes()
    candles = [
        _candle("2025-12-20T20:00:00Z", 7900),
        _candle("2025-12-20T20:01:00Z", 8000),
        _candle("2025-12-20T20:02:00Z", 5500),
        _candle("2025-12-20T20:03:00Z", 8200),
    ]
    row, _ = evaluate_ticker(
        candles,
        q,
        market={"expiration_result_yes": True},
        snap_fn=_snap_quarter("Q3"),
    )
    assert row is not None
    assert row["terminal_yes"] is True
    assert row["exit_outcome"] == "LOSS_EXIT"
    assert row["loss_exit"] is True
    assert row["win_exit"] is False


def test_te_leading_scope_population_n_is_n_scoped():
    rows = [
        {
            "te": {"point_differential": 8, "point_differential_abs_e0": 8},
            "exit_outcome": "WIN_EXIT",
            "path_true": True,
            "terminal_yes": True,
        },
        {
            "te": {"point_differential": 7, "point_differential_abs_e0": 7},
            "exit_outcome": "WIN_EXIT",
            "path_true": True,
            "terminal_yes": True,
        },
        {
            "te": {"point_differential": -3, "point_differential_abs_e0": 3},
            "exit_outcome": "LOSS_EXIT",
            "path_true": False,
            "terminal_yes": False,
        },
        {"te": {}, "exit_outcome": "LOSS_EXIT", "path_true": False, "terminal_yes": False},
    ]
    kept, scope = apply_te_population_scope(rows, {"scoreSide": "leading", "absDiff": "any"})
    assert scope["n_entry"] == 4
    assert scope["n_scoped"] == 2
    assert scope["n_scoped"] == len(kept)
    measured = measure_rows(kept)
    assert measured["n"] == scope["n_scoped"]
    assert measured["win_exit"] == 2
    assert measured["win_exit_rate"] == 1.0
    unscoped = measure_rows(rows)
    assert unscoped["n"] == 4
    assert unscoped["win_exit_rate"] == 0.5


def test_measure_rows_yes_rate_uses_terminal_available():
    rows = [
        {"path_true": True, "terminal_yes": True, "exit_outcome": "WIN_EXIT"},
        {"path_true": True, "terminal_yes": True, "exit_outcome": "WIN_EXIT"},
        {"path_true": True, "terminal_yes": True, "exit_outcome": "WIN_EXIT"},
        {"path_true": False, "terminal_yes": False, "exit_outcome": "LOSS_EXIT"},
        {"path_true": False, "terminal_yes": None, "exit_outcome": "LOSS_EXIT"},
        {"path_true": True, "terminal_yes": None, "exit_outcome": "WIN_EXIT"},
    ]
    measured = measure_rows(rows)
    assert measured["n"] == 6
    assert measured["terminal_yes"] == 3
    assert measured["terminal_available"] == 4
    assert measured["terminal_missing"] == 2
    assert measured["yes_rate"] == 3 / 4
    assert measured["yes_rate"] != 3 / 6


def test_analyze_result_denominator_is_classified_when_tie_excluded():
    rows = [
        {
            "ticker": "W",
            "entry_ts": "2025-12-20T20:01:00Z",
            "entry_close": 8000,
            "exit_close": 9000,
            "hyp_pnl_cents": 10,
            "exit_outcome": "WIN_EXIT",
            "path_true": True,
            "terminal_yes": True,
        },
        {
            "ticker": "L",
            "entry_ts": "2025-12-20T20:02:00Z",
            "entry_close": 8000,
            "exit_close": 5500,
            "hyp_pnl_cents": -25,
            "exit_outcome": "LOSS_EXIT",
            "path_true": False,
            "terminal_yes": False,
        },
        {
            "ticker": "TIE",
            "entry_ts": "2025-12-20T20:03:00Z",
            "entry_close": 8000,
            "exit_close": None,
            "exit_outcome": "TIE_EXCLUDED",
            "path_true": False,
            "terminal_yes": True,
        },
    ]
    metrics = measure_rows(rows)
    out = analyze_result(rows, metrics=metrics)
    empirical = out["empirical"]
    assert empirical["n"] == 3
    assert empirical["denominator"] == 2
    assert empirical["successes"] == 1
    assert empirical["failures"] == 1
    assert empirical["rate"]["p_hat"] == 0.5
    assert empirical["rate"]["denominator"] == 2


def test_te_exact_timestamp_ambiguous_vs_generic_minute_tie():
    q = _q_90_55_hold_yes()
    entry = _entry_event()
    after_same_minute = [_tb("2025-12-20T20:02:10Z", 9000), _tb("2025-12-20T20:02:40Z", 5500)]
    generic = _classify_exits(
        after_same_minute,
        entry,
        q,
        None,
        entry_elapsed=None,
        snap_fn=_snap_quarter("Q3"),
        sport="NBA",
    )
    te = classify_first_exit(entry.bar, after_same_minute, win_price_e4=9000, loss_price_e4=5500)
    assert generic["exit_outcome"] == "TIE_EXCLUDED"
    assert te["exit_outcome"] == WIN

    after_exact = [_tb("2025-12-20T20:02:10Z", 9000), _tb("2025-12-20T20:02:10Z", 5500)]
    generic_exact = _classify_exits(
        after_exact,
        entry,
        q,
        None,
        entry_elapsed=None,
        snap_fn=_snap_quarter("Q3"),
        sport="NBA",
    )
    te_exact = classify_first_exit(entry.bar, after_exact, win_price_e4=9000, loss_price_e4=5500)
    assert generic_exact["exit_outcome"] == "TIE_EXCLUDED"
    assert te_exact["exit_outcome"] == AMBIGUOUS
    assert te_exact["exclusion_reason"] == TIE_EXACT_TIMESTAMP
