"""Every discrete Quick Start combo pulls the warehouse or fails closed.

N is the count of injected rows that match the chips. Not a golden live N.
Does not edit FIRST80. CANDLE ≠ FILL.
"""

from __future__ import annotations

import pytest

from roller.research_query.chip_catalog import (
    DIRECTION_FAMILIES,
    ENTRY_FAMILIES,
    PATH_FAMILIES,
    REFUSE_PATH_FAMILIES,
    ChipCombo,
    all_combos,
    catalog_entry_families,
    draft_from_combo,
    implemented_entry_bindings,
    measure_combos,
    period_chips,
    refuse_combos,
)
from roller.research_query.chip_query import measured_n, pull
from roller.research_query.compiler import compile_draft
from roller.research_query.execute import execute_compiled
from roller.research_query.models import ENTRY_OP_FAMILIES, TOUCH_FAMILIES, ResearchStatus


PRICES = [7900, 8000, 7900, 8100, 7000, 9000]


def _bar(i: int, bid: int, *, ticker: str, game: str, sport: str, league: str) -> dict:
    return {
        "available_at": f"2025-12-20T20:{i:02d}:00Z",
        "candle_timestamp": f"2025-12-20T20:{i:02d}:00Z",
        "yes_bid_close": bid,
        "yes_ask_close": bid + 400,
        "last_close_e4": bid,
        "volume": 10,
        "ticker": ticker,
        "internal_game_id": game,
        "is_valid": True,
        "team_side": "home" if sport != "ATP" and sport != "WTA" else "1",
        "_research_sport": sport,
        "_research_league": league,
        "sport": sport,
        "league": league,
    }


def _nba_pbp() -> list[dict]:
    return [
        {
            "internal_game_id": "NBA_G1",
            "event_number": 1,
            "event_timestamp": "2025-12-20T20:00:50Z",
            "event_time": "2025-12-20T20:00:50Z",
            "available_at": "2025-12-20T20:00:50Z",
            "period": 3,
            "clock": "08:00",
            "home_score": 60,
            "away_score": 55,
        }
    ]


def _ncaab_pbp() -> list[dict]:
    return [
        {
            "internal_game_id": "NCAAB_G1",
            "event_number": 1,
            "event_timestamp": "2025-12-20T20:00:50Z",
            "event_time": "2025-12-20T20:00:50Z",
            "available_at": "2025-12-20T20:00:50Z",
            "period": 2,
            "clock": "12:00",
            "home_score": 40,
            "away_score": 35,
        }
    ]


def _mlb_pbp() -> list[dict]:
    return [
        {
            "internal_game_id": "MLB_G1",
            "event_number": 1,
            "event_timestamp": "2025-12-20T20:00:50Z",
            "inning": 7,
            "half": "top",
            "outs": 1,
            "balls": 1,
            "strikes": 1,
            "home_score": 1,
            "away_score": 3,
            "batting_team": "away",
        }
    ]


def _tennis_pbp(game: str) -> list[dict]:
    return [
        {
            "internal_game_id": game,
            "point_number": 1,
            "set_number": 1,
            "game_number": 2,
            "event_timestamp": "2025-12-20T20:00:50Z",
            "pbp_basis": "TIMESTAMPED_OBSERVED",
            "pit_joinable": True,
            "server": 1,
            "receiver": 2,
        }
    ]


def warehouse_for(league: str) -> dict:
    sport = {
        "NBA": "NBA",
        "NCAAB": "NCAAB",
        "MLB": "MLB",
        "ATP": "ATP",
        "WTA": "WTA",
    }[league]
    ticker = f"{league}-T"
    game = f"{league}_G1"
    candles = [_bar(i, bid, ticker=ticker, game=game, sport=sport, league=league) for i, bid in enumerate(PRICES)]
    pbp = {
        "NBA": _nba_pbp,
        "NCAAB": _ncaab_pbp,
        "MLB": _mlb_pbp,
        "ATP": lambda: _tennis_pbp("ATP_G1"),
        "WTA": lambda: _tennis_pbp("WTA_G1"),
    }[league]()
    return {
        "ticker_payloads": {ticker: candles},
        "pbp_by_game": {game: pbp},
        "markets_by_ticker": {ticker: {"result": "yes", "internal_game_id": game}},
        "games": [
            {
                "internal_game_id": game,
                "league": league,
                "sport": sport,
                "_research_sport": sport,
                "_research_league": league,
                "game_date": "2025-12-20",
            }
        ],
    }


