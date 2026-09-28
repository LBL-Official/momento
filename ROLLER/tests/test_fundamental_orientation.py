"""Home-minus-away orientation. Positive = home leads."""

from __future__ import annotations

from roller.fundamental.orientation import home_leading, home_trailing, score_diff_home, y_home_win


def test_home_and_away_leads():
    assert score_diff_home(110, 100) == 10
    assert score_diff_home(98, 105) == -7
    assert home_leading(10) is True
    assert home_trailing(10) is False
    assert home_leading(-7) is False
    assert home_trailing(-7) is True
    assert y_home_win("1") == 1
    assert y_home_win("0") == 0
    assert y_home_win("") is None


def test_tie_is_not_a_home_win():
    assert score_diff_home(100, 100) == 0
    assert home_leading(0) is False
    assert home_trailing(0) is False
    assert y_home_win("0") == 0
