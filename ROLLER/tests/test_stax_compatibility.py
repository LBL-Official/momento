"""STAX universe compatibility. No silent date expansion."""

from __future__ import annotations

import pytest

from roller.stax.compatibility import (
    assert_compatible,
    canonicalize_universe,
    universe_from_source,
)
from roller.stax.models import ConstraintViolation
from roller.stax.validation import reject_rolling_fields
from tests.stax_fixtures import source


def _u(**kwargs):
    return universe_from_source(source(**kwargs))


def test_same_universe_passes():
    a = _u()
    b = _u(name="CROSS60")
    assert_compatible(a, b)
    assert a.sport_family == "basketball"
    assert a.league_set == ("NBA",)


def test_season_alias_matches():
    a = _u(seasons=("2025-26",))
    b = _u(seasons=("2025-2026",))
    assert_compatible(a, b)


def test_different_sport_fails():
    a = _u(sports=("basketball",), leagues=("NBA",))
    b = _u(sports=("baseball",), leagues=("MLB",), seasons=("2025-26",), date_from="2026-06-18", date_to="2026-06-30")
    with pytest.raises(ConstraintViolation) as exc:
        assert_compatible(a, b)
    assert exc.value.code == "STAX_CONSTRAINT_VIOLATION"
    assert "SPORT" in exc.value.message


def test_different_league_fails():
    a = _u(leagues=("NBA",))
    b = _u(leagues=("NCAAB",))
    with pytest.raises(ConstraintViolation):
        assert_compatible(a, b)


def test_nba_vs_nba_wnba_fails():
    a = _u(leagues=("NBA",))
    b = _u(leagues=("NBA", "WNBA"))
    with pytest.raises(ConstraintViolation) as exc:
        assert_compatible(a, b)
    assert "league_set" in exc.value.details


def test_different_season_fails():
    a = _u(seasons=("2025-26",))
    b = _u(seasons=("2024-25",), date_from="2024-10-04", date_to="2025-06-22")
    with pytest.raises(ConstraintViolation):
        assert_compatible(a, b)


def test_different_date_range_fails():
    a = _u(date_from="2025-10-10", date_to="2026-06-13")
    b = _u(date_from="2025-11-01", date_to="2026-06-13")
    with pytest.raises(ConstraintViolation) as exc:
        assert_compatible(a, b)
    assert "timeframe" in exc.value.details


def test_does_not_expand_narrower_window():
    locked = canonicalize_universe(
        {"sports": ["basketball"], "leagues": ["NBA"], "seasons": ["2025-26"], "date_from": "2025-10-10", "date_to": "2026-06-13"}
    )
    narrow = canonicalize_universe(
        {"sports": ["basketball"], "leagues": ["NBA"], "seasons": ["2025-26"], "date_from": "2025-10-10", "date_to": "2026-06-01"}
    )
    with pytest.raises(ConstraintViolation):
        assert_compatible(locked, narrow)
    assert locked.date_to == "2026-06-13"
    assert narrow.date_to == "2026-06-01"


def test_rolling_fields_rejected():
    with pytest.raises(Exception) as exc:
        reject_rolling_fields({"timeframe_mode": "ROLLING"})
    assert exc.value.code == "STAX_ROLLING_UNSUPPORTED"


def test_typo_season_2025_25_fails():
    a = _u(seasons=("2025-26",))
    b = _u(seasons=("2025-25",))
    with pytest.raises(ConstraintViolation) as exc:
        assert_compatible(a, b)
    assert "seasons" in exc.value.details


def test_full_season_vs_explicit_subset_fails():
    a = _u(date_from=None, date_to=None)
    b = _u(date_from="2025-10-10", date_to="2026-06-13")
    with pytest.raises(ConstraintViolation) as exc:
        assert_compatible(a, b)
    assert "timeframe" in exc.value.details


def test_compiled_question_beats_client_universe_field():
    spoof = source(leagues=("NCAAB",))
    spoof["universe"] = source(leagues=("NBA",))["universe"]
    spoof["sports"] = ["basketball"]
    spoof["leagues"] = ["NBA"]
    uni = universe_from_source(spoof)
    assert uni.league_set == ("NCAAB",)
    with pytest.raises(ConstraintViolation) as exc:
        assert_compatible(_u(leagues=("NBA",)), uni)
    assert exc.value.code == "STAX_CONSTRAINT_VIOLATION"
    assert "SPORT / LEAGUE / TIMEFRAME MUST MATCH" in exc.value.message
    assert "league_set" in exc.value.details
