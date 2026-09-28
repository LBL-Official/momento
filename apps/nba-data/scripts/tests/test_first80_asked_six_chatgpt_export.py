#!/usr/bin/env python3
"""Unit math for asked-six FIRST80 ChatGPT export. Does not change live FIRST01."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load():
    path = SCRIPTS / "first80_asked_six_chatgpt_export.py"
    spec = importlib.util.spec_from_file_location("first80_asked_six_chatgpt_export", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


M = _load()


class TestPayoff(unittest.TestCase):
    def test_stop_win_hold_loss_hold(self):
        self.assertEqual(M.outcome_80_40(True, True), ("STOP_40", -40))
        self.assertEqual(M.outcome_80_40(False, True), ("STOP_40", -40))
        self.assertEqual(M.outcome_80_40(True, False), ("WIN_HOLD", 20))
        self.assertEqual(M.outcome_80_40(False, False), ("LOSS_HOLD", -80))

    def test_win_80_40_excludes_stopped_winners(self):
        stopped_yes = M.flags_80_40(True, True)
        self.assertFalse(stopped_yes["win_80_40"])
        self.assertTrue(stopped_yes["stopped_40"])
        self.assertTrue(stopped_yes["terminal_yes"])
        survive = M.flags_80_40(True, False)
        self.assertTrue(survive["win_80_40"])
        self.assertFalse(survive["stopped_40"])

    def test_attach_keeps_all_rows(self):
        rows = [
            {"W": "True", "T40": "False", "sport": "NBA"},
            {"W": "True", "T40": "True", "sport": "NBA"},
        ]
        # identity halt expects 1182; test flags only on a tiny patch
        flags = [M.flags_80_40(M._as_bool(r["W"]), M._as_bool(r["T40"])) for r in rows]
        self.assertEqual([f["win_80_40"] for f in flags], [True, False])
        self.assertEqual(sum(f["win_80_40"] or f["stopped_40"] for f in flags), 2)


class TestSide(unittest.TestCase):
    def test_ticker_and_bought_name(self):
        g = {
            "home_market_ticker": "KXNBAGAME-X-SAS",
            "away_market_ticker": "KXNBAGAME-X-NYK",
            "home_team": "San Antonio",
            "away_team": "New York",
            "home_team_code": "SAS",
            "away_team_code": "NYK",
        }
        self.assertEqual(M.side_of("KXNBAGAME-X-SAS", g), "home")
        self.assertEqual(M.side_of("KXNBAGAME-X-NYK", g), "away")
        wnba = {
            "home_team": "Dallas",
            "away_team": "Connecticut",
            "home_team_code": "Dallas",
            "away_team_code": "Connecticut",
        }
        self.assertEqual(M.side_of("KXWNBAGAME-X-DAL", wnba, "Dallas"), "home")


class TestIdentity(unittest.TestCase):
    def test_asked_six_counts(self):
        self.assertEqual(sum(M.EXPECTED_ASKED.values()), M.EXPECTED_TOTAL)
        self.assertEqual(M.EXPECTED_ASKED["NBA"], 604)
        self.assertEqual(M.EXPECTED_ASKED["WNBA"], 246)
        self.assertEqual(M.EXPECTED_ASKED["NCAAB"], 332)

    def test_unavailable_not_invented(self):
        self.assertEqual(M.UNAVAILABLE, "UNAVAILABLE")
        self.assertIn("possession_status", M.CSV_COLUMNS)
        self.assertIn("exit_kind", M.CSV_COLUMNS)
        self.assertIn("hyp_pnl_cents_80_40", M.CSV_COLUMNS)
        self.assertIn("win_80_40", M.CSV_COLUMNS)
        self.assertLess(M.CSV_COLUMNS.index("win_80_40"), M.CSV_COLUMNS.index("W"))


class TestCents(unittest.TestCase):
    def test_e4(self):
        self.assertEqual(M.e4_to_cents(8000), 80.0)
        self.assertEqual(M.e4_to_prob(8000), 0.8)
        self.assertIsNone(M.e4_to_cents(None))


if __name__ == "__main__":
    unittest.main()
