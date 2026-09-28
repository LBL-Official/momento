from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

UTC = timezone.utc
SRC = Path(__file__).resolve().parents[1]


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n")


def _game(ticker, date, start, home, away, home_name, away_name, gid):
    return {
        "game_id": gid,
        "event_id": ticker,
        "event_ticker": ticker,
        "season": "2025-2026",
        "season_phase": "REGULAR_SEASON",
        "phase_method": "test",
        "game_date": date,
        "scheduled_start": start,
        "home_team": home_name,
        "away_team": away_name,
        "home_team_code": home,
        "away_team_code": away,
        "home_market_ticker": f"{ticker}-{home}",
        "away_market_ticker": f"{ticker}-{away}",
        "market_tickers": [f"{ticker}-{home}", f"{ticker}-{away}"],
        "market_count": 2,
        "event_status": "finalized",
        "settlement_status": "yes,no",
        "event_title": f"{away} at {home}",
        "event_subtitle": f"{away} at {home}",
        "source": "test",
        "schema_version": "test",
    }


def _pbp_live(nba_id: str, actions: list[dict]) -> dict:
    return {"meta": {}, "game": {"gameId": nba_id, "actions": actions}}


def _action(n, ts, period, clock, home, away, typ="shot", desc=""):
    return {
        "actionNumber": n,
        "timeActual": ts,
        "period": period,
        "clock": clock,
        "scoreHome": str(home),
        "scoreAway": str(away),
        "actionType": typ,
        "description": desc,
        "teamTricode": "LAL",
        "possession": 1,
    }


def _box(nba_id, tip, home_score, away_score, home="BOS", away="LAL"):
    return {
        "meta": {},
        "boxScoreSummary": {
            "gameId": nba_id,
            "gameTimeUTC": tip,
            "homeTeam": {"teamTricode": home, "score": home_score},
            "awayTeam": {"teamTricode": away, "score": away_score},
        },
    }


