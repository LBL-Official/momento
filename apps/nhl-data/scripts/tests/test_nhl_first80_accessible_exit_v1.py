"""Unit tests for NHL gettable-at-80 and actual-exit measurement.

Does not require the warehouse. Does not change live trading.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path("/Users/user/Desktop/Momento/apps/nhl-data/scripts")
sys.path.insert(0, str(SCRIPTS))
import nhl_first80_accessible_exit_v1 as M  # noqa: E402


def q(ts, bid_c, ask_c=None, bid_l=None, bid_h=None, vol=100, bid_o=None):
    if ask_c is None:
        ask_c = bid_c + 200
    if bid_l is None:
        bid_l = bid_c
    if bid_h is None:
        bid_h = bid_c
    if bid_o is None:
        bid_o = bid_c
    return {
        "ts": ts,
        "bid_o": bid_o,
        "bid_h": bid_h,
        "bid_l": bid_l,
        "bid_c": bid_c,
        "ask_o": ask_c,
        "ask_h": ask_c,
        "ask_l": ask_c,
        "ask_c": ask_c,
        "px_o": bid_c,
        "px_h": bid_h,
        "px_l": bid_l,
        "px_c": bid_c,
        "vol": vol,
    }


class GettableTests(unittest.TestCase):
    def test_jump_through_80_is_not_gettable(self):
        rec = {
            "first_80_timestamp": 100,
            "close_ts": 10000,
            "maker_fill_confidence": "HIGH",
            "last_print_through_80": True,
            "stop_close_triggered": False,
            "expiration_result_yes": True,
        }
        quotes = [
            q(40, 5500),
            q(100, 8800, bid_o=5500, bid_l=5500, bid_h=8800),
        ]
        rec["entry_features"] = M.EQ.features_for(rec, quotes)
        flags = M.universe_flags(rec)
        self.assertGreaterEqual(rec["entry_features"]["jump_1m_cents"], 20)
        self.assertFalse(flags["GETTABLE_AT_80"])
        self.assertFalse(flags["RESTABLE_80"])

    def test_gradual_high_fill_can_be_gettable(self):
        rec = {
            "first_80_timestamp": 300,
            "close_ts": 10000,
            "maker_fill_confidence": "HIGH",
            "last_print_through_80": True,
            "stop_close_triggered": False,
            "expiration_result_yes": True,
        }
        quotes = [
            q(60, 7600),
            q(120, 7700),
            q(180, 7800),
            q(240, 7900),
            q(300, 8100, ask_c=8300, bid_l=8000, bid_h=8200, bid_o=7900),
            q(360, 8100, ask_c=8300),
        ]
        rec["entry_features"] = M.EQ.features_for(rec, quotes)
        flags = M.universe_flags(rec)
        self.assertLess(rec["entry_features"]["jump_1m_cents"], 10)
        self.assertTrue(flags["high_access"])
        self.assertTrue(flags["GETTABLE_AT_80"])


class ExitTests(unittest.TestCase):
    def test_never_leaves_80_settles_100(self):
        rec = {
            "first_80_timestamp": 100,
            "close_ts": 400,
            "game_date": None,
            "stop_close_triggered": False,
            "expiration_result_yes": True,
        }
        quotes = [q(100, 8100), q(160, 8200), q(220, 8500)]
        ex = M.measure_exits(rec, quotes)
        self.assertFalse(ex["left_80"])
        self.assertEqual(ex["actual_exit_leave80_close"], 100.0)
        self.assertEqual(ex["pnl_leave80_close"], 20.0)
        self.assertEqual(ex["pnl_8040_assumed"], 20.0)

    def test_leave_80_uses_printed_close_not_40(self):
        rec = {
            "first_80_timestamp": 100,
            "close_ts": 500,
            "game_date": None,
            "stop_close_triggered": True,
            "expiration_result_yes": False,
        }
        quotes = [
            q(100, 8100),
            q(160, 2200, bid_o=8100, bid_l=1800, bid_h=8100),
        ]
        ex = M.measure_exits(rec, quotes)
        self.assertTrue(ex["left_80"])
        self.assertEqual(ex["actual_exit_leave80_close"], 22.0)
        self.assertEqual(ex["actual_exit_leave80_low"], 18.0)
        self.assertEqual(ex["pnl_leave80_close"], -58.0)
        self.assertEqual(ex["pnl_8040_assumed"], -40.0)
        self.assertEqual(ex["t40_actual_minus_assumed_40"], -18.0)
        self.assertTrue(ex["t40"]["jumped_through_40"])

    def test_mean_median_actual_exits(self):
        s = M._stats([100.0, 22.0, 40.0])
        self.assertEqual(s["n"], 3)
        self.assertAlmostEqual(s["mean"], 54.0)
        self.assertEqual(s["median"], 40.0)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
