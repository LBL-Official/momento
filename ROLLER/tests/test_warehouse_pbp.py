"""Phase 5 NBA PBP projection. Identity ≠ PIT. No candle join. No invented clocks."""

from __future__ import annotations

import inspect
from pathlib import Path

import pandas as pd
import pytest

from roller.io_csv import read_csv
from roller.warehouse.pbp_events import project_pbp_frame, source_game_index

ROLLER_ROOT = Path(__file__).resolve().parents[1]
LIVE_OCT = ROLLER_ROOT / "data" / "nba" / "2025_2026" / "canonical" / "pbp" / "month=2025-10.csv"
LIVE_IDENTITY = ROLLER_ROOT / "meta" / "game_identity.csv"


def _identity() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "internal_game_id": "NBA_20251010_BOS_TOR",
                "sport": "NBA",
                "source_game_id": "0012500044",
            },
            {
                "internal_game_id": "NBA_20260108_MIA_CHI",
                "sport": "NBA",
                "source_game_id": "",
            },
        ]
    )


def _event(**kwargs) -> dict:
    row = {
        "internal_game_id": "NBA_20251010_BOS_TOR",
        "source_game_id": "0012500044",
        "event_number": "2",
        "event_timestamp": "2025-10-10T23:12:27.0Z",
        "time_actual": "2025-10-10T23:12:27.0Z",
        "available_at": "2025-10-10T23:12:27.0Z",
        "timestamp_status": "OBSERVED",
        "period": "1",
        "clock": "PT12M00.00S",
        "home_score": "0",
        "away_score": "0",
        "event_type": "period",
        "possession": "",
        "source_dataset": "pbp",
    }
    row.update(kwargs)
    return row


def test_source_game_id_links_to_canonical_game():
    index = source_game_index(_identity())
    out = project_pbp_frame(pd.DataFrame([_event()]), index)
    assert out.loc[0, "internal_game_id"] == "NBA_20251010_BOS_TOR"
    assert out.loc[0, "game_link_status"] == "LINKED"
    assert out.loc[0, "source_game_id"] == "0012500044"


def test_duplicate_event_number_preserved():
    rows = [_event(), _event(event_timestamp="2025-10-10T23:12:28.0Z")]
    out = project_pbp_frame(pd.DataFrame(rows), source_game_index(_identity()))
    assert len(out) == 2
    assert out["event_number"].tolist() == ["2", "2"]


def test_same_clock_keeps_source_sequence():
    rows = [
        _event(event_number="10", clock="PT07M42.00S", event_type="2pt"),
        _event(event_number="9", clock="PT07M42.00S", event_type="foul"),
    ]
    out = project_pbp_frame(pd.DataFrame(rows), source_game_index(_identity()))
    assert out["event_number"].tolist() == ["9", "10"]
    assert out["event_type"].tolist() == ["foul", "2pt"]


def test_period_halftime_overtime_preserved():
    rows = [
        _event(event_number="1", period="2", event_type="period"),
        _event(event_number="2", period="HT", event_type="period"),
        _event(event_number="3", period="5", event_type="period"),
    ]
    out = project_pbp_frame(pd.DataFrame(rows), source_game_index(_identity()))
    assert out["period"].tolist() == ["2", "HT", "5"]


def test_missing_timestamp_and_score_not_invented():
    out = project_pbp_frame(
        pd.DataFrame(
            [_event(event_timestamp="", time_actual="", home_score="", away_score="", timestamp_status="CLOCK_ONLY")]
        ),
        source_game_index(_identity()),
    )
    assert out.loc[0, "event_timestamp"] == ""
    assert out.loc[0, "home_score"] == ""
    assert out.loc[0, "timestamp_status"] == "CLOCK_ONLY"


def test_unlinked_source_and_conflict_fail_closed():
    index = source_game_index(_identity())
    missing = project_pbp_frame(pd.DataFrame([_event(source_game_id="")]), index)
    assert missing.loc[0, "game_link_status"] == "UNLINKED"
    assert missing.loc[0, "internal_game_id"] == ""
    unknown = project_pbp_frame(pd.DataFrame([_event(source_game_id="999")]), index)
    assert unknown.loc[0, "game_link_status"] == "UNLINKED"
    conflict = project_pbp_frame(
        pd.DataFrame([_event(internal_game_id="NBA_20251011_NYK_BKN")]),
        index,
    )
    assert conflict.loc[0, "game_link_status"] == "CONFLICT"
    assert conflict.loc[0, "internal_game_id"] == ""


def test_ambiguous_source_id_not_guessed():
    ident = pd.concat(
        [
            _identity(),
            pd.DataFrame(
                [{"internal_game_id": "NBA_20251010_NYK_BKN", "sport": "NBA", "source_game_id": "0012500044"}]
            ),
        ],
        ignore_index=True,
    )
    out = project_pbp_frame(pd.DataFrame([_event()]), source_game_index(ident))
    assert out.loc[0, "game_link_status"] == "AMBIGUOUS"
    assert out.loc[0, "internal_game_id"] == ""


def test_no_candle_join_or_clock_invention_in_module():
    import roller.warehouse.pbp_events as pbp

    src = inspect.getsource(pbp)
    assert "kalshi_candles" not in src
    assert "nearest" not in src
    assert "PT07M" not in src
    assert "infer" not in src.lower() or "possession_inferred" in src


@pytest.mark.skipif(not LIVE_OCT.is_file(), reason="NBA October PBP absent")
@pytest.mark.skipif(not LIVE_IDENTITY.is_file(), reason="identity catalog absent")
def test_live_october_pbp_sequence_and_link():
    ident = read_csv(LIVE_IDENTITY)
    index = source_game_index(ident)
    raw = read_csv(LIVE_OCT)
    out = project_pbp_frame(raw, index)
    assert len(out) == len(raw)
    assert (out["game_link_status"] == "LINKED").all()
    bos = out[out["internal_game_id"] == "NBA_20251010_BOS_TOR"]
    nums = pd.to_numeric(bos["event_number"], errors="coerce")
    assert nums.is_monotonic_increasing
    assert (out["source_game_id"].astype(str).str.strip() != "").all()
