"""Deterministic observation_id. Same inputs → same id. Schema version changes id."""

from __future__ import annotations

from roller.state.observation_id import make_observation_id, parse_observation_id


def test_same_inputs_same_id():
    a = make_observation_id("NBA_20251220_LAL_BOS", "2025-12-20T18:30:00Z", "2.0.0")
    b = make_observation_id("NBA_20251220_LAL_BOS", "2025-12-20T18:30:00Z", "2.0.0")
    assert a == b
    assert a.startswith("OBS_NBA_20251220_LAL_BOS_")
    assert a.endswith("_V2.0.0")


def test_schema_version_changes_id():
    a = make_observation_id("NBA_20251220_LAL_BOS", "2025-12-20T18:30:00Z", "2.0.0")
    b = make_observation_id("NBA_20251220_LAL_BOS", "2025-12-20T18:30:00Z", "2.1.0")
    assert a != b


def test_parse_round_trip():
    oid = make_observation_id("NBA_20251220_LAL_BOS", "2025-12-20T18:30:00.000Z", "2.0.0")
    gid, ts, ver = parse_observation_id(oid)
    assert gid == "NBA_20251220_LAL_BOS"
    assert ver == "2.0.0"
    assert ts.year == 2025 and ts.month == 12 and ts.day == 20
    assert ts.hour == 18 and ts.minute == 30
