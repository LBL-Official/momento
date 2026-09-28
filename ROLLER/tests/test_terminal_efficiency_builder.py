"""Score/market path fixtures and reconciliation. Not an ML test."""

from __future__ import annotations

from roller.base_terminal_efficiency.builder import observations_for_ticker
from roller.base_terminal_efficiency.empirical import measure, partition, range_pred
from roller.base_terminal_efficiency.market import market_path_metrics
from roller.base_terminal_efficiency.score import score_state
from roller.base_terminal_efficiency.versions import ENTRY_PRICE_DEFINITION


def _candle(minute: int, bid: int, *, ticker="T-HOME", game="G1"):
    return {
        "available_at": f"2025-12-20T20:{minute:02d}:00Z",
        "yes_bid_close": bid,
        "yes_ask_close": bid + 400,
        "volume": 10,
        "ticker": ticker,
        "internal_game_id": game,
        "team_side": "home",
    }


def _pbp_path(scores: list[int], *, away: int = 0):
    rows = []
    for i, s in enumerate(scores):
        rows.append(
            {
                "internal_game_id": "G1",
                "event_number": i + 1,
                "event_timestamp": f"2025-12-20T20:{i:02d}:00Z",
                "available_at": f"2025-12-20T20:{i:02d}:00Z",
                "period": 1,
                "clock": "10:00",
                "home_score": s,
                "away_score": away,
            }
        )
    return rows


def test_same_entry_score_different_score_paths():
    a = score_state(_pbp_path([0, 10, 20]), "2025-12-20T20:02:30Z", team_side="home")
    b = score_state(_pbp_path([0, 5, 20]), "2025-12-20T20:02:30Z", team_side="home")
    assert a["team_points"] == b["team_points"] == 20
    assert a["score_path_team"] != b["score_path_team"]
    assert a["score_path_team"] == (0, 10, 20)
    assert b["score_path_team"] == (0, 5, 20)


def test_same_entry_price_different_market_paths():
    up = market_path_metrics([5000, 6000, 7000, 8000])
    down = market_path_metrics([9000, 8500, 8200, 8000])
    assert up["signed_price_displacement_e4"] == 3000
    assert down["signed_price_displacement_e4"] == -1000
    assert up["cumulative_price_travel_e4"] != down["cumulative_price_travel_e4"]


def test_displacement_zero_travel_twenty():
    m = market_path_metrics([5000, 6000, 5000])
    assert m["signed_price_displacement_e4"] == 0
    assert m["cumulative_price_travel_e4"] == 2000  # 10¢ + 10¢ in E4 = 1000+1000


def test_insufficient_volatility_unavailable_not_zero():
    m = market_path_metrics([5000, 6000])
    assert m["entry_price_volatility"] is None
    s = score_state(_pbp_path([0, 10, 20]), "2025-12-20T20:02:30Z", team_side="home")
    assert s["team_score_volatility"] is None


def test_three_increments_have_score_vol():
    s = score_state(_pbp_path([0, 2, 5, 9]), "2025-12-20T20:03:30Z", team_side="home")
    assert s["team_score_volatility"] is not None
    assert s["team_score_volatility"] != 0


def test_builder_reconciles_price_and_score():
    # Candle close at :03 is strictly after PBP available_at :02 (I(t) half-open).
    candles = [_candle(i + 1, bid) for i, bid in enumerate([5000, 6000, 5000])]
    pbp = _pbp_path([0, 10, 20])
    rows, path = observations_for_ticker(candles, pbp)
    assert rows
    last = rows[-1]
    assert last.entry_price_e4 == 5000
    assert last.entry_price_definition == ENTRY_PRICE_DEFINITION
    assert last.team_points == 20
    assert last.opponent_points == 0
    assert last.total_points == 20
    assert last.point_differential == 20
    assert last.signed_price_displacement_e4 == 0
    assert last.cumulative_price_travel_e4 == 2000
    assert last.entry_price_volatility is not None
    assert path["ticker"] == "T-HOME"
    assert [b["yes_bid_close"] for b in path["bars"]] == [5000, 6000, 5000]


def test_stale_manifest_is_data_required(tmp_path):
    from roller.base_terminal_efficiency.manifest import (
        BaseTeManifest,
        validate_against_sources,
        write_manifest,
        load_manifest,
    )
    from roller.base_terminal_efficiency.models import DATA_REQUIRED
    from roller.base_terminal_efficiency.versions import CODE_VERSION, SCHEMA_VERSION, SEMANTICS_VERSION

    man = BaseTeManifest(
        schema_version=SCHEMA_VERSION,
        semantics_version=SEMANTICS_VERSION,
        code_version=CODE_VERSION,
        dataset_version="abc",
        git_sha=None,
        build_timestamp_utc="2026-01-01T00:00:00Z",
        league="NBA",
        season="2025-2026",
        source_paths=["/tmp/x"],
        source_checksums={"/tmp/x": "old"},
        observation_count=1,
        game_count=1,
        ticker_count=1,
        coverage_start=None,
        coverage_end=None,
    )
    p = tmp_path / "manifest.json"
    write_manifest(p, man)
    loaded = load_manifest(p)
    assert not isinstance(loaded, str)
    assert validate_against_sources(loaded, {"/tmp/x": "new"}) == DATA_REQUIRED
    assert load_manifest(tmp_path / "missing.json") == DATA_REQUIRED


def test_empirical_counts_no_alpha():
    rows = [
        {"terminal_outcome": "YES", "entry_price_e4": 8000, "point_differential": 5},
        {"terminal_outcome": "MISSING", "entry_price_e4": 7500, "point_differential": 1},
    ]
    exits = [{"exit_outcome": "WIN"}, {"exit_outcome": "AMBIGUOUS"}]
    m = measure(rows, exit_results=exits)
    assert m["n_entry"] == 2
    assert m["n_win_exit"] == 1
    assert m["n_ambiguous"] == 1
    assert m["n_terminal_yes"] == 1
    assert m["n_terminal_missing"] == 1
    assert "alpha" not in m
    part = partition(rows, range_pred("entry_price_e4", 7500, 8000), exit_results=exits)
    assert part["n_entry"] == 2
