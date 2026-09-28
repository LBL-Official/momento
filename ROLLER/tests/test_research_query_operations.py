"""Phase 1 detectors + WIN/LOSS. Candle close only. Does not edit FIRST80."""

from __future__ import annotations

from datetime import datetime, timezone

from roller.research_query.compiler import compile_draft, compile_question, reference_match
from roller.research_query.entry_engine import observe_entry, tradable_sequence
from roller.research_query.execute import execute_compiled
from roller.research_query.hashing import question_hash
from roller.research_query.models import (
    EntryCondition,
    EntryOp,
    ExitOutcome,
    PathCondition,
    PathOp,
    ResearchQuestion,
    ResearchStatus,
    TerminalOutcome,
    TouchOrdinal,
    Universe,
)
from roller.research_query.operations import (
    RecoveryInvalid,
    first_above,
    first_below,
    first_bounce,
    first_break,
    first_cross,
    first_maximum_touch,
    first_minimum_touch,
    first_recovery,
    first_reversion,
    path_bounce,
    path_never_reach,
    path_revert,
)
from roller.research_query.path_engine import first_later
from tests.test_research_query_engine import _q, _series, _snap_quarter

UTC = timezone.utc


def _bars(bids: list[int]):
    return tradable_sequence(_series(bids))[0]


def test_cross_break_equality():
    bars = _bars([7900, 8000, 8100])
    assert first_cross(bars, 8000).bid == 8000
    assert first_break(bars, 8000) is None
    assert first_break(_bars([7900, 8100]), 8000).bid == 8100
    assert first_cross(_bars([8000, 8000]), 8000) is None


def test_reversion_ordered():
    assert first_reversion(_bars([7900, 8100, 8200, 7900]), 8000) is not None
    assert first_reversion(_bars([7900, 8100, 8000]), 8000) is None


def test_bounce_locked_examples():
    assert first_bounce(_bars([7900, 8000, 7900]), 8000) is not None
    assert first_bounce(_bars([8100, 8000, 8100]), 8000) is not None
    assert first_bounce(_bars([7900, 8100]), 8000) is None
    assert first_bounce(_bars([7900, 8000, 8100]), 8000) is None
    up = first_bounce(_bars([7900, 8000, 7900]), 8000, "up")
    assert up is not None and up.bid == 7900
    assert first_bounce(_bars([7900, 8000, 7900]), 8000, "down") is None


def test_path_bounce_locked_examples():
    yes = _bars([7900, 8000, 7900])
    assert path_bounce(yes[1:], 8000, entry_close=yes[0].bid) is not None
    no_hold = _bars([7900, 8000, 8100])
    assert path_bounce(no_hold[1:], 8000, entry_close=no_hold[0].bid) is None
    missing_next = _bars([7900, 8000])
    assert path_bounce(missing_next[1:], 8000, entry_close=missing_next[0].bid) is None


def test_path_revert_incomplete_79_81_80():
    incomplete = _bars([7900, 8100, 8000])
    assert path_revert(incomplete[1:], 8000, entry_close=incomplete[0].bid) is None
    complete = _bars([7900, 8100, 8200, 7900])
    assert path_revert(complete[1:], 8000, entry_close=complete[0].bid) is not None


def test_path_never_reach_holds_when_p_absent():
    absent = _bars([7900, 8000, 8100, 8200])
    hit = path_never_reach(absent[1:], 9000, entry_close=absent[0].bid)
    assert hit is absent[-1]
    crossed = _bars([7900, 8000, 9100])
    assert path_never_reach(crossed[1:], 9000, entry_close=crossed[0].bid) is None


def test_path_engine_dispatches_new_ops():
    bounce_yes = _bars([7900, 8000, 7900])
    assert first_later(bounce_yes[1:], entry_close=bounce_yes[0].bid, op=PathOp.BOUNCE, price_e4=8000)
    assert first_later(_bars([7900, 8000, 8100])[1:], entry_close=7900, op=PathOp.BOUNCE, price_e4=8000) is None
    assert first_later(_bars([7900, 8100, 8000])[1:], entry_close=7900, op=PathOp.REVERT, price_e4=8000) is None
    assert first_later(_bars([7900, 8000, 8100])[1:], entry_close=7900, op=PathOp.NEVER_REACH, price_e4=9000)


