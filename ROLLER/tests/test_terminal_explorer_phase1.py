"""Phase 1: Explorer + Object Inspector vertical slice tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from roller.dashboard_adapter.explorer import ExplorerError, list_universe_games
from roller.dashboard_adapter.object_inspector import ObjectInspectorError, build_object_payload
from roller.dashboard_adapter.serialize import to_jsonable

MOMENTO = Path(__file__).resolve().parents[2]
NBA_GAMES = MOMENTO / "ROLLER" / "data" / "nba" / "2025_2026" / "canonical" / "games.csv"


def test_explorer_requires_as_of():
    with pytest.raises(ExplorerError, match="as_of is required"):
        list_universe_games(as_of=None)


def test_explorer_rejects_empty_as_of():
    with pytest.raises(ExplorerError, match="as_of is required"):
        list_universe_games(as_of="  ")


def test_object_inspector_requires_as_of():
    with pytest.raises(ObjectInspectorError, match="as_of is required"):
        build_object_payload("NBA_20251010_BOS_TOR", as_of=None)


def test_serialize_never_coerces_null_or_nan_to_zero():
    payload = {
        "missing": None,
        "nan": float("nan"),
        "status": "NOT_CONSTRUCTIBLE",
        "value": None,
        "nested": {"x": None, "status": "NOT_CONSTRUCTIBLE"},
    }
    out = to_jsonable(payload)
    assert out["missing"] is None
    assert out["nan"] is None
    assert out["value"] is None
    assert out["nested"]["x"] is None
    assert out["status"] == "NOT_CONSTRUCTIBLE"
    assert out["nested"]["status"] == "NOT_CONSTRUCTIBLE"
    # Explicit zeros that were actually zero remain zero — only missing must stay null.
    assert to_jsonable({"actual_zero": 0})["actual_zero"] == 0
    text = json.dumps(out)
    assert '"missing": null' in text
    assert '"value": null' in text


@pytest.mark.integration
def test_explorer_real_nba_as_of_2025_10_11():
    if not NBA_GAMES.is_file():
        pytest.skip(f"canonical NBA games absent: {NBA_GAMES}")
    result = list_universe_games(as_of="2025-10-11")
    assert result["universe"] == "BBALL1"
    assert result["information_mode"] == "POINT_IN_TIME"
    assert result["n_rows"] >= 1
    ids = {r["internal_game_id"] for r in result["rows"]}
    assert "NBA_20251010_BOS_TOR" in ids


@pytest.mark.integration
def test_object_inspector_real_observation_preserves_statuses():
    if not NBA_GAMES.is_file():
        pytest.skip(f"canonical NBA games absent: {NBA_GAMES}")
    payload = build_object_payload(
        "NBA_20251010_BOS_TOR",
        as_of="2025-10-10T23:15:00Z",
        include_measurements=True,
    )
    assert payload["identity"]["observation_id"].startswith("OBS_NBA_20251010_BOS_TOR_")
    assert payload["state"]["status"] == "REAL"
    fund_status = payload["measurements"]["fundamental"]["status"]
    assert fund_status != 0
    assert fund_status is not None
    # Must not coerce NOT_CONSTRUCTIBLE / null into numeric zero in constructibility table.
    for row in payload["constructibility"]["observation_sections"]:
        assert row["status"] != 0
        assert isinstance(row["status"], str)
