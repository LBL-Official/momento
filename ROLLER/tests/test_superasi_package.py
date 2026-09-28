"""SuperASI package schema. LIVE EXECUTION = FALSE."""

from __future__ import annotations

import pytest

from roller.superasi.models import SuperasiError
from roller.superasi.package import new_package, normalize_trade
from roller.superasi.validation import validate_package
from roller.superasi.versions import PACKAGE_SCHEMA


def _trade(**kw):
    row = {
        "ticker": "T-A",
        "internal_game_id": "G-A",
        "sport": "NBA",
        "slice": "Q3",
        "dataset_split": "OOS",
        "entry_ts": "2025-01-01T00:00:00Z",
        "entry_close": 80,
        "entry_price_e4": 8000,
        "path_true": True,
        "win_exit": True,
        "loss_exit": False,
        "terminal_yes": True,
        "price_basis": "YES_BID_CLOSE",
    }
    row.update(kw)
    return row


def test_schema_and_checksum(tmp_path=None):
    pkg, trades = new_package(source="roller_generic", trades=[_trade()])
    assert pkg["schema_version"] == PACKAGE_SCHEMA
    assert pkg["live_execution"] is False
    assert pkg["population_n"] == 1
    validate_package(pkg, trades)
    with pytest.raises(SuperasiError) as ei:
        validate_package(pkg, [])
    assert ei.value.code == "POPULATION_COUNT_MISMATCH"


def test_empty_refused():
    with pytest.raises(SuperasiError) as ei:
        new_package(source="roller_generic", trades=[])
    assert ei.value.code == "EMPTY_POPULATION"


def test_e4_entry_close_becomes_cents():
    t = normalize_trade(_trade(entry_close=8000, entry_price_e4=8000), 0)
    assert t["entry_close"] == 80
    frozen = normalize_trade(
        {
            "ticker": "K",
            "entry_price_e4": 8000,
            "T40": True,
            "W": False,
            "price_basis": "TRADABLE_YES_BID",
        },
        1,
    )
    assert frozen["entry_close"] == 80
    assert frozen["price_basis"] == "YES_BID_CLOSE"
    assert frozen["loss_exit"] is True
    assert frozen["path_true"] is False
    assert frozen["terminal_yes"] is False


def test_missing_ask_is_unavailable():
    t = normalize_trade(_trade(), 0)
    assert t["entry_ask_status"] == "UNAVAILABLE"
    assert t["entry_ask"] is None


def test_unknown_source():
    with pytest.raises(SuperasiError) as ei:
        new_package(source="nope", trades=[_trade()])
    assert ei.value.code == "PACKAGE_SCHEMA_INVALID"