def test_bounce_skips_untradable_next():
    candles = _series([7900, 8000, 7900])
    candles[2]["is_valid"] = False
    candles.append(
        {
            "available_at": "2025-12-20T20:03:00Z",
            "yes_bid_close": 7900,
            "yes_ask_close": 8300,
            "volume": 10,
            "ticker": "T-A",
            "internal_game_id": "G1",
            "is_valid": True,
        }
    )
    bars, _ = tradable_sequence(candles)
    hit = first_bounce(bars, 8000)
    assert hit is not None
    assert hit.ts.minute == 3


def test_recovery_sides_and_invalid():
    assert first_recovery(_bars([8500, 7900, 8200]), 8000).bid == 8200
    assert first_recovery(_bars([7500, 8200, 7900]), 8000).bid == 7900
    assert first_recovery(_bars([8500, 8200, 8100]), 8000) is None
    try:
        first_recovery(_bars([8000, 8100, 7900]), 8000)
        raise AssertionError("expected RecoveryInvalid")
    except RecoveryInvalid:
        pass
    assert first_recovery(_bars([8000, 8100, 7900]), 8000, direction="up") is not None


def test_above_below_extrema():
    bars = _bars([8000, 7900, 8100, 8200])
    assert first_above(bars, 8000).bid == 8100
    assert first_below(bars, 8000).bid == 7900
    assert first_maximum_touch(bars, 8200).bid == 8200
    assert first_minimum_touch(bars, 7900).bid == 7900
    assert first_maximum_touch(_bars([7000, 7100]), 8000) is None


