from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from roller.admin import load_dataset, load_identity
from roller.config import RollerConfig
from roller.maintenance.update import update_sport


SRC = Path(__file__).resolve().parents[1]


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n")


def _game(sport_prefix, ticker, date, start, home, away, home_name, away_name, gid):
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


@pytest.fixture
def expand_env(tmp_path: Path) -> Path:
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
    (root / "reports" / "integrity").mkdir(parents=True)
    (root / "reports" / "daily_updates").mkdir(parents=True)
    (root / "config" / "sources.json").write_text(
        json.dumps({"warehouse_root": str(data), "fetch_clis": {}, "pbp_ingest": {}}) + "\n"
    )

    wnba = data / "WNBA" / "2025-2026" / "warehouse"
    g25 = "KXWNBAGAME-25JUN10NYDAL"
    g26 = "KXWNBAGAME-26JUN10LALV"
    _write_json(
        wnba / "normalized" / "wnba" / "games" / "wnba_games.json",
        [
            _game("WNBA", g25, "2025-06-10", "2025-06-10T19:00:00Z", "Dallas", "New York", "Dallas", "New York", "w1"),
            _game("WNBA", g26, "2026-06-10", "2026-06-10T19:00:00Z", "Las Vegas", "Los Angeles", "Las Vegas", "Los Angeles", "w2"),
        ],
    )
    _write_json(
        wnba / "normalized" / "wnba" / "pbp" / "game_crosswalk.json",
        [
            {
                "event_id": g25,
                "event_ticker": g25,
                "game_date": "2025-06-10",
                "home_team_code": "DAL",
                "away_team_code": "NY",
                "espn_game_id": "401850001",
                "match_status": "MATCHED",
                "match_method": "test",
            },
            {
                "event_id": g26,
                "event_ticker": g26,
                "game_date": "2026-06-10",
                "home_team_code": "LV",
                "away_team_code": "LA",
                "espn_game_id": "401850002",
                "match_status": "MATCHED",
                "match_method": "test",
            },
        ],
    )
    for espn_id, date, wall, hs, as_ in (
        ("401850001", "2025-06-10", "2025-06-10T21:00:00Z", 80, 75),
        ("401850002", "2026-06-10", "2026-06-10T21:00:00Z", 90, 88),
    ):
        _write_json(
            wnba / "normalized" / "wnba" / "pbp" / "plays" / f"{espn_id}.json",
            {
                "espn_game_id": espn_id,
                "plays": [
                    {
                        "sequenceNumber": "1",
                        "wallclock": wall,
                        "period": 4,
                        "clock": "0:00",
                        "homeScore": hs,
                        "awayScore": as_,
                        "type_text": "end",
                        "text": "end",
                    }
                ],
            },
        )

    ncaab = data / "NCAAB" / "2025-2026" / "warehouse"
    p5 = "KXNCAAMBGAME-25DEC01DUKEUNC"
    non = "KXNCAAMBGAME-25DEC01TLSUNM"
    _write_json(
        ncaab / "normalized" / "ncaab" / "games" / "ncaab_games.json",
        [
            _game("NCAAB", p5, "2025-12-01", None, "UNC", "DUKE", "North Carolina", "Duke", "n1"),
            _game("NCAAB", non, "2025-12-01", None, "UNM", "TLSA", "New Mexico", "Tulsa", "n2"),
        ],
    )
    _write_json(
        ncaab / "normalized" / "ncaab" / "pbp" / "game_crosswalk.json",
        [
            {
                "event_id": p5,
                "event_ticker": p5,
                "game_date": "2025-12-01",
                "home_team_code": "UNC",
                "away_team_code": "DUKE",
                "espn_game_id": "401860001",
                "match_status": "MATCHED",
                "match_method": "test",
            },
            {
                "event_id": non,
                "event_ticker": non,
                "game_date": "2025-12-01",
                "home_team_code": "UNM",
                "away_team_code": "TLSA",
                "espn_game_id": "",
                "match_status": "UNMATCHED",
                "match_method": "UNMATCHED",
            },
        ],
    )
    _write_json(
        ncaab / "normalized" / "ncaab" / "pbp" / "plays" / "401860001.json",
        {
            "espn_game_id": "401860001",
            "plays": [
                {
                    "sequenceNumber": "1",
                    "wallclock": "2025-12-01T22:00:00Z",
                    "period": 2,
                    "clock": "0:00",
                    "homeScore": 70,
                    "awayScore": 68,
                    "type_text": "end",
                    "text": "end",
                }
            ],
        },
    )
    return root


def test_wnba_campaigns_and_stable_codes(expand_env: Path):
    cfg = RollerConfig(expand_env)
    update_sport(cfg, "WNBA", "2025", include_pbp=True, include_candles=False)
    update_sport(cfg, "WNBA", "2026", include_pbp=True, include_candles=False)
    ident = load_identity(cfg)
    ids = set(ident["internal_game_id"])
    assert "WNBA_20250610_NY_DAL" in ids
    assert "WNBA_20260610_LA_LV" in ids
    g25 = load_dataset(cfg, "WNBA", "2025", "games")
    g26 = load_dataset(cfg, "WNBA", "2026", "games")
    assert list(g25["internal_game_id"]) == ["WNBA_20250610_NY_DAL"]
    assert list(g26["internal_game_id"]) == ["WNBA_20260610_LA_LV"]
    assert str(g25.iloc[0]["final_home_score"]) == "80"


def test_ncaab_identity_includes_non_p5_features_default_p5(expand_env: Path):
    cfg = RollerConfig(expand_env)
    update_sport(cfg, "NCAAB", "2025-2026", include_pbp=True, include_candles=False)
    ident = load_identity(cfg)
    assert "NCAAB_20251201_DUKE_UNC" in set(ident["internal_game_id"])
    assert "NCAAB_20251201_TLSA_UNM" in set(ident["internal_game_id"])
    games = load_dataset(cfg, "NCAAB", "2025-2026", "games")
    p5 = games[games["internal_game_id"] == "NCAAB_20251201_DUKE_UNC"].iloc[0]
    other = games[games["internal_game_id"] == "NCAAB_20251201_TLSA_UNM"].iloc[0]
    assert str(p5["p5_vs_p5"]) == "1"
    assert str(other["p5_vs_p5"]) == "0"
    assert p5["scheduled_start"] == ""
    assert p5["availability_quality"] == "CONSERVATIVE_PROXY"
    feats = load_dataset(cfg, "NCAAB", "2025-2026", "team_features")
    assert set(feats["internal_game_id"]) == {"NCAAB_20251201_DUKE_UNC"}
