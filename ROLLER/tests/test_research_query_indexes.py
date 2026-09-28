"""Observation indexes reproduce Phase 1 detectors. Fail closed on stale/corrupt."""

from __future__ import annotations

from pathlib import Path

import pytest

from roller.research_query.compiler import compile_question
from roller.research_query.entry_engine import crossings, observe_entry
from roller.research_query.execute import execute_compiled
from roller.research_query.facts import TradableIndex
from roller.research_query.indexes.builder import build_index, index_root
from roller.research_query.indexes.manifest import MANIFEST_NAME, file_sha256, read_manifest, write_manifest
from roller.research_query.indexes.reader import IndexUnavailable, open_index
from roller.research_query.indexes.transitions import rows_from_index
from roller.research_query.models import (
    EntryCondition,
    EntryOp,
    PathCondition,
    PathOp,
    ResearchQuestion,
    TerminalOutcome,
    TouchOrdinal,
    Universe,
)
from roller.research_query.operations import first_cross
from roller.research_query.planner import plan_query
from tests.test_research_query_engine import _q, _series, _snap_quarter


def _question() -> ResearchQuestion:
    return ResearchQuestion(
        universe=Universe(
            sports=("basketball",),
            leagues=("NBA",),
            seasons=("2025-26",),
            markets=("kalshi",),
            market_data=("candles",),
        ),
        entry_conditions=(
            EntryCondition(
                id="e1",
                ordinal=TouchOrdinal.FIRST_TOUCH,
                price_e4=8000,
                operation=EntryOp.CROSS,
            ),
        ),
        path_conditions=(),
        terminal=TerminalOutcome.BOTH,
    )


def test_transitions_match_crossings():
    candles = _series([7900, 8000, 8000, 8000, 7900, 8000])
    index = TradableIndex.build({"T-A": candles})
    trans = rows_from_index(index)
    bars = index.bars["T-A"]
    hits = crossings(bars, 8000)
    via_a = [
        t
        for t in trans
        if int(t["prior_e4"]) < 8000 <= int(t["current_e4"])
    ]
    assert len(hits) == 2
    assert len(via_a) == 2
    assert first_cross(bars, 8000).ts == hits[0].ts