def test_period_filter_after_game_event(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    cond = EntryCondition(
        id="e1",
        ordinal=TouchOrdinal.FIRST_TOUCH,
        price_e4=8000,
        period="Q3",
        operation=EntryOp.CROSS,
    )
    ev, diag = observe_entry(
        _series([7900, 8100]),
        cond,
        snap_fn=_snap_quarter("Q2"),
    )
    assert ev is None
    assert diag["reject_reason"] == "period_filter"


def test_standalone_recovery_requires_direction(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    draft = {
        "universe": {
            "sports": ["basketball"],
            "leagues": ["NBA"],
            "seasons": ["2025-26"],
            "markets": ["kalshi"],
            "marketData": ["candles"],
        },
        "entryConditions": [{"id": "e1", "family": "recovery", "priceCents": 80}],
        "exitConditions": [{"id": "t", "kind": "terminal", "family": "both"}],
    }
    c = compile_draft(draft)
    assert c.status is ResearchStatus.OPERATION_REQUIRED
    assert "direction" in " ".join(c.reasons).lower()


def test_win_loss_price_gate(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    bad = {
        "universe": {
            "sports": ["basketball"],
            "leagues": ["NBA"],
            "seasons": ["2025-26"],
            "markets": ["kalshi"],
            "marketData": ["candles"],
        },
        "entryConditions": [{"id": "e1", "family": "first_touch", "priceCents": 80}],
        "exitConditions": [
            {"id": "p1", "kind": "path", "family": "reach", "priceCents": 40, "outcome": "win"},
        ],
    }
    c = compile_draft(bad)
    assert c.status is ResearchStatus.OPERATION_REQUIRED
    ok = dict(bad)
    ok["exitConditions"] = [
        {"id": "p1", "kind": "path", "family": "reach", "priceCents": 40, "outcome": "loss"},
    ]
    assert compile_draft(ok).status is ResearchStatus.READY


def test_tagged_win_loss_first_hit(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    q = ResearchQuestion(
        universe=Universe(
            sports=("basketball",),
            leagues=("NBA",),
            seasons=("2025-26",),
            markets=("kalshi",),
            market_data=("candles",),
        ),
        entry_conditions=(
            EntryCondition(id="e1", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=8000),
        ),
        path_conditions=(
            PathCondition(id="w", op=PathOp.REACH, price_e4=8500, outcome=ExitOutcome.WIN),
            PathCondition(id="l", op=PathOp.REACH, price_e4=7000, outcome=ExitOutcome.LOSS),
        ),
        terminal=TerminalOutcome.BOTH,
    )
    compiled = compile_question(q)
    out = execute_compiled(
        compiled,
        ticker_payloads={"T-A": _series([7900, 8000, 8500, 7000], ticker="T-A")},
        snap_fn=_snap_quarter("Q3"),
    )
    row = out["population"]["trades"][0]
    assert row["exit_outcome"] == "WIN_EXIT"
    assert row["win_exit"] is True


def test_tagged_draft_not_frozen(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    draft = {
        "universe": {
            "sports": ["basketball"],
            "leagues": ["NBA"],
            "seasons": ["2025-26"],
            "markets": ["kalshi"],
            "marketData": ["candles"],
        },
        "entryConditions": [{"id": "e1", "family": "first_touch", "priceCents": 80, "period": "Q3"}],
        "exitConditions": [
            {"id": "p1", "kind": "path", "family": "reach", "priceCents": 40, "outcome": "loss"},
            {"id": "t", "kind": "terminal", "family": "hold_expiration_win", "outcome": "win"},
        ],
    }
    c = compile_draft(draft)
    assert c.reference_match is None
    assert c.execution_path.value == "generic_query"


def test_untagged_path_true_preserved(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    q = _q(TouchOrdinal.FIRST_TOUCH, 8000)
    q = ResearchQuestion(
        universe=q.universe,
        entry_conditions=q.entry_conditions,
        path_conditions=(PathCondition(id="p", op=PathOp.REACH, price_e4=4000),),
        terminal=TerminalOutcome.BOTH,
    )
    out = execute_compiled(
        compile_question(q),
        ticker_payloads={"T-A": _series([7900, 8000, 4000])},
        snap_fn=_snap_quarter("Q3"),
    )
    assert out["population"]["trades"][0]["path_true"] is True
    assert out["population"]["trades"][0]["exit_outcome"] is None


def test_touch_hash_stable():
    a = _q(TouchOrdinal.FIRST_TOUCH, 8000, "Q3")
    b = ResearchQuestion(
        universe=a.universe,
        entry_conditions=a.entry_conditions,
        path_conditions=a.path_conditions,
        terminal=a.terminal,
    )
    assert question_hash(a) == question_hash(b)
    assert "operation" not in a.entry_conditions[0].to_dict()


def test_same_minute_tie_excluded():
    from roller.research_query.entry_engine import TouchEvent, TradableBar, same_minute_ties

    ts = datetime(2025, 12, 20, 20, 1, tzinfo=UTC)
    evs = []
    for ticker in ("T-A", "T-B"):
        bar = TradableBar(ts=ts, bid=8000, ask=8400, volume=10, ticker=ticker, game_id="G1", raw={})
        evs.append(
            TouchEvent(
                ordinal=TouchOrdinal.FIRST_TOUCH,
                touch_index=1,
                price_e4=8000,
                bar=bar,
                snap={"slice": "Q3", "status": "REAL"},
                alignment="aligned",
            )
        )
    kept, excluded = same_minute_ties(evs)
    assert kept == []
    assert excluded == 2


def test_reference_match_untouched_for_first80():
    q = ResearchQuestion(
        universe=Universe(
            sports=("basketball",),
            leagues=("NBA",),
            seasons=("2025-26",),
            markets=("kalshi",),
            market_data=("candles",),
        ),
        entry_conditions=(
            EntryCondition(id="e1", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=8000, period="Q3"),
        ),
        path_conditions=(PathCondition(id="p", op=PathOp.REACH, price_e4=4000),),
        terminal=TerminalOutcome.BOTH,
    )
    assert reference_match(q) == "FIRST80_Q3"


def _nba_universe():
    return {
        "sports": ["basketball"],
        "leagues": ["NBA"],
        "seasons": ["2025-26"],
        "markets": ["kalshi"],
        "marketData": ["candles"],
    }


def test_exit_path_families_compile_ready(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    for family, cents, outcome in (
        ("bounce", 90, "win"),
        ("revert", 90, "win"),
        ("maximum_move", 90, "win"),
        ("minimum_move", 40, "loss"),
        ("never_reach", 90, "win"),
    ):
        draft = {
            "universe": _nba_universe(),
            "entryConditions": [{"id": "e1", "family": "first_touch", "priceCents": 80}],
            "exitConditions": [
                {"id": "p1", "kind": "path", "family": family, "priceCents": cents, "outcome": outcome},
            ],
        }
        c = compile_draft(draft)
        assert c.status is ResearchStatus.READY, (family, c.status, c.reasons)
        assert c.question.path_conditions[0].op.value == family.upper()


def test_cross_draft_preserves_ast_operation(monkeypatch):
    """Invariant 1: draft Cross must compile to EntryOp.CROSS, never silent First Touch."""
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    draft = {
        "universe": _nba_universe(),
        "entryConditions": [{"id": "e1", "family": "cross", "priceCents": 60}],
        "exitConditions": [{"id": "p1", "kind": "path", "family": "reach", "priceCents": 90}],
    }
    c = compile_draft(draft)
    assert c.status is ResearchStatus.READY
    assert c.question.entry_conditions[0].resolved_operation() is EntryOp.CROSS
    assert c.question.entry_conditions[0].operation is EntryOp.CROSS


def test_operation_required_never_returns_population(monkeypatch):
    """Invariant 2: OPERATION_REQUIRED execute must not return N > 0."""
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    draft = {
        "universe": _nba_universe(),
        "entryConditions": [{"id": "e1", "family": "cross", "priceCents": 60}],
        "exitConditions": [
            {"id": "p1", "kind": "path", "family": "reach", "priceCents": 90},
            {"id": "h1", "kind": "horizon", "family": "horizon_game_win", "outcome": "win"},
        ],
    }
    c = compile_draft(draft)
    assert c.status is ResearchStatus.OPERATION_REQUIRED
    assert "horizon_game_win" in (c.unavailable or [])
    out = execute_compiled(
        c,
        ticker_payloads={"T-A": _series([5900, 6000, 9000])},
        snap_fn=_snap_quarter("Q3"),
    )
    assert out["execution_status"] == "OPERATION_REQUIRED"
    trades = (out.get("population") or {}).get("trades")
    assert trades in (None, [])
    assert out.get("population", {}).get("n") in (None, 0) or "trades" not in (out.get("population") or {})


def test_incomplete_horizon_not_silently_reach_only(monkeypatch):
    """Invariant 3: Game clock without minutes must not collapse to Reach-only READY."""
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    draft = {
        "universe": _nba_universe(),
        "entryConditions": [{"id": "e1", "family": "cross", "priceCents": 60}],
        "exitConditions": [
            {"id": "p1", "kind": "path", "family": "reach", "priceCents": 90, "outcome": "win"},
            {
                "id": "h1",
                "kind": "horizon",
                "family": "horizon_game_win",
                "outcome": "win",
                # horizonMinutes intentionally omitted
            },
        ],
    }
    c = compile_draft(draft)
    assert c.status is ResearchStatus.OPERATION_REQUIRED
    ops = {p.op for p in c.question.path_conditions}
    assert PathOp.HORIZON_WIN not in ops
    # Reach may still be on the AST, but compile must block — never READY Reach-only.
    assert c.execution_path.value == "none"


def test_game_clock_requires_pbp(monkeypatch):
    """Invariant 3b: Game clock WIN with minutes but no PBP → DATA_REQUIRED."""

    def _exists(cfg, sport, season, name):
        return name != "pbp"

    monkeypatch.setattr("roller.research_query.availability._dataset_exists", _exists)
    draft = {
        "universe": _nba_universe(),
        "entryConditions": [{"id": "e1", "family": "cross", "priceCents": 60}],
        "exitConditions": [
            {"id": "p1", "kind": "path", "family": "reach", "priceCents": 90, "outcome": "win"},
            {
                "id": "h1",
                "kind": "horizon",
                "family": "horizon_game_win",
                "horizonMinutes": 5,
                "outcome": "win",
            },
        ],
    }
    c = compile_draft(draft)
    assert c.status is ResearchStatus.DATA_REQUIRED
    out = execute_compiled(c, ticker_payloads={"T-A": _series([5900, 6000, 9000])})
    assert out["execution_status"] == "DATA_REQUIRED"
    assert (out.get("population") or {}).get("trades") in (None, [])


def test_cross_csv_entry_operation_not_first_touch(monkeypatch):
    """Invariant 4: result rows expose entry_operation=CROSS."""
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    draft = {
        "universe": _nba_universe(),
        "entryConditions": [{"id": "e1", "family": "cross", "priceCents": 60}],
        "exitConditions": [{"id": "p1", "kind": "path", "family": "reach", "priceCents": 90}],
    }
    c = compile_draft(draft)
    assert c.status is ResearchStatus.READY
    out = execute_compiled(
        c,
        ticker_payloads={"T-A": _series([5900, 6000, 7000, 9000])},
        snap_fn=_snap_quarter("Q3"),
    )
    trades = out["population"]["trades"]
    assert trades
    assert trades[0]["entry_operation"] == "CROSS"
    assert trades[0]["entry_ordinal"] == "FIRST"
    assert trades[0]["entry_operation"] != "FIRST_TOUCH"

