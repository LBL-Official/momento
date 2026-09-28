"""Generic research_query engines — synthetic adversarial tests. Does not edit FIRST80."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from roller.research.quality import quality
from roller.research_query.compiler import compile_draft, compile_question, question_from_draft, reference_match
from roller.research_query.entry_engine import crossings, nth_touch, same_minute_ties, tradable_sequence
from roller.research_query.execute import evaluate_ticker, execute_compiled, execute_question
from roller.research_query.measurements import (
    max_drawdown_cents,
    measure_finite_math,
    measure_rows,
    risk_of_ruin,
)
from roller.research_query.models import (
    BASIS_LAST_TRADE,
    EntryCondition,
    PathCondition,
    PathOp,
    ResearchQuestion,
    ResearchStatus,
    TerminalOutcome,
    TouchOrdinal,
    Universe,
    cents_to_e4,
)
from roller.research_query.path_engine import first_later, run_path
from roller.research_query.population import commute_ok, intersect_tickers
from roller.research_query.season_mapping import warehouse_season
from roller.timeutil import parse_utc

UTC = timezone.utc


def _bar(i: int, bid: int, *, ticker: str = "T-A", game: str = "G1", ask: int | None = None, vol: int = 10, valid=True):
    return {
        "available_at": f"2025-12-20T20:{i:02d}:00Z",
        "yes_bid_close": bid,
        "yes_ask_close": bid + 400 if ask is None else ask,
        "volume": vol,
        "ticker": ticker,
        "internal_game_id": game,
        "is_valid": valid,
    }


def _series(bids: list[int], **kw):
    return [_bar(i, b, **kw) for i, b in enumerate(bids)]


def _snap_quarter(q: str):
    period = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4, "OT": 5}.get(q, 3)

    def fn(ts: datetime) -> dict:
        return {
            "status": "REAL",
            "slice": q,
            "period": period,
            "clock": "08:00",
            "period_remaining_s": 480,
        }

    return fn


def _q(ordinal: TouchOrdinal, price_e4: int = 8000, period: str | None = None, **kw) -> ResearchQuestion:
    return ResearchQuestion(
        universe=Universe(
            sports=("basketball",),
            leagues=("NBA",),
            seasons=("2025-26",),
            markets=("kalshi",),
            market_data=("candles",),
        ),
        entry_conditions=(
            EntryCondition(id="e1", ordinal=ordinal, price_e4=price_e4, period=period),
        ),
        path_conditions=kw.get("path", ()),
        terminal=kw.get("terminal", TerminalOutcome.BOTH),
    )


def test_quality_reused_not_reinvented():
    assert quality(8000, 8500, 1, False) is True
    assert quality(8000, 9100, 1, False) is False


def test_ordinal_70_79_80_82_78_80_77_80():
    bars, skipped = tradable_sequence(_series([7000, 7900, 8000, 8200, 7800, 8000, 7700, 8000]))
    assert skipped == 0
    hits = crossings(bars, 8000)
    assert [h.bid for h in hits] == [8000, 8000, 8000]
    assert [h.ts.minute for h in hits] == [2, 5, 7]


def test_repeated_threshold_is_two_touches():
    bars, _ = tradable_sequence(_series([7900, 8000, 8000, 8000, 7900, 8000]))
    hits = crossings(bars, 8000)
    assert len(hits) == 2
    assert hits[0].ts.minute == 1
    assert hits[1].ts.minute == 5


def test_stays_above_is_one_touch():
    bars, _ = tradable_sequence(_series([7900, 8000, 8100, 8200, 8300]))
    assert len(crossings(bars, 8000)) == 1


def test_price_60_not_80():
    candles = _series([5000, 6000, 7000, 8000])
    bars, _ = tradable_sequence(candles)
    assert len(crossings(bars, 6000)) == 1
    assert crossings(bars, 6000)[0].ts.minute == 1
    assert crossings(bars, 8000)[0].ts.minute == 3


def test_untradable_does_not_create_or_reset_touch():
    rows = [
        _bar(0, 7900),
        _bar(1, 8000),
        {**_bar(2, 7000), "yes_ask_close": 9000, "volume": 0},  # untradable; must not reset
        _bar(3, 8000),
    ]
    bars, skipped = tradable_sequence(rows)
    assert skipped >= 1
    hits = crossings(bars, 8000)
    assert len(hits) == 1


def test_nth_touch_period_is_game_level_then_filter():
    candles = _series([7000, 8000, 7000, 8000])
    # first touch at minute 1 → Q2; second at minute 3 → Q3

    def snap(ts: datetime) -> dict:
        q = "Q2" if ts.minute == 1 else "Q3"
        return {"status": "REAL", "slice": q, "period": 2 if q == "Q2" else 3, "period_remaining_s": 400}

    first_q3, _ = nth_touch(
        candles,
        EntryCondition(id="e", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=8000, period="Q3"),
        snap_fn=snap,
    )
    assert first_q3 is None
    first_q2, _ = nth_touch(
        candles,
        EntryCondition(id="e", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=8000, period="Q2"),
        snap_fn=snap,
    )
    assert first_q2 is not None
    second_q3, _ = nth_touch(
        candles,
        EntryCondition(id="e", ordinal=TouchOrdinal.SECOND_TOUCH, price_e4=8000, period="Q3"),
        snap_fn=snap,
    )
    assert second_q3 is not None
    second_q2, _ = nth_touch(
        candles,
        EntryCondition(id="e", ordinal=TouchOrdinal.SECOND_TOUCH, price_e4=8000, period="Q2"),
        snap_fn=snap,
    )
    assert second_q2 is None


def test_unaligned_fails_period_not_price_only():
    candles = _series([7000, 8000])

    def snap(_ts):
        return {"status": "UNALIGNED", "slice": "UNALIGNED"}

    miss, diag = nth_touch(
        candles,
        EntryCondition(id="e", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=8000, period="Q3"),
        snap_fn=snap,
    )
    assert miss is None
    assert diag["unaligned"] == 1
    hit, _ = nth_touch(
        candles,
        EntryCondition(id="e", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=8000, period=None),
        snap_fn=snap,
    )
    assert hit is not None


def test_first_touch_records_observed_close_not_assumed_trigger():
    ev, _ = nth_touch(
        _series([7900, 8100]),
        EntryCondition(id="e", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=8000),
    )
    assert ev is not None
    assert ev.bar.bid == 8100


def test_max_entry_rejects_jump_through_and_does_not_take_later_touch():
    candles = _series([7900, 9400, 7000, 8200])
    first, diag = nth_touch(
        candles,
        EntryCondition(id="e", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=8000, max_entry_e4=8900),
    )
    assert first is None
    assert diag["reject_reason"] == "max_entry_exceeded"
    under, _ = nth_touch(
        _series([7900, 8100]),
        EntryCondition(id="e", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=8000, max_entry_e4=8900),
    )
    assert under is not None
    assert under.bar.bid == 8100


def test_max_entry_is_not_crossings_band():
    from roller.research_query.entry_engine import crossings_band

    candles = _series([7900, 9400, 7000, 8200])
    bars, _ = tradable_sequence(candles)
    band = crossings_band(bars, 8000, 8900)
    assert [h.bid for h in band] == [8200]
    ev, diag = nth_touch(
        candles,
        EntryCondition(id="e", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=8000, max_entry_e4=8900),
    )
    assert ev is None
    assert diag["reject_reason"] == "max_entry_exceeded"


def test_draft_max_entry_cents_is_ceiling_not_band(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    draft = {
        "universe": {
            "sports": ["basketball"],
            "leagues": ["NBA"],
            "seasons": ["2025-26"],
            "markets": ["kalshi"],
            "marketData": ["candles"],
        },
        "entryConditions": [
            {"id": "e1", "family": "first_touch", "priceCents": 80, "maxEntryCents": 89, "period": "Q3"}
        ],
        "exitConditions": [
            {"id": "p1", "kind": "path", "family": "reach", "priceCents": 40},
            {"id": "t", "kind": "terminal", "family": "both"},
        ],
    }
    q = question_from_draft(draft)
    assert q.entry_conditions[0].price_e4 == 8000
    assert q.entry_conditions[0].price_to_e4 is None
    assert q.entry_conditions[0].max_entry_e4 == 8900
    assert compile_draft(draft).reference_match is None


def test_same_minute_tie_excluded():
    a = TouchEvent_stub("T-A", "G1", "2025-12-20T20:01:00Z")
    b = TouchEvent_stub("T-B", "G1", "2025-12-20T20:01:00Z")
    kept, excluded = same_minute_ties([a, b])
    assert kept == []
    assert excluded == 2


def TouchEvent_stub(ticker: str, game: str, iso: str):
    from roller.research_query.entry_engine import TouchEvent, TradableBar

    ts = parse_utc(iso)
    bar = TradableBar(ts=ts, bid=8000, ask=8400, volume=10, ticker=ticker, game_id=game, raw={})
    return TouchEvent(
        ordinal=TouchOrdinal.FIRST_TOUCH,
        touch_index=1,
        price_e4=8000,
        bar=bar,
        snap={"status": "REAL", "slice": "Q3"},
        alignment="aligned",
    )


def test_and_commutative_funnel():
    a = {"t1", "t2", "t3"}
    b = {"t2", "t9"}
    i1, f1 = intersect_tickers([("a", "A", a), ("b", "B", b)], universe_n=10)
    i2, f2 = intersect_tickers([("b", "B", b), ("a", "A", a)], universe_n=10)
    assert i1 == i2 == {"t2"}
    assert commute_ok(a, b)
    assert f1[-1].qualifying == 1
    assert any(s.condition_id == "a" and s.qualifying == 3 for s in f1)


def test_empty_intersection_is_valid_zero():
    ident, funnel = intersect_tickers(
        [("a", "A", {"x"}), ("b", "B", {"y"})],
        universe_n=5,
    )
    assert ident == set()
    assert funnel[-1].qualifying == 0


def test_sequential_not_unordered():
    later = tradable_sequence(_series([4000, 8000], ticker="T"))[0]
    reach_then_recover = [
        PathCondition(id="p1", op=PathOp.REACH, price_e4=4000, sequential=True),
        PathCondition(id="p2", op=PathOp.RECOVER, price_e4=8000, sequential=True),
    ]
    recover_then_reach = [
        PathCondition(id="p1", op=PathOp.RECOVER, price_e4=8000, sequential=True),
        PathCondition(id="p2", op=PathOp.REACH, price_e4=4000, sequential=True),
    ]
    hits, ok, _exit = run_path(later, 8000, reach_then_recover)
    assert ok and len(hits) == 2
    assert run_path(later, 8000, recover_then_reach)[1] is False

    later_high_then_low = tradable_sequence(_series([8200, 4000], ticker="T"))[0]
    assert run_path(later_high_then_low, 8000, reach_then_recover)[1] is False
    assert run_path(later_high_then_low, 8000, recover_then_reach)[1] is False


def test_entry_candle_cannot_satisfy_path():
    later = tradable_sequence(_series([8000, 4000]))[0]
    # if we wrongly included entry 80 as reach 80
    hit = first_later(later, entry_close=8000, op=PathOp.REACH, price_e4=8000)
    assert hit is None or hit.ts.minute != later[0].ts.minute or later[0].bid != 8000
    # first later bar is 8000 — prior is entry 8000, reach_from_side(8000,8000,8000) is False
    assert first_later(later[:1], entry_close=8000, op=PathOp.REACH, price_e4=8000) is None
    assert first_later(later, entry_close=8000, op=PathOp.REACH, price_e4=4000) is not None


def test_target_already_at_entry_not_immediate_reach():
    later = tradable_sequence(_series([8000, 8000]))[0]
    assert first_later(later, entry_close=8000, op=PathOp.REACH, price_e4=8000) is None


def test_zero_close_is_not_reach_35():
    skipped = tradable_sequence(_series([0, 8200]))[0]
    assert skipped[0].bid == 0
    assert first_later(skipped, entry_close=8000, op=PathOp.REACH, price_e4=3500) is None
    later_real = tradable_sequence(_series([0, 3400]))[0]
    hit = first_later(later_real, entry_close=8000, op=PathOp.REACH, price_e4=3500)
    assert hit is not None
    assert hit.bid == 3400


def test_joint_partition_same_population():
    rows = [
        {"path_true": True, "terminal_yes": True},
        {"path_true": True, "terminal_yes": False},
        {"path_true": False, "terminal_yes": True},
        {"path_true": False, "terminal_yes": False},
        {"path_true": True, "terminal_yes": None},
    ]
    m = measure_rows(rows)
    p = m["partition"]
    assert p["T_AND_W"] + p["T_AND_NOT_W"] + p["NOT_T_AND_W"] + p["NOT_T_AND_NOT_W"] == 4
    assert m["terminal_missing"] == 1
    assert m["n"] == 5
    assert m["path_true"] == 3
    assert m["path_false"] == 2
    assert p["joint_n"] == 4


def test_second_touch_round_trip_never_becomes_first(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    draft = {
        "universe": {
            "sports": ["basketball"],
            "leagues": ["NBA"],
            "seasons": ["2025-26"],
            "markets": ["kalshi"],
            "marketData": ["candles"],
            "dataSources": ["nba_api"],
        },
        "entryConditions": [
            {"id": "e1", "family": "second_touch", "priceCents": 80, "period": "Q3"}
        ],
        "exitConditions": [
            {"id": "p1", "kind": "path", "family": "reach", "priceCents": 40},
            {"id": "t1", "kind": "terminal", "family": "both"},
        ],
    }
    q = question_from_draft(draft)
    assert q.entry_conditions[0].ordinal is TouchOrdinal.SECOND_TOUCH
    assert q.entry_conditions[0].price_e4 == 8000
    blob = json.dumps(q.to_dict())
    q2 = ResearchQuestion.from_dict(json.loads(blob))
    assert q2.entry_conditions[0].ordinal is TouchOrdinal.SECOND_TOUCH
    compiled = compile_question(q2, draft=draft)
    assert compiled.question.entry_conditions[0].ordinal is TouchOrdinal.SECOND_TOUCH
    assert compiled.reference_match is None
    assert compiled.execution_path.value == "generic_query"
    assert compiled.status is ResearchStatus.READY
    candles = _series([7000, 8000, 7000, 8000, 4000])
    row, _ = evaluate_ticker(
        candles,
        q2,
        snap_fn=_snap_quarter("Q3"),
        market={"result": "yes"},
    )
    assert row is not None
    assert row["entry_ordinal"] == "SECOND_TOUCH"
    assert row["entry_operation"] == "SECOND_TOUCH"
    assert row["path_true"] is True


def test_reference_match_breaks_on_material_difference(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    lock = {
        "universe": {
            "sports": ["basketball"],
            "leagues": ["NBA"],
            "seasons": ["2025-26"],
            "markets": ["kalshi"],
            "marketData": ["candles"],
        },
        "entryConditions": [
            {"id": "e1", "family": "first_touch", "priceCents": 80, "period": "Q3"}
        ],
        "exitConditions": [
            {"id": "p1", "kind": "path", "family": "reach", "priceCents": 40},
            {"id": "t", "kind": "terminal", "family": "both"},
        ],
    }
    assert compile_draft(lock).reference_match == "FIRST80_Q3"
    lock2 = json.loads(json.dumps(lock))
    lock2["entryConditions"][0]["family"] = "second_touch"
    assert compile_draft(lock2).reference_match is None
    lock3 = json.loads(json.dumps(lock))
    lock3["entryConditions"][0]["priceCents"] = 60
    assert compile_draft(lock3).reference_match is None
    lock4 = json.loads(json.dumps(lock))
    lock4["entryConditions"][0]["period"] = "Q2"
    assert compile_draft(lock4).reference_match is None


def _polymarket_draft(markets=("polymarket",)):
    return {
        "universe": {
            "sports": ["basketball"],
            "leagues": ["NBA"],
            "seasons": ["2025-26"],
            "markets": list(markets),
            "marketData": ["candles"],
        },
        "entryConditions": [
            {"id": "e1", "family": "first_touch", "priceCents": 80, "period": "Q3"}
        ],
        "exitConditions": [{"id": "t", "kind": "terminal", "family": "both"}],
    }


def test_polymarket_never_substitutes_kalshi(monkeypatch):
    """Polymarket compiles and runs, but only on its own last-trade basis.

    This previously asserted DATA_REQUIRED / OPERATION_REQUIRED, which made
    linked Polymarket data unreadable. The surviving invariant is that a
    Polymarket question never borrows Kalshi's tradable basis or a frozen lock.
    """
    monkeypatch.setattr(
        "roller.research_query.availability._dataset_exists", lambda *a, **k: True
    )
    c = compile_draft(_polymarket_draft())
    assert c.status is ResearchStatus.READY
    assert c.question.basis() == BASIS_LAST_TRADE
    assert c.question.entry_conditions[0].price_field == "last_close_e4"
    assert c.reference_match is None
    assert "kalshi_1m_candles" not in c.available
    assert "tradable_yes_bid_close_cross" not in c.available


def test_polymarket_cross_venue_is_operation_required(monkeypatch):
    monkeypatch.setattr(
        "roller.research_query.availability._dataset_exists", lambda *a, **k: True
    )
    draft = _polymarket_draft(markets=("kalshi", "polymarket"))
    c = compile_draft(draft)
    assert c.status is ResearchStatus.OPERATION_REQUIRED
    assert "cross_venue_joint_basis" in c.unavailable
    out = execute_question({"draft": draft})
    assert out["execution_status"] == "OPERATION_REQUIRED"
    assert out["summary"]["population_n"] is None


def test_bounce_operation_required_not_zero(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    draft = {
        "universe": {
            "sports": ["basketball"],
            "leagues": ["NBA"],
            "seasons": ["2025-26"],
            "markets": ["kalshi"],
            "marketData": ["candles"],
        },
        "entryConditions": [{"id": "e1", "family": "bounce", "priceCents": 80, "period": "Q3"}],
        "exitConditions": [{"id": "t", "kind": "terminal", "family": "both"}],
    }
    c = compile_draft(draft)
    assert c.status is ResearchStatus.READY
    assert c.execution_path.value == "generic_query"
    tickers = {
        "T-UP": _series([7900, 8000, 7900], ticker="T-UP", game="G-UP"),
        "T-DOWN": _series([8100, 8000, 8100], ticker="T-DOWN", game="G-DOWN"),
        "T-THRU": _series([7900, 8000, 8100], ticker="T-THRU", game="G-THRU"),
        "T-SKIP": _series([7900, 8100], ticker="T-SKIP", game="G-SKIP"),
    }
    out = execute_compiled(
        c,
        ticker_payloads=tickers,
        snap_fn=_snap_quarter("Q3"),
    )
    assert out["execution_status"] == "COMPLETE"
    ids = {r["ticker"] for r in out["population"]["trades"]}
    assert ids == {"T-UP", "T-DOWN"}


def test_generic_provenance_not_frozen(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    q = _q(TouchOrdinal.SECOND_TOUCH, 8000, "Q3")
    compiled = compile_question(q)
    out = execute_compiled(
        compiled,
        ticker_payloads={"T-A": _series([7000, 8000, 7000, 8000])},
        snap_fn=_snap_quarter("Q3"),
        markets_by_ticker={"T-A": {"result": "yes"}},
    )
    assert out["execution_status"] == "COMPLETE"
    assert out["provenance"]["path"] == "generic_query"
    assert out["provenance"]["observability"] == "CANDLE-LEVEL OBSERVED"
    assert out["provenance"].get("definition_versions", {}).get("FIRST80") != "warehouse_frozen_v1"
    assert "warehouse_frozen_v1" not in json.dumps(out["provenance"])


def test_malicious_client_cannot_force_frozen(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    draft = {
        "universe": {
            "sports": ["basketball"],
            "leagues": ["NBA"],
            "seasons": ["2025-26"],
            "markets": ["kalshi"],
            "marketData": ["candles"],
        },
        "entryConditions": [
            {"id": "e1", "family": "second_touch", "priceCents": 80, "period": "Q3"}
        ],
        "exitConditions": [{"id": "t", "kind": "terminal", "family": "both"}],
        "execution_path": "frozen_reference",
        "reference_match": "FIRST80_Q3",
        "status": "READY",
    }
    out = execute_question({"draft": draft, "execution_path": "frozen_reference", "reference_match": "FIRST80_Q3"})
    assert out["compile"]["execution_path"] == "generic_query"
    assert out["compile"]["reference_match"] is None
    assert out.get("provenance", {}).get("path") != "warehouse_frozen_v1"


def test_season_mapping_ui_to_warehouse():
    assert warehouse_season("2025-26", "NBA") == "2025-2026"
    assert warehouse_season("2025-2026", "NBA") == "2025-2026"


def test_cents_e4():
    assert cents_to_e4(80) == 8000
    assert cents_to_e4(5) == 500


def test_frozen_lock_uses_existing_executor():
    from roller.dashboard_adapter.bindings import (
        warehouse_barrier_trades_available,
        warehouse_first80_available,
    )
    from roller.dashboard_adapter.research_executor import execute_research_object
    from roller.dashboard_adapter.research_object import load_sample

    if not warehouse_first80_available() or not warehouse_barrier_trades_available():
        pytest.skip("warehouse FIRST80 artifacts missing")
    spec = load_sample("first80_q3_path_terminal.json")
    frozen = execute_research_object(spec)
    assert frozen["execution_status"] == "COMPLETE"
    n = frozen["summary"]["population_n"]
    draft = {
        "universe": {
            "sports": ["basketball"],
            "leagues": ["NBA"],
            "seasons": ["2025-26"],
            "markets": ["kalshi"],
            "marketData": ["candles"],
        },
        "entryConditions": [
            {"id": "e1", "family": "first_touch", "priceCents": 80, "period": "Q3"}
        ],
        "exitConditions": [
            {"id": "p1", "kind": "path", "family": "reach", "priceCents": 40},
            {"id": "t", "kind": "terminal", "family": "both"},
        ],
    }
    compiled = compile_draft(draft)
    assert compiled.reference_match == "FIRST80_Q3"
    assert compiled.execution_path.value == "frozen_reference"
    out = execute_question({"draft": draft})
    assert out["execution_status"] == "COMPLETE"
    assert out["summary"]["population_n"] == n
    assert out.get("bindings", {}).get("FIRST80", {}).get("actual_definition_version") == "warehouse_frozen_v1"


def test_clock_filter_boundary():
    from roller.research_query.models import ClockWindow

    w = ClockWindow(240, 480)
    assert w.contains(240)
    assert w.contains(480)
    assert not w.contains(239)
    assert not w.contains(481)


def test_missing_settlement_counted_not_inferred():
    q = _q(TouchOrdinal.FIRST_TOUCH, 8000)
    row, _ = evaluate_ticker(_series([7000, 8000, 4000]), q, market=None)
    assert row is not None
    assert row["terminal_yes"] is None
    m = measure_rows([row])
    assert m["terminal_missing"] == 1
    assert m["yes_rate"] is None


def test_ncaab_h1_matches_first_ten_slice():
    from roller.research_query.models import ClockWindow

    candles = _series([7000, 8000])
    snap = lambda ts: {
        "status": "REAL",
        "slice": "H1_1",
        "period": 1,
        "clock": "15:00",
        "period_remaining_s": 900,
    }
    q_half = _q(TouchOrdinal.FIRST_TOUCH, 8000, "H1")
    row, _ = evaluate_ticker(candles, q_half, sport="NCAAB", snap_fn=snap)
    assert row is not None
    q_first10 = _q(TouchOrdinal.FIRST_TOUCH, 8000, "H1_1")
    row10, _ = evaluate_ticker(candles, q_first10, sport="NCAAB", snap_fn=snap)
    assert row10 is not None
    q_second10 = _q(TouchOrdinal.FIRST_TOUCH, 8000, "H1_2")
    miss, _ = evaluate_ticker(candles, q_second10, sport="NCAAB", snap_fn=snap)
    assert miss is None
    q_5 = ResearchQuestion(
        universe=q_half.universe,
        entry_conditions=(
            EntryCondition(
                id="e1",
                ordinal=TouchOrdinal.FIRST_TOUCH,
                price_e4=8000,
                period="H1",
                clock=ClockWindow(900, 1200),
            ),
        ),
        path_conditions=(),
        terminal=TerminalOutcome.BOTH,
    )
    hit5, _ = evaluate_ticker(candles, q_5, sport="NCAAB", snap_fn=snap)
    assert hit5 is not None


def test_period_windows_are_or_not_and():
    from roller.research_query.models import PeriodWindow

    candles = _series([7000, 8000])
    q = ResearchQuestion(
        universe=_q(TouchOrdinal.FIRST_TOUCH, 8000).universe,
        entry_conditions=(
            EntryCondition(
                id="e1",
                ordinal=TouchOrdinal.FIRST_TOUCH,
                price_e4=8000,
                period_windows=(PeriodWindow(period="Q1"), PeriodWindow(period="Q3")),
            ),
        ),
        path_conditions=(),
        terminal=TerminalOutcome.BOTH,
    )
    assert evaluate_ticker(candles, q, snap_fn=_snap_quarter("Q1"))[0] is not None
    assert evaluate_ticker(candles, q, snap_fn=_snap_quarter("Q3"))[0] is not None
    miss, _ = evaluate_ticker(candles, q, snap_fn=_snap_quarter("Q2"))
    assert miss is None


def test_single_period_dict_omits_empty_windows():
    payload = _q(TouchOrdinal.FIRST_TOUCH, 8000, "Q3").entry_conditions[0].to_dict()
    assert payload["period"] == "Q3"
    assert "period_windows" not in payload


def test_hold_only_win_does_not_require_path_price(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    draft = {
        "universe": {
            "sports": ["basketball"],
            "leagues": ["NBA"],
            "seasons": ["2025-26"],
            "markets": ["kalshi"],
            "marketData": ["candles"],
        },
        "entryConditions": [{"id": "e1", "family": "first_touch", "priceCents": 55}],
        "exitConditions": [
            {"id": "t", "kind": "terminal", "family": "hold_expiration_win", "outcome": "win"},
        ],
    }
    q = question_from_draft(draft)
    assert q.win_hold is True
    assert q.path_conditions == ()
    assert "reach" not in q.requested_dimensions
    compiled = compile_draft(draft)
    assert compiled.reference_match is None
    row, _ = evaluate_ticker(_series([5000, 5500, 4000]), q, market={"result": "yes"})
    assert row is not None
    assert row["exit_outcome"] == "WIN_EXIT"
    assert row["terminal_yes"] is True
    missing, _ = evaluate_ticker(_series([5000, 5500, 4000]), q, market=None)
    assert missing is not None
    assert missing["exit_outcome"] is None
    assert missing["terminal_yes"] is None


def test_draft_period_windows_compile_or():
    q = question_from_draft(
        {
            "universe": {
                "sports": ["basketball"],
                "leagues": ["NBA"],
                "markets": ["kalshi"],
                "marketData": ["candles"],
            },
            "entryConditions": [
                {
                    "id": "e1",
                    "family": "first_touch",
                    "priceCents": 80,
                    "periodWindows": [{"period": "Q1"}, {"period": "Q3"}],
                }
            ],
            "exitConditions": [{"id": "p1", "kind": "path", "family": "reach", "priceCents": 40}],
        }
    )
    assert q.entry_conditions[0].period is None
    assert [w.period for w in q.entry_conditions[0].period_windows] == ["Q1", "Q3"]
    assert reference_match(q) is None


def test_nba_four_minute_clock_window():
    from roller.research_query.models import ClockWindow

    candles = _series([7000, 8000])
    q = ResearchQuestion(
        universe=_q(TouchOrdinal.FIRST_TOUCH).universe,
        entry_conditions=(
            EntryCondition(
                id="e1",
                ordinal=TouchOrdinal.FIRST_TOUCH,
                price_e4=8000,
                period="Q1",
                clock=ClockWindow(480, 720),
            ),
        ),
        path_conditions=(),
        terminal=TerminalOutcome.BOTH,
    )
    inside = lambda ts: {
        "status": "REAL",
        "slice": "Q1",
        "period": 1,
        "clock": "10:00",
        "period_remaining_s": 600,
    }
    outside = lambda ts: {
        "status": "REAL",
        "slice": "Q1",
        "period": 1,
        "clock": "03:00",
        "period_remaining_s": 180,
    }
    ok, _ = evaluate_ticker(candles, q, snap_fn=inside)
    no, _ = evaluate_ticker(candles, q, snap_fn=outside)
    assert ok is not None
    assert no is None


def test_band_enter_is_one_touch_and_breaks_lock(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    from roller.research_query.entry_engine import crossings_band

    bars, _ = tradable_sequence(_series([4000, 5500, 6000, 8000, 4000, 5600]))
    hits = crossings_band(bars, 5000, 7000)
    assert [h.ts.minute for h in hits] == [1, 5]
    draft = {
        "universe": {
            "sports": ["basketball"],
            "leagues": ["NBA"],
            "seasons": ["2025-26"],
            "markets": ["kalshi"],
            "marketData": ["candles"],
        },
        "entryConditions": [
            {"id": "e1", "family": "first_touch", "priceFrom": 80, "priceTo": 83, "period": "Q3"}
        ],
        "exitConditions": [
            {"id": "p1", "kind": "path", "family": "reach", "priceCents": 40},
            {"id": "t", "kind": "terminal", "family": "both"},
        ],
    }
    q = question_from_draft(draft)
    assert q.entry_conditions[0].price_e4 == 8000
    assert q.entry_conditions[0].price_to_e4 == 8300
    assert compile_draft(draft).reference_match is None


def test_hold_expiration_and_horizon_compile(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    draft = {
        "universe": {
            "sports": ["basketball"],
            "leagues": ["NBA"],
            "seasons": ["2025-26"],
            "markets": ["kalshi"],
            "marketData": ["candles"],
        },
        "entryConditions": [{"id": "e1", "family": "first_touch", "priceCents": 55}],
        "exitConditions": [
            {
                "id": "h1",
                "kind": "horizon",
                "family": "horizon_market_win",
                "horizonKind": "market",
                "horizonMinutes": 2,
            },
            {"id": "t", "kind": "terminal", "family": "hold_expiration_win"},
        ],
    }
    q = question_from_draft(draft)
    assert q.terminal is TerminalOutcome.YES
    assert q.path_conditions[0].op is PathOp.HORIZON_WIN
    assert q.path_conditions[0].horizon_kind == "market"
    assert q.path_conditions[0].horizon_minutes == 2
    assert compile_draft(draft).reference_match is None
    candles = _series([5000, 5500, 4000, 6200])
    row, _ = evaluate_ticker(candles, q, market={"result": "yes"})
    assert row is not None
    assert row["path_true"] is True
    assert row["exit_close"] == 6200
    assert row["hyp_pnl_cents"] == (6200 - 5500) // 100


def test_horizon_loss_still_records_exit_close():
    q = _q(
        TouchOrdinal.FIRST_TOUCH,
        5500,
        path=(
            PathCondition(
                id="h1",
                op=PathOp.HORIZON_WIN,
                price_e4=5000,
                horizon_kind="market",
                horizon_minutes=2,
            ),
        ),
    )
    candles = _series([5000, 5500, 4000, 4200])
    row, _ = evaluate_ticker(candles, q, market=None)
    assert row is not None
    assert row["path_true"] is False
    assert row["exit_close"] == 4200
    assert row["hyp_pnl_cents"] == (4200 - 5500) // 100
    assert row["terminal_yes"] is None


def test_path_margin_not_joint_zeros_when_settlement_absent():
    rows = [
        {"path_true": True, "terminal_yes": None, "hyp_pnl_cents": 5, "entry_ts": "2026-01-01T00:00:00Z"},
        {"path_true": False, "terminal_yes": None, "hyp_pnl_cents": -8, "entry_ts": "2026-01-01T00:01:00Z"},
        {"path_true": True, "terminal_yes": None, "hyp_pnl_cents": -3, "entry_ts": "2026-01-01T00:02:00Z"},
    ]
    m = measure_rows(rows)
    assert m["path_true"] == 2
    assert m["path_false"] == 1
    assert m["partition"]["joint_n"] == 0
    math = measure_finite_math(
        rows,
        model_a_8040=False,
        path_rate=m["path_rate"],
        path_true=m["path_true"],
        path_available=m["path_available"],
    )
    assert math["observed_n"] == 3
    assert math["mean_hyp_pnl_cents"] == (5 - 8 - 3) / 3
    assert math["max_drawdown_cents"] == 11
    assert math["risk_of_ruin"] is not None


def test_model_a_8040_ev_and_ruin():
    math = measure_finite_math(
        [{"path_true": True}, {"path_true": False}, {"path_true": False}],
        model_a_8040=True,
        path_rate=1 / 3,
        path_true=1,
        path_available=3,
    )
    assert math["model_a_ev_cents"] == 20.0 - 60.0 * (1 / 3)
    assert math["risk_of_ruin"] is not None
    assert risk_of_ruin(0.0, 20.0, 40.0) == 1.0
    assert risk_of_ruin(1.0, 20.0, 40.0) == 0.0
    assert max_drawdown_cents([10, -5, -20, 8]) == 25


def test_full_season_autofill_does_not_break_lock(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    lock = {
        "universe": {
            "sports": ["basketball"],
            "leagues": ["NBA"],
            "seasons": ["2025-26"],
            "markets": ["kalshi"],
            "marketData": ["candles"],
            "dateFrom": "2025-10-10",
            "dateTo": "2026-06-13",
        },
        "entryConditions": [{"id": "e1", "family": "first_touch", "priceCents": 80, "period": "Q3"}],
        "exitConditions": [
            {"id": "p1", "kind": "path", "family": "reach", "priceCents": 40},
            {"id": "t", "kind": "terminal", "family": "both"},
        ],
    }
    assert compile_draft(lock).reference_match == "FIRST80_Q3"
    lock["universe"]["dateFrom"] = "2025-12-01"
    assert compile_draft(lock).reference_match is None