def _period_expected(combo: ChipCombo) -> bool | None:
    """True/False when the fixture snap is known; None if period is absent."""
    if not combo.period and not combo.clock_from:
        return None
    if combo.league == "NBA":
        if combo.period != "Q3":
            return False
        if combo.clock_from == "12:00" and combo.clock_to == "08:00":
            return True
        if combo.clock_from == "08:00" and combo.clock_to == "04:00":
            return True
        if combo.clock_from == "04:00" and combo.clock_to == "00:00":
            return False
        return combo.clock_from is None
    if combo.league == "NCAAB":
        if combo.period in {"H2", "H2_1", "P5"}:
            if combo.clock_from == "20:00":
                return False
            if combo.clock_from == "15:00" and combo.clock_to == "10:00":
                return True
            if combo.clock_from in {"10:00", "05:00"}:
                return False
            return combo.clock_from is None
        return False
    if combo.league == "MLB":
        return combo.period in {"T7", "I7"}
    if combo.league in {"ATP", "WTA"}:
        return combo.period in {"S1", "G1-3"}
    return False


def _touch_expected(family: str) -> int:
    """Hand count on 79,80,79,81,70,90 at 80¢. Upward touches only."""
    return {"first_touch": 1, "second_touch": 1, "third_touch": 1}.get(family, 0) if family in (
        "first_touch",
        "second_touch",
        "third_touch",
        "fourth_touch",
        "nth_touch",
    ) else -1