@pytest.fixture
def roller_env(tmp_path: Path) -> Path:
    root = tmp_path / "ROLLER"
    data = tmp_path / "Data"
    shutil.copytree(SRC / "config", root / "config")
    shutil.copy(SRC / "roller.json", root / "roller.json")
    (root / "meta").mkdir()
    feat_reg = SRC / "meta" / "feature_registry.json"
    if feat_reg.is_file():
        shutil.copy(feat_reg, root / "meta" / "feature_registry.json")
    meas_reg = SRC / "meta" / "measurement_registry.json"
    if meas_reg.is_file():
        shutil.copy(meas_reg, root / "meta" / "measurement_registry.json")
    fund_reg = SRC / "meta" / "fundamental_registry.json"
    if fund_reg.is_file():
        shutil.copy(fund_reg, root / "meta" / "fundamental_registry.json")
    greek_v4b_reg = SRC / "meta" / "greek_v4b_registry.json"
    if greek_v4b_reg.is_file():
        shutil.copy(greek_v4b_reg, root / "meta" / "greek_v4b_registry.json")
    greek_v4c_reg = SRC / "config" / "greek_v4c_registry.json"
    if greek_v4c_reg.is_file():
        shutil.copy(greek_v4c_reg, root / "config" / "greek_v4c_registry.json")
    (root / "reports" / "integrity").mkdir(parents=True)
    (root / "reports" / "daily_updates").mkdir(parents=True)
    (root / "config" / "sources.json").write_text(
        json.dumps({"warehouse_root": str(data), "fetch_clis": {}, "pbp_ingest": {}}) + "\n"
    )

    wh = data / "NBA" / "2025-2026" / "warehouse"
    g1 = "KXNBAGAME-25DEC10LALBOS"
    g2 = "KXNBAGAME-25DEC15BOSLAL"
    g3 = "KXNBAGAME-25DEC20LALBOS"
    g4a = "KXNBAGAME-25DEC25LALBOSA"
    g4b = "KXNBAGAME-25DEC25LALBOSB"
    unmatched = "KXNBAGAME-25DEC28UNKUNK"

    games = [
        _game(g1, "2025-12-10", "2025-12-10T19:00:00Z", "BOS", "LAL", "Boston", "Los Angeles", "id1"),
        _game(g2, "2025-12-15", "2025-12-15T19:00:00Z", "LAL", "BOS", "Los Angeles", "Boston", "id2"),
        _game(g3, "2025-12-20", "2025-12-20T19:00:00Z", "BOS", "LAL", "Boston", "Los Angeles", "id3"),
        _game(g4a, "2025-12-25", "2025-12-25T17:00:00Z", "BOS", "LAL", "Boston", "Los Angeles", "id4a"),
        _game(g4b, "2025-12-25", "2025-12-25T21:00:00Z", "BOS", "LAL", "Boston", "Los Angeles", "id4b"),
        _game(unmatched, "2025-12-28", "2025-12-28T19:00:00Z", "BOS", "NYK", "Boston", "New York", "idU"),
    ]
    # unmatched has no home/away tickers? keep tickers but UNMATCHED crosswalk
    _write_json(wh / "normalized" / "nba" / "games" / "nba_games.json", games)

    xwalk = [
        {
            "event_id": g1,
            "event_ticker": g1,
            "game_date": "2025-12-10",
            "home_team_code": "BOS",
            "away_team_code": "LAL",
            "nba_game_id": "0022500001",
            "match_status": "MATCHED",
            "match_method": "game_date+team_pair",
        },
        {
            "event_id": g2,
            "event_ticker": g2,
            "game_date": "2025-12-15",
            "home_team_code": "LAL",
            "away_team_code": "BOS",
            "nba_game_id": "0022500002",
            "match_status": "MATCHED",
            "match_method": "game_date+team_pair",
        },
        {
            "event_id": g3,
            "event_ticker": g3,
            "game_date": "2025-12-20",
            "home_team_code": "BOS",
            "away_team_code": "LAL",
            "nba_game_id": "0022500003",
            "match_status": "MATCHED",
            "match_method": "game_date+team_pair",
        },
        {
            "event_id": g4a,
            "event_ticker": g4a,
            "game_date": "2025-12-25",
            "home_team_code": "BOS",
            "away_team_code": "LAL",
            "nba_game_id": "0022500004",
            "match_status": "MATCHED",
            "match_method": "game_date+team_pair",
        },
        {
            "event_id": g4b,
            "event_ticker": g4b,
            "game_date": "2025-12-25",
            "home_team_code": "BOS",
            "away_team_code": "LAL",
            "nba_game_id": "0022500005",
            "match_status": "MATCHED",
            "match_method": "game_date+team_pair",
        },
        {
            "event_id": unmatched,
            "event_ticker": unmatched,
            "game_date": "2025-12-28",
            "home_team_code": "BOS",
            "away_team_code": "NYK",
            "nba_game_id": "",
            "match_status": "UNMATCHED",
            "match_method": "UNMATCHED",
        },
    ]
    _write_json(wh / "normalized" / "nba" / "pbp" / "game_crosswalk.json", xwalk)

    sequences = {
        "0022500001": ("2025-12-10T19:00:00Z", 100, 110, "BOS", "LAL"),  # away LAL wins
        "0022500002": ("2025-12-15T19:00:00Z", 99, 105, "LAL", "BOS"),  # away BOS wins
        "0022500003": ("2025-12-20T19:00:00Z", 107, 108, "BOS", "LAL"),  # away LAL wins
        "0022500004": ("2025-12-25T17:00:00Z", 90, 91, "BOS", "LAL"),
        "0022500005": ("2025-12-25T21:00:00Z", 88, 80, "BOS", "LAL"),
    }
    # box home_score, away_score
    boxes = {
        "0022500001": (100, 110),
        "0022500002": (99, 105),
        "0022500003": (107, 108),
        "0022500004": (90, 91),
        "0022500005": (88, 80),
    }
    for nba_id, (tip, hs, as_, home, away) in sequences.items():
        hscore, ascore = boxes[nba_id]
        _write_json(
            wh / "raw" / "nba_stats" / "boxscore_summary" / f"{nba_id}.json",
            _box(nba_id, tip, hscore, ascore, home=home, away=away),
        )
        if nba_id == "0022500003":
            actions = [
                _action(1, "2025-12-20T20:00:00Z", 1, "PT12M00.00S", 0, 0, "period", "start"),
                _action(2, "2025-12-20T20:13:02Z", 3, "PT06M32.00S", 10, 8, "shot", "make"),
                _action(3, "2025-12-20T20:14:00Z", 3, "PT06M00.00S", 12, 8, "shot", "make"),
                _action(4, "2025-12-20T22:00:00Z", 4, "PT00M00.00S", 107, 108, "period", "end"),
            ]
        else:
            actions = [
                _action(1, tip, 1, "PT12M00.00S", 0, 0),
                _action(2, tip.replace("T19:", "T22:"), 4, "PT00M00.00S", hscore, ascore, "period", "end"),
            ]
        _write_json(wh / "raw" / "nba_stats" / "pbp_live" / f"{nba_id}.json", _pbp_live(nba_id, actions))

    candle_dir = wh / "normalized" / "nba" / "candles_1m" / "month=2025-12"
    candle_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "ticker": f"{g3}-BOS",
            "event_id": g3,
            "game_id": "id3",
            "end_period_ts": 1766261610,
            "start_time": datetime(2025, 12, 20, 20, 12, tzinfo=UTC),
            "end_time": datetime(2025, 12, 20, 20, 13, 30, tzinfo=UTC),
            "yes_bid_open_e4": 5000,
            "yes_bid_high_e4": 5100,
            "yes_bid_low_e4": 4900,
            "yes_bid_close_e4": 5050,
            "yes_ask_open_e4": 5200,
            "yes_ask_high_e4": 5300,
            "yes_ask_low_e4": 5100,
            "yes_ask_close_e4": 5150,
            "volume_hundredths": 10,
        },
        {
            "ticker": f"{g3}-BOS",
            "event_id": g3,
            "game_id": "id3",
            "end_period_ts": 1766261670,
            "start_time": datetime(2025, 12, 20, 20, 14, tzinfo=UTC),
            "end_time": datetime(2025, 12, 20, 20, 15, 0, tzinfo=UTC),
            "yes_bid_open_e4": 5050,
            "yes_bid_high_e4": 5200,
            "yes_bid_low_e4": 5000,
            "yes_bid_close_e4": 5180,
            "yes_ask_open_e4": 5150,
            "yes_ask_high_e4": 5400,
            "yes_ask_low_e4": 5150,
            "yes_ask_close_e4": 5300,
            "volume_hundredths": 12,
        },
    ]
    pd.DataFrame(rows).to_parquet(candle_dir / f"{g3}-BOS.parquet", index=False)
    return root
