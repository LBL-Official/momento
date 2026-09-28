"""Vital Bot Standard Phase 2 — isolated MLB 001 folder. No crate move."""

from __future__ import annotations

from pathlib import Path

import pytest

from roller.vital.bots import get_bot, get_bot_boundary, list_bots
from roller.vital.errors import VitalError
from roller.vital.mlb_001.boundary import POINTERS, boundary_record
from roller.vital.mlb_001.identity import BOT_ID, ENGINE_POINTER, PACKAGE, STRATEGY_POINTER
from roller.vital.naming import (
    BOT_STANDARD_PHASE,
    display_name,
    folder_relpath,
    package_module,
    parse_bot_id,
    resolve_canonical_bot_id,
)
from roller.vital.store import TREE_DIRS, pointers_path, seed_mlb_001
from roller.vital.versions import BOT_ID as VERSION_BOT_ID


def test_naming_parses_mlb_001():
    sport, ordinal = parse_bot_id("mlb-001")
    assert sport == "mlb"
    assert ordinal == 1
    assert display_name("mlb-001") == "MLB Bot 001"
    assert package_module("mlb-001") == "roller.vital.mlb_001"
    assert folder_relpath("mlb-001") == "research/vital/bots/mlb-001"
    assert resolve_canonical_bot_id("mlb-bot-one") == BOT_ID


def test_naming_rejects_sport_dump_and_malformed():
    with pytest.raises(VitalError) as dump:
        parse_bot_id("mlb")
    assert dump.value.code == "INVALID_BOT_ID"
    with pytest.raises(VitalError):
        parse_bot_id("mlb-1")
    with pytest.raises(VitalError):
        parse_bot_id("MLB-001")


def test_versions_reexports_isolated_identity():
    assert VERSION_BOT_ID == BOT_ID == "mlb-001"
    assert PACKAGE == "roller.vital.mlb_001"
    assert BOT_STANDARD_PHASE["1"] == "ACCEPTED"
    assert BOT_STANDARD_PHASE["2"] == "IMPLEMENTED"
    assert BOT_STANDARD_PHASE["3"] == "IMPLEMENTED"
    assert BOT_STANDARD_PHASE["4"] == "IMPLEMENTED"
    assert BOT_STANDARD_PHASE["5"] == "IMPLEMENTED"
    assert BOT_STANDARD_PHASE["6"] == "IMPLEMENTED"


def test_seed_writes_isolated_boundary(tmp_path):
    seed_mlb_001(root=tmp_path)
    dest = tmp_path / "bots" / BOT_ID
    for name in TREE_DIRS:
        assert (dest / name).is_dir()
    boundary = get_bot_boundary("mlb-bot-one", root=tmp_path)
    assert boundary["bot_id"] == BOT_ID
    assert boundary["isolated"] is True
    assert boundary["moved"] is False
    assert boundary["second_engine"] is False
    assert boundary["pointers"]["worker"] == ENGINE_POINTER
    assert boundary["pointers"]["strategy"] == STRATEGY_POINTER
    assert pointers_path(BOT_ID, root=tmp_path).is_file()
    assert not (dest / "source" / "apps").exists()
    assert not (dest / "source" / "strategies").exists()


def test_vital_identifies_mlb_001_independently(tmp_path):
    listed = list_bots(root=tmp_path)
    assert [row["bot_id"] for row in listed] == [BOT_ID]
    bot = get_bot("mlb-001", root=tmp_path)
    assert bot["bot_id"] == BOT_ID
    assert bot["kind"] == "grandfathered"
    with pytest.raises(VitalError) as missing:
        get_bot("mlb-002", root=tmp_path)
    assert missing.value.code == "BOT_NOT_FOUND"
    with pytest.raises(VitalError):
        get_bot_boundary("mlb-002", root=tmp_path)


def test_mlb_002_is_not_inside_mlb_001_tree(tmp_path):
    seed_mlb_001(root=tmp_path)
    nested = tmp_path / "bots" / BOT_ID / "mlb-002"
    assert not nested.exists()
    assert (tmp_path / "bots" / "mlb-002").exists() is False
    record = boundary_record()
    assert "mlb-002" not in record["folder"]
    assert record["pointers"]["worker"] == "apps/trading-engine"
    repo = Path(__file__).resolve().parents[2]
    assert (repo / POINTERS["worker"]).is_dir()
    assert (repo / POINTERS["strategy"]).is_dir()
    assert (repo / "ROLLER" / "roller" / "vital" / "mlb_001" / "identity.py").is_file()
