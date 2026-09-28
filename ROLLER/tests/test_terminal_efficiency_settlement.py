"""Kalshi settlement only. Missing is not NO. No box-score inference."""

from __future__ import annotations

from roller.base_terminal_efficiency.settlement import terminal_outcome


def test_yes():
    assert terminal_outcome({"result": "yes"}) == "YES"
    assert terminal_outcome({"settlement_value_e4": 10000}) == "YES"


def test_no():
    assert terminal_outcome({"result": "no"}) == "NO"
    assert terminal_outcome({"settlement_value_e4": 0}) == "NO"


def test_missing_not_no():
    assert terminal_outcome(None) == "MISSING"
    assert terminal_outcome({}) == "MISSING"
    assert terminal_outcome({"result": ""}) == "MISSING"


def test_box_score_is_not_settlement():
    assert terminal_outcome({"home_win": 1, "final_home_score": 110}) == "MISSING"
    assert terminal_outcome({"result": "yes", "home_win": 0}) == "YES"