@pytest.fixture(autouse=True)
def _warehouse_present(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    monkeypatch.setattr(
        "roller.research_query.market_path.candles_quality_ready",
        lambda *a, **k: True,
    )


def test_catalog_covers_every_implemented_entry_and_path():
    assert tuple(catalog_entry_families()) == ENTRY_FAMILIES
    assert set(ENTRY_FAMILIES) == implemented_entry_bindings()
    measured = measure_combos()
    entries = {c.entry_family for c in measured}
    assert entries == set(ENTRY_FAMILIES)
    paths = {c.path_family for c in measured}
    assert set(PATH_FAMILIES) <= paths
    refuse_paths = {c.path_family for c in refuse_combos() if c.path_family in REFUSE_PATH_FAMILIES}
    assert refuse_paths == set(REFUSE_PATH_FAMILIES)
    for league, families in (
        ("NBA", period_chips("NBA")),
        ("NCAAB", period_chips("NCAAB")),
        ("MLB", period_chips("MLB")),
        ("ATP", period_chips("ATP")),
        ("WTA", period_chips("WTA")),
    ):
        ids = {c.period_id or c.period for c in measured if c.league == league and c.period}
        want = {p.get("id") or p.get("period") for p in families}
        assert want <= ids, f"{league} missing period chips: {want - ids}"


def test_identity_holds_for_every_measure_combo():
    for combo in measure_combos():
        draft = draft_from_combo(combo)
        compiled = compile_draft(draft)
        assert compiled.status in {ResearchStatus.READY, ResearchStatus.READY_WITH_LIMITATIONS}, (
            combo.combo_id,
            compiled.status,
            compiled.reasons,
        )
        entry = compiled.question.entry_conditions[0]
        if combo.entry_family in TOUCH_FAMILIES:
            assert entry.ordinal.value == TOUCH_FAMILIES[combo.entry_family].value
        else:
            assert entry.resolved_operation() is ENTRY_OP_FAMILIES[combo.entry_family]
        assert entry.price_e4 == 8000
        if combo.period:
            assert entry.names_period(combo.period)
        if combo.direction:
            assert entry.direction == combo.direction


@pytest.mark.parametrize("combo", measure_combos(), ids=lambda c: c.combo_id)
def test_measure_combo_returns_warehouse_n(combo: ChipCombo):
    draft = draft_from_combo(combo)
    wh = warehouse_for(combo.league)
    pulled = pull(draft, **wh)
    compiled = compile_draft(draft)
    assert compiled.status is ResearchStatus.READY, (combo.combo_id, compiled.reasons)
    executed = execute_compiled(
        compiled,
        ticker_payloads=wh["ticker_payloads"],
        pbp_by_game=wh["pbp_by_game"],
        markets_by_ticker=wh["markets_by_ticker"],
        games=wh["games"],
        te_filters=draft.get("teFilters"),
    )
    pull_n = pulled["n"]
    exec_n = measured_n(executed)
    assert pull_n is not None, (combo.combo_id, pulled.get("execution_status"), pulled)
    assert exec_n == pull_n, (combo.combo_id, exec_n, pull_n, executed.get("execution_status"))

    period_ok = _period_expected(combo)
    touch_n = _touch_expected(combo.entry_family)
    if period_ok is False and combo.period:
        assert pull_n == 0, (combo.combo_id, "period chip must exclude this snap")
    elif period_ok is not False and touch_n >= 0 and combo.path_family == "reach" and not combo.horizon_family:
        assert pull_n == touch_n, (combo.combo_id, pull_n, touch_n)
    if pull_n:
        op = pulled["trades"][0]["entry_operation"]
        if combo.entry_family in TOUCH_FAMILIES:
            assert op == TOUCH_FAMILIES[combo.entry_family].value
        else:
            assert op == ENTRY_OP_FAMILIES[combo.entry_family].value


@pytest.mark.parametrize("combo", refuse_combos(), ids=lambda c: c.combo_id)
def test_refuse_combo_returns_no_number(combo: ChipCombo):
    draft = draft_from_combo(combo)
    compiled = compile_draft(draft)
    assert compiled.status in {
        ResearchStatus.OPERATION_REQUIRED,
        ResearchStatus.DATA_REQUIRED,
        ResearchStatus.READY_WITH_LIMITATIONS,
    }, (combo.combo_id, compiled.status, compiled.reasons)
    if combo.refuse_status:
        assert compiled.status.value == combo.refuse_status or compiled.status in {
            ResearchStatus.OPERATION_REQUIRED,
            ResearchStatus.DATA_REQUIRED,
        }
    if combo.league in {"NBA", "NCAAB", "MLB", "ATP", "WTA"}:
        wh = warehouse_for(combo.league)
    else:
        wh = warehouse_for("NBA")
        draft["universe"]["leagues"] = [combo.league]
    pulled = pull(draft, **wh)
    assert pulled["n"] is None
    executed = execute_compiled(
        compiled,
        ticker_payloads=wh["ticker_payloads"],
        pbp_by_game=wh["pbp_by_game"],
        markets_by_ticker=wh["markets_by_ticker"],
        games=wh["games"],
    )
    assert measured_n(executed) is None
    assert (executed.get("population") or {}).get("trades") in (None, [])


def test_last_trade_reads_print_not_yes_bid():
    """Hand case: yes bid 80 / print 60 is a 60¢ last-trade touch, not 80¢."""
    combo = ChipCombo(league="NBA", entry_family="first_touch", market_data="last_trade", expect="MEASURE")
    draft = draft_from_combo(combo)
    ticker = "NBA-DIVERGE"
    candles = []
    for i, (bid, last) in enumerate(((7900, 5900), (8000, 6000), (8100, 6100))):
        row = _bar(i, bid, ticker=ticker, game="NBA_G1", sport="NBA", league="NBA")
        row["last_close_e4"] = last
        candles.append(row)
    wh = {
        "ticker_payloads": {ticker: candles},
        "pbp_by_game": {"NBA_G1": _nba_pbp()},
        "markets_by_ticker": {ticker: {"result": "yes"}},
        "games": [{"internal_game_id": "NBA_G1", "sport": "NBA", "league": "NBA"}],
    }
    at_80 = pull(draft, **wh)
    assert at_80["n"] == 0
    draft["entryConditions"][0]["priceCents"] = 60
    at_60 = pull(draft, **wh)
    assert at_60["n"] == 1
    assert at_60["trades"][0]["entry_close"] == 6000


def test_direction_up_vs_down_changes_n():
    up = ChipCombo(
        league="NBA",
        entry_family="cross",
        direction="up",
        expect="MEASURE",
    )
    down = ChipCombo(
        league="NBA",
        entry_family="cross",
        direction="down",
        expect="MEASURE",
    )
    wh = warehouse_for("NBA")
    assert pull(draft_from_combo(up), **wh)["n"] == 1
    # 80→79 is the first down cross of 80 after the open.
    assert pull(draft_from_combo(down), **wh)["n"] == 1
    only_up = warehouse_for("NBA")
    only_up["ticker_payloads"]["NBA-T"] = [
        _bar(i, bid, ticker="NBA-T", game="NBA_G1", sport="NBA", league="NBA")
        for i, bid in enumerate([7900, 8000, 8100, 8200])
    ]
    assert pull(draft_from_combo(up), **only_up)["n"] == 1
    assert pull(draft_from_combo(down), **only_up)["n"] == 0


def test_every_combo_is_classified():
    ids = [c.combo_id for c in all_combos()]
    assert len(ids) == len(set(ids))
    assert DIRECTION_FAMILIES <= set(ENTRY_FAMILIES)