def test_index_reproduces_observe_entry(tmp_path, monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    payloads = {
        "T-A": _series([7900, 8100, 7900], ticker="T-A", game="G-A"),
        "T-B": _series([8100, 7900], ticker="T-B", game="G-B"),
    }
    man = build_index(
        league="NBA",
        season="2025-26",
        ticker_payloads=payloads,
        pbp_by_game={},
        markets_by_ticker={"T-A": {"result": "yes"}},
        dest=tmp_path,
    )
    assert man.ticker_count == 2
    idx = open_index(_question(), dest=tmp_path, expected_dataset_version="injected")
    q = _question()
    scan_tickers = set()
    indexed_tickers = set()
    for ticker, candles in payloads.items():
        ev, _ = observe_entry(candles, q.entry_conditions[0], snap_fn=_snap_quarter("Q3"))
        if ev:
            scan_tickers.add(ticker)
        ev2, _ = observe_entry(
            [],
            q.entry_conditions[0],
            snap_fn=_snap_quarter("Q3"),
            precomputed=idx.bars.precomputed(ticker),
        )
        if ev2:
            indexed_tickers.add(ticker)
    assert scan_tickers == indexed_tickers == {"T-A", "T-B"}


def test_stale_checksum_fail_closed(tmp_path):
    payloads = {"T-A": _series([7900, 8100], ticker="T-A")}
    build_index(
        league="NBA",
        season="2025-26",
        ticker_payloads=payloads,
        dest=tmp_path,
    )
    bars = tmp_path / "bars.parquet"
    bars.write_bytes(bars.read_bytes() + b"\x00")
    with pytest.raises(IndexUnavailable):
        open_index(_question(), dest=tmp_path, expected_dataset_version="injected")


def test_dataset_version_mismatch_fail_closed(tmp_path):
    build_index(
        league="NBA",
        season="2025-26",
        ticker_payloads={"T-A": _series([7900, 8000])},
        dest=tmp_path,
    )
    with pytest.raises(IndexUnavailable):
        open_index(_question(), dest=tmp_path, expected_dataset_version="other")


def test_planner_absent_is_full_scan(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    compiled = compile_question(_q(TouchOrdinal.SECOND_TOUCH, 8000))
    plan = plan_query(compiled)
    assert plan.execution_mode in {"full_scan", "indexed", "unavailable"}
    if plan.execution_mode == "full_scan":
        assert plan.reason in {"index_absent", "not_generic"}


def test_indexed_execute_matches_scan(tmp_path, monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    payloads = {
        "T-A": _series([7900, 8000, 4000], ticker="T-A", game="G-A"),
        "T-B": _series([7000, 7100], ticker="T-B", game="G-B"),
    }
    q = ResearchQuestion(
        universe=_question().universe,
        entry_conditions=(
            EntryCondition(id="e1", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=8000),
        ),
        path_conditions=(PathCondition(id="p", op=PathOp.REACH, price_e4=4000),),
        terminal=TerminalOutcome.BOTH,
    )
    compiled = compile_question(q)
    scan = execute_compiled(
        compiled,
        ticker_payloads=payloads,
        snap_fn=_snap_quarter("Q3"),
        markets_by_ticker={"T-A": {"result": "yes"}},
    )
    build_index(
        league="NBA",
        season="2025-26",
        ticker_payloads=payloads,
        markets_by_ticker={"T-A": {"result": "yes"}},
        dest=tmp_path,
    )
    idx_scan = {
        r["ticker"] for r in scan["population"]["trades"]
    }
    from roller.research_query.indexes.reader import open_index
    from roller.research_query.planner import bundle_from_index

    idx = open_index(q, dest=tmp_path, expected_dataset_version="injected")
    bundle = bundle_from_index(idx)
    indexed = execute_compiled(
        compiled,
        ticker_payloads=bundle["ticker_payloads"],
        pbp_by_game=bundle["pbp_by_game"],
        markets_by_ticker=bundle["markets_by_ticker"],
        snap_fn=_snap_quarter("Q3"),
        tradable_index=bundle["tradable_index"],
    )
    assert idx_scan == {"T-A"}
    assert {r["ticker"] for r in indexed["population"]["trades"]} == idx_scan
    assert indexed["summary"]["population_n"] == scan["summary"]["population_n"]


def test_snaps_round_trip_score_facts(tmp_path):
    from roller.research_query.indexes.snaps import read_snaps, write_snaps

    write_snaps(
        tmp_path / "pbp_events.parquet",
        {
            "MLB_1": [
                {
                    "internal_game_id": "MLB_1",
                    "event_timestamp": "2026-04-02T17:01:00Z",
                    "event_number": 12,
                    "home_score": 3,
                    "away_score": 2,
                    "inning": 4,
                    "half": "T",
                    "period": "T4",
                }
            ]
        },
    )
    got = read_snaps(tmp_path / "pbp_events.parquet")
    ev = got["MLB_1"][0]
    assert ev["home_score"] == 3
    assert ev["away_score"] == 2
    assert ev["inning"] == 4
    assert ev["event_number"] == 12


def test_last_trade_bars_allow_null_ask(tmp_path):
    from datetime import datetime, timezone

    from roller.research_query.entry_engine import TradableBar
    from roller.research_query.indexes.bars import read_bars, write_bars
    from roller.research_query.models import BASIS_LAST_TRADE

    ts = datetime(2025, 6, 18, 16, 0, tzinfo=timezone.utc)
    bar = TradableBar(
        ts=ts,
        bid=7500,
        ask=None,
        volume=3,
        ticker="KX-LT",
        game_id="G-LT",
        raw={},
        basis=BASIS_LAST_TRADE,
    )
    index = TradableIndex(bars={"KX-LT": [bar]}, skipped={"KX-LT": 0}, basis=BASIS_LAST_TRADE)
    write_bars(tmp_path / "bars.parquet", index)
    got = read_bars(tmp_path / "bars.parquet")
    assert got.basis == BASIS_LAST_TRADE
    assert got.bars["KX-LT"][0].ask is None
    assert got.bars["KX-LT"][0].bid == 7500


def test_read_bars_treats_nan_volume_as_missing(tmp_path):
    from datetime import datetime, timezone

    from roller.research_query.entry_engine import TradableBar
    from roller.research_query.indexes.bars import read_bars, write_bars
    from roller.research_query.models import BASIS_TRADABLE

    ts = datetime(2025, 6, 18, 16, 0, tzinfo=timezone.utc)
    present = TradableBar(
        ts=ts,
        bid=8000,
        ask=8100,
        volume=4,
        ticker="KX-VOL",
        game_id="G-VOL",
        raw={},
        basis=BASIS_TRADABLE,
    )
    missing = TradableBar(
        ts=ts,
        bid=8000,
        ask=8100,
        volume=None,
        ticker="KX-VOL",
        game_id="G-VOL",
        raw={},
        basis=BASIS_TRADABLE,
    )
    index = TradableIndex(
        bars={"KX-VOL": [present, missing]},
        skipped={"KX-VOL": 0},
        basis=BASIS_TRADABLE,
    )
    write_bars(tmp_path / "bars.parquet", index)
    got = read_bars(tmp_path / "bars.parquet")
    assert got.bars["KX-VOL"][0].volume == 4
    assert got.bars["KX-VOL"][1].volume is None


def test_tennis_tour_filter_never_groups_wta_into_atp():
    from roller.research_query.availability import LeagueScope
    from roller.research_query.execute import _scope_keeps_record

    atp = LeagueScope(league="ATP", sport="ATP", season="2025-2026")
    wta = LeagueScope(league="WTA", sport="WTA", season="2025-2026")
    assert _scope_keeps_record({"ticker": "KXATPMATCH-25JUN18AAABBB-AAA"}, atp) is True
    assert _scope_keeps_record({"ticker": "KXWTAMATCH-25JUN18AAABBB-AAA"}, atp) is False
    assert _scope_keeps_record({"ticker": "KXWTAMATCH-25JUN18AAABBB-AAA"}, wta) is True
    assert _scope_keeps_record({"ticker": "NOPE"}, atp) is False


def test_planner_last_trade_is_not_forced_full_scan_when_index_present(tmp_path, monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    payloads = {"T-A": _series([7900, 8000], ticker="T-A", game="G-A")}
    q = ResearchQuestion(
        universe=Universe(
            sports=("baseball",),
            leagues=("MLB",),
            seasons=("2025-26",),
            markets=("kalshi",),
            market_data=("last_trade",),
        ),
        entry_conditions=(EntryCondition(id="e1", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=7500),),
        path_conditions=(),
        terminal=TerminalOutcome.BOTH,
    )
    compiled = compile_question(q)
    build_index(
        league="MLB",
        season="2025-26",
        ticker_payloads=payloads,
        dest=tmp_path,
        basis="LAST_TRADE_PRINT",
    )
    plan = plan_query(compiled, dest=tmp_path, dataset_version="injected")
    assert plan.execution_mode == "indexed"
    assert plan.reason is None


def test_combined_union_indexes_do_not_prefix_distinct_tickers():
    from roller.research_query.indexes.manifest import IndexManifest
    from roller.research_query.indexes.reader import ObservationIndex, union_observation_indexes

    def _idx(sport: str, ticker: str) -> ObservationIndex:
        man = IndexManifest(
            index_version="rq_index_v1.0.0",
            dataset_version="x",
            code_version="c",
            operation_semantics_version="1",
            league=sport,
            season="2025-2026",
            sport=sport,
            built_at_utc="2026-09-11T00:00:00Z",
            git_sha=None,
            source_paths=[],
            files={},
            ticker_count=1,
            game_count=1,
            bar_rows=1,
            transition_rows=0,
            settlement_rows=0,
        )
        bars = TradableIndex.build({ticker: _series([7900, 8000], ticker=ticker, game=f"G-{sport}")})
        return ObservationIndex(
            manifest=man,
            bars=bars,
            transitions=[],
            pbp_by_game={},
            markets_by_ticker={},
            universe=[],
            root=Path("."),
        )

    merged = union_observation_indexes([_idx("ATP", "KXATPMATCH-A"), _idx("WTA", "KXWTAMATCH-B")])
    assert set(merged.bars.bars) == {"KXATPMATCH-A", "KXWTAMATCH-B"}


def test_corrupt_manifest_rewritten_checksum(tmp_path):
    build_index(
        league="NBA",
        season="2025-26",
        ticker_payloads={"T-A": _series([7900, 8000])},
        dest=tmp_path,
    )
    man = read_manifest(tmp_path / MANIFEST_NAME)
    man.files["bars.parquet"] = "0" * 64
    write_manifest(tmp_path / MANIFEST_NAME, man)
    assert file_sha256(tmp_path / "bars.parquet") != "0" * 64
    with pytest.raises(IndexUnavailable):
        open_index(_question(), dest=tmp_path, expected_dataset_version="injected")


def test_index_root_atp_wta_share_tennis_tree():
    from roller.config import RollerConfig
    from roller.research_query.models import BASIS_LAST_TRADE, BASIS_TRADABLE

    cfg = RollerConfig()
    atp = index_root(cfg, "ATP", "2025-2026", league="ATP", basis=BASIS_TRADABLE)
    wta = index_root(cfg, "WTA", "2025-2026", league="WTA", basis=BASIS_TRADABLE)
    atp_lt = index_root(cfg, "ATP", "2025-2026", league="ATP", basis=BASIS_LAST_TRADE)
    assert "data/tennis/2025_2026" in str(atp)
    assert "data/tennis/2025_2026" in str(wta)
    assert atp != wta
    assert atp.parent.name == "ATP"
    assert wta.parent.name == "WTA"
    assert atp.name == "tradable"
    assert atp_lt.name == "last_trade"
    assert atp_lt != atp


def test_single_league_fingerprints_match_scope():
    from roller.research_query.availability import LeagueScope
    from roller.research_query.dataset_version import dataset_fingerprint, scope_fingerprint
    from roller.research_query.indexes.builder import _question_for

    q = _question_for("NBA", "2025-2026")
    scope = LeagueScope(league="NBA", sport="NBA", season="2025-2026")
    assert dataset_fingerprint(q) == scope_fingerprint(scope)


def test_combined_plan_indexed_when_both_scope_indexes_exist(monkeypatch):
    from roller.research_query.compiler import compile_draft
    from roller.research_query.indexes.manifest import IndexManifest
    from roller.research_query.indexes.reader import ObservationIndex
    from tests.test_combined_league_union import _combined_draft

    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)

    def fake_open(scope, **_kwargs):
        man = IndexManifest(
            index_version="rq_index_v1.0.0",
            dataset_version="x",
            code_version="c",
            operation_semantics_version="1",
            league=scope.league,
            season=scope.season,
            sport=scope.sport,
            built_at_utc="2026-09-11T00:00:00Z",
            git_sha=None,
            source_paths=[],
            files={},
            ticker_count=1,
            game_count=1,
            bar_rows=1,
            transition_rows=0,
            settlement_rows=0,
        )
        ticker = f"{scope.sport}-T"
        bars = TradableIndex.build({ticker: _series([7900, 8000], ticker=ticker, game=f"G-{scope.sport}")})
        return ObservationIndex(
            manifest=man,
            bars=bars,
            transitions=[],
            pbp_by_game={},
            markets_by_ticker={},
            universe=[{"ticker": ticker, "game_id": f"G-{scope.sport}", "league": scope.league}],
            root=Path("."),
        )

    monkeypatch.setattr("roller.research_query.planner.open_scope_index", fake_open)
    compiled = compile_draft(_combined_draft())
    plan = plan_query(compiled)
    assert plan.execution_mode == "indexed"
    assert set(plan.index.bars.bars) == {"NBA-T", "NCAAB-T"}
