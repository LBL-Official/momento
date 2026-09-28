from __future__ import annotations

from pathlib import Path

from roller.canonical.identity_build import build_identity
from roller.config import RollerConfig
from roller.identity import assign_internal_ids, base_game_id, id_token
from roller.ingest.games import infer_market_tickers
from roller.maintenance.update import update_sport


def test_base_id_uses_codes_not_names():
    assert base_game_id("NBA", "2025-12-19", "LAL", "BOS") == "NBA_20251219_LAL_BOS"
    assert id_token("Nigeria National Team") == "NigeriaNationalTeam"
    assert id_token("L-MD") == "L-MD"
    assert base_game_id("WNBA", "2026-05-02", "Nigeria National Team", "IND") == (
        "WNBA_20260502_NigeriaNationalTeam_IND"
    )
    assert base_game_id("NCAAB", "2025-11-19", "L-MD", "DUQ") != base_game_id(
        "NCAAB", "2025-11-19", "LMD", "DUQ"
    )


def test_infer_tickers_from_market_list():
    home, away = infer_market_tickers(
        {
            "home_market_ticker": None,
            "away_market_ticker": None,
            "market_tickers": [
                "KXWNBAGAME-26AUG30CONNDAL-CONN",
                "KXWNBAGAME-26AUG30CONNDAL-DAL",
            ],
        },
        "DAL",
        "CONN",
        lambda code: {"CON": "CONN"}.get(code, code),
    )
    assert home.endswith("-DAL")
    assert away.endswith("-CONN")


def test_rematch_suffix_deterministic():
    rows = [
        {
            "sport": "NBA",
            "game_date": "2025-12-25",
            "away_team_id": "LAL",
            "home_team_id": "BOS",
            "scheduled_start": "2025-12-25T21:00:00Z",
            "event_ticker": "B",
        },
        {
            "sport": "NBA",
            "game_date": "2025-12-25",
            "away_team_id": "LAL",
            "home_team_id": "BOS",
            "scheduled_start": "2025-12-25T17:00:00Z",
            "event_ticker": "A",
        },
    ]
    first = assign_internal_ids(rows)
    second = assign_internal_ids(list(reversed(rows)))
    ids1 = sorted(r["internal_game_id"] for r in first)
    ids2 = sorted(r["internal_game_id"] for r in second)
    assert ids1 == ids2
    assert "NBA_20251225_LAL_BOS" in ids1
    assert "NBA_20251225_LAL_BOS_2" in ids1


def test_identity_uniqueness_and_mapping(roller_env: Path):
    cfg = RollerConfig(roller_env)
    update_sport(cfg, "NBA", "2025-2026", include_pbp=True, include_candles=True)
    ident = build_identity(cfg, sports=["NBA"])
    assert ident["internal_game_id"].is_unique
    mapped = ident[ident["mapping_status"] == "MAPPED"]
    unmatched = ident[ident["mapping_status"] == "UNMAPPED"]
    assert len(mapped) == 5
    assert len(unmatched) == 1
    assert set(ident[ident["game_date"] == "2025-12-25"]["internal_game_id"]) == {
        "NBA_20251225_LAL_BOS",
        "NBA_20251225_LAL_BOS_2",
    }
