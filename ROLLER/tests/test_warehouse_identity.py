"""Phase 2 canonical Game identity. No execute, compiler, candles, or market links."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from roller.canonical.identity_build import IDENTITY_COLUMNS, build_identity
from roller.config import RollerConfig
from roller.identity import assign_internal_ids
from roller.mlb.ingest import internal_game_id as mlb_ingest_internal_game_id
from roller.warehouse.entities import Game
from roller.warehouse.identity import (
    IDENTITY_RULE_VERSION,
    PHASE2_SPORTS,
    IdentityStatus,
    apply_preserved_internal_ids,
    audit_identity_records,
    audit_phase2_disk,
    basketball_base_id,
    classify_identity_record,
    existing_identity_lookups,
    extend_identity_artifact,
    game_from_row,
    internal_game_id_format_ok,
    mlb_internal_game_id,
    parse_internal_game_id,
    resolve_internal_game_id,
)

ROLLER_ROOT = Path(__file__).resolve().parents[1]
LIVE_NBA_GAMES = ROLLER_ROOT / "data" / "nba" / "2025_2026" / "canonical" / "games.csv"
LIVE_NCAAB_GAMES = ROLLER_ROOT / "data" / "ncaab" / "2025_2026" / "canonical" / "games.csv"
LIVE_MLB_GAMES = ROLLER_ROOT / "data" / "mlb" / "2025_2026" / "canonical" / "games.csv"


def _row(**kwargs) -> dict:
    base = {
        "internal_game_id": "NBA_20251010_BOS_TOR",
        "sport": "NBA",
        "season": "2025-2026",
        "league": "NBA",
        "game_date": "2025-10-10",
        "home_team_id": "TOR",
        "away_team_id": "BOS",
        "source_game_id": "0012500044",
        "warehouse_game_id": "wh-1",
        "scheduled_start": "2025-10-10T23:00:00Z",
    }
    base.update(kwargs)
    return base


def test_existing_valid_id_formats_are_preserved():
    assert basketball_base_id("NBA", "2025-10-22", "AWAY", "HOME") == "NBA_20251022_AWAY_HOME"
    assert basketball_base_id("NCAAB", "2025-11-03", "AFA", "BEL") == "NCAAB_20251103_AFA_BEL"
    mlb = mlb_internal_game_id(
        official_date="2025-09-28",
        away_abbreviation="HOU",
        home_abbreviation="LAA",
        game_pk="776135",
    )
    assert mlb == "MLB_20250928_HOU_LAA_776135"
    assert mlb == mlb_ingest_internal_game_id(
        {
            "official_date": "2025-09-28",
            "away_abbreviation": "HOU",
            "home_abbreviation": "LAA",
            "game_pk": "776135",
        }
    )
    assert parse_internal_game_id("NBA_20251010_BOS_TOR").sport == "NBA"
    assert parse_internal_game_id("NCAAB_20251119_L-MD_DUQ").away_team_id == "L-MD"
    assert parse_internal_game_id(mlb).game_pk == "776135"


def test_identity_construction_is_deterministic():
    rows = [
        {
            "sport": "NBA",
            "game_date": "2025-12-25",
            "away_team_id": "LAL",
            "home_team_id": "BOS",
            "scheduled_start": "2025-12-25T21:00:00Z",
            "event_ticker": "B",
            "warehouse_game_id": "late",
        },
        {
            "sport": "NBA",
            "game_date": "2025-12-25",
            "away_team_id": "LAL",
            "home_team_id": "BOS",
            "scheduled_start": "2025-12-25T17:00:00Z",
            "event_ticker": "A",
            "warehouse_game_id": "early",
        },
    ]
    first = [r["internal_game_id"] for r in assign_internal_ids(rows)]
    second = [r["internal_game_id"] for r in assign_internal_ids(list(reversed(rows)))]
    assert sorted(first) == sorted(second)
    by_wh = {r["warehouse_game_id"]: r["internal_game_id"] for r in assign_internal_ids(rows)}
    assert by_wh["early"] == "NBA_20251225_LAL_BOS"
    assert by_wh["late"] == "NBA_20251225_LAL_BOS_2"


def test_unique_source_id_resolves_to_one_canonical_id():
    lookup = {("NBA", "0012500044"): "NBA_20251010_BOS_TOR"}
    got = resolve_internal_game_id(sport="NBA", source_game_id="0012500044", by_source=lookup)
    assert got.status is IdentityStatus.VALID
    assert got.internal_game_id == "NBA_20251010_BOS_TOR"
    assert got.source_system == "nba_stats"


def test_duplicate_canonical_id_is_detected():
    rows = [
        _row(warehouse_game_id="a"),
        _row(warehouse_game_id="b"),
    ]
    cov = audit_identity_records(rows, sport="NBA")
    assert cov.duplicate_internal_game_id == 1
    assert cov.status_counts[IdentityStatus.DUPLICATE.value] == 2


def test_conflicting_source_ids_fail_closed():
    rows = [
        _row(internal_game_id="NBA_20251010_BOS_TOR", source_game_id="0012500044"),
        _row(
            internal_game_id="NBA_20251010_BOS_TOR_2",
            source_game_id="0012500044",
            warehouse_game_id="wh-2",
            scheduled_start="2025-10-10T23:30:00Z",
        ),
    ]
    cov = audit_identity_records(rows, sport="NBA")
    assert cov.source_to_many_internal == 1
    assert cov.status_counts[IdentityStatus.CONFLICT.value] == 2
    lookup = existing_identity_lookups(rows)[1]
    assert ("NBA", "0012500044") not in lookup
    got = resolve_internal_game_id(
        sport="NBA",
        source_game_id="0012500044",
        internal_game_id="NBA_20251010_BOS_TOR",
        by_source={("NBA", "0012500044"): "NBA_20251011_NYK_BKN"},
    )
    assert got.status is IdentityStatus.CONFLICT


def test_missing_source_and_missing_id_fail_closed():
    missing_id = classify_identity_record(_row(internal_game_id=""))
    assert missing_id.status is IdentityStatus.MISSING
    missing_src = resolve_internal_game_id(sport="NBA", source_game_id="", internal_game_id="")
    assert missing_src.status is IdentityStatus.MISSING
    unknown = resolve_internal_game_id(sport="NBA", source_game_id="no-such-game", by_source={})
    assert unknown.status is IdentityStatus.MISSING


def test_ambiguous_rematch_without_distinguishing_keys():
    rows = [
        _row(
            internal_game_id="NBA_20251225_LAL_BOS",
            game_date="2025-12-25",
            away_team_id="LAL",
            home_team_id="BOS",
            source_game_id="",
            warehouse_game_id="",
            scheduled_start="",
            event_ticker="",
        ),
        _row(
            internal_game_id="NBA_20251225_LAL_BOS_2",
            game_date="2025-12-25",
            away_team_id="LAL",
            home_team_id="BOS",
            source_game_id="",
            warehouse_game_id="",
            scheduled_start="",
            event_ticker="",
        ),
    ]
    cov = audit_identity_records(rows, sport="NBA")
    assert cov.status_counts[IdentityStatus.AMBIGUOUS.value] == 2


def test_malformed_and_impossible_identity_are_invalid():
    assert classify_identity_record(_row(internal_game_id="KXMLBGAME-25SEP28HOULAA")).status is IdentityStatus.INVALID
    assert classify_identity_record(_row(internal_game_id="NBA_20251010_BOS_TOR_1")).status is IdentityStatus.INVALID
    assert classify_identity_record(_row(internal_game_id="MLB_20250928_HOU_LAA")).status is IdentityStatus.INVALID
    assert classify_identity_record(_row(internal_game_id="NBA_20251399_BOS_TOR")).status is IdentityStatus.INVALID
    assert classify_identity_record(_row(sport="NCAAB")).status is IdentityStatus.INVALID
    assert classify_identity_record(_row(league="MLB")).status is IdentityStatus.INVALID
    assert classify_identity_record(_row(game_date="2025-10-11")).status is IdentityStatus.INVALID
    assert not internal_game_id_format_ok("MLB_20250928_HOU_LAA", "MLB")
    mlb_conflict = classify_identity_record(
        {
            "internal_game_id": "MLB_20250928_HOU_LAA_776135",
            "sport": "MLB",
            "league": "MLB",
            "season": "2025-2026",
            "game_date": "2025-09-28",
            "source_game_id": "999999",
        }
    )
    assert mlb_conflict.status is IdentityStatus.CONFLICT


def test_game_entity_keeps_source_id_distinct_from_internal_id():
    game = game_from_row(_row())
    assert isinstance(game, Game)
    assert game.internal_game_id != game.source_game_id
    assert game.source_system == "nba_stats"
    assert game.identity_rule_version == IDENTITY_RULE_VERSION
    assert game.scheduled_at == "2025-10-10T23:00:00Z"
    assert game.event_ticker == ""


def test_preserve_existing_ids_does_not_remint():
    existing = [_row(internal_game_id="NBA_20251010_BOS_TOR", warehouse_game_id="wh-1")]
    by_wh, by_src = existing_identity_lookups(existing)
    assigned = [
        {
            "sport": "NBA",
            "warehouse_game_id": "wh-1",
            "source_game_id": "0012500044",
            "internal_game_id": "NBA_20251010_TOR_BOS",
        }
    ]
    out = apply_preserved_internal_ids(assigned, by_wh, by_src)
    assert out[0]["internal_game_id"] == "NBA_20251010_BOS_TOR"


def test_ticker_is_not_an_identity_key():
    got = resolve_internal_game_id(
        sport="NBA",
        source_game_id="",
        internal_game_id="KXNBAGAME-25OCT10BOSTOR",
        by_source={},
    )
    assert got.status is IdentityStatus.INVALID
    cov = audit_identity_records(
        [_row(internal_game_id="KXNBAGAME-25OCT10BOSTOR", source_game_id="")],
        sport="NBA",
    )
    assert cov.status_counts[IdentityStatus.INVALID.value] == 1


def test_ncaab_and_mlb_identity_rules():
    ncaab = classify_identity_record(
        {
            "internal_game_id": "NCAAB_20251103_AFA_BEL",
            "sport": "NCAAB",
            "league": "NCAAB",
            "season": "2025-2026",
            "game_date": "2025-11-03",
            "source_game_id": "401798001",
        }
    )
    mlb = classify_identity_record(
        {
            "internal_game_id": "MLB_20250928_HOU_LAA_776135",
            "sport": "MLB",
            "league": "MLB",
            "season": "2025-2026",
            "game_date": "2025-09-28",
            "source_game_id": "776135",
        }
    )
    assert ncaab.status is IdentityStatus.VALID
    assert mlb.status is IdentityStatus.VALID
    assert ncaab.source_system == "espn"
    assert mlb.source_system == "mlb_statsapi"


def test_extend_identity_artifact_copies_mlb_without_reminting(roller_env: Path):
    cfg = RollerConfig(roller_env)
    games_path = cfg.dataset_path("MLB", "2025-2026", "games")
    games_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "internal_game_id": "MLB_20250928_HOU_LAA_776135",
                "sport": "MLB",
                "season": "2025-2026",
                "league": "MLB",
                "game_date": "2025-09-28",
                "home_team_id": "LAA",
                "away_team_id": "HOU",
                "home_team_name": "LAA",
                "away_team_name": "HOU",
                "source_game_id": "776135",
                "warehouse_game_id": "776135",
                "event_ticker": "KXMLBGAME-25SEP28HOULAA",
                "kalshi_market_yes_home": "",
                "kalshi_market_yes_away": "",
            }
        ]
    ).to_csv(games_path, index=False)
    first = extend_identity_artifact(cfg, sports=("MLB",))
    assert first.appended == 1
    assert first.sports_appended["MLB"] == 1
    ident = pd.read_csv(cfg.root / "meta" / "game_identity.csv", dtype=str, keep_default_na=False)
    assert list(ident.columns) == IDENTITY_COLUMNS
    assert ident.loc[ident["sport"] == "MLB", "internal_game_id"].tolist() == [
        "MLB_20250928_HOU_LAA_776135"
    ]
    second = extend_identity_artifact(cfg, sports=("MLB",))
    assert second.appended == 0
    rebuilt = build_identity(cfg, sports=["MLB"])
    mlb_ids = rebuilt.loc[rebuilt["sport"] == "MLB", "internal_game_id"].tolist()
    assert mlb_ids == ["MLB_20250928_HOU_LAA_776135"]
    assert not any(gid.endswith("776135") is False and gid.startswith("MLB_") for gid in mlb_ids)


def test_identity_build_preserves_existing_nba_id(roller_env: Path):
    cfg = RollerConfig(roller_env)
    first = build_identity(cfg, sports=["NBA"])
    target = first.loc[first["source_game_id"] == "0022500001"].iloc[0]
    original = target["internal_game_id"]
    assert original == "NBA_20251210_LAL_BOS"
    second = build_identity(cfg, sports=["NBA"])
    again = second.loc[second["source_game_id"] == "0022500001", "internal_game_id"].tolist()
    assert again == [original]


@pytest.mark.skipif(not LIVE_NBA_GAMES.is_file(), reason="NBA canonical games absent")
@pytest.mark.skipif(not LIVE_NCAAB_GAMES.is_file(), reason="NCAAB canonical games absent")
@pytest.mark.skipif(not LIVE_MLB_GAMES.is_file(), reason="MLB canonical games absent")
def test_live_phase2_identity_invariants():
    cfg = RollerConfig(ROLLER_ROOT)
    report = audit_phase2_disk(cfg)
    assert report.rule_version == IDENTITY_RULE_VERSION
    for sport in PHASE2_SPORTS:
        cov = report.sports[sport]
        assert cov.total_games > 0
        assert cov.without_internal_game_id == 0
        assert cov.duplicate_internal_game_id == 0
        assert cov.source_to_many_internal == 0
        assert cov.internal_to_many_source == 0
        assert cov.status_counts[IdentityStatus.DUPLICATE.value] == 0
        assert cov.status_counts[IdentityStatus.CONFLICT.value] == 0
        assert cov.status_counts[IdentityStatus.INVALID.value] == 0
        assert cov.status_counts[IdentityStatus.AMBIGUOUS.value] == 0
        assert cov.status_counts[IdentityStatus.MISSING.value] == 0
        assert cov.status_counts[IdentityStatus.VALID.value] == cov.total_games
        vs = report.games_vs_identity[sport]
        assert vs.games_only == 0
        assert vs.source_mismatch == 0
    assert report.sports["MLB"].with_source_game_id == report.sports["MLB"].total_games
    mlb_ids = pd.read_csv(LIVE_MLB_GAMES, dtype=str, keep_default_na=False)["internal_game_id"]
    assert mlb_ids.map(lambda gid: bool(parse_internal_game_id(gid) and parse_internal_game_id(gid).game_pk)).all()
