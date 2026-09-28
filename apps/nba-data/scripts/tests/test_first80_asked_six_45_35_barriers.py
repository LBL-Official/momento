#!/usr/bin/env python3
"""45/35 barrier nesting. Does not change live FIRST01."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]


def _load():
    path = SCRIPTS / "first80_asked_six_45_35_barriers.py"
    spec = importlib.util.spec_from_file_location(
        "first80_asked_six_45_35_barriers", path
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


M = _load()


def q(ts, bid_cents, ask_cents=None, vol=1):
    bid = bid_cents * 100
    ask = (ask_cents * 100) if ask_cents is not None else bid + 200
    return {"ts": ts, "bid_c": bid, "ask_c": ask, "bid_l": bid, "vol": vol}


class TestTouches(unittest.TestCase):
    def test_nested_45_then_40_then_35(self):
        quotes = [
            q(1000, 80),
            q(1060, 44),
            q(1120, 39),
            q(1180, 33),
        ]
        t = M.first_touches(quotes, 1000)
        self.assertEqual(t["t45_close"], 44)
        self.assertEqual(t["t40_close"], 39)
        self.assertEqual(t["t35_close"], 33)

    def test_same_bar_40_is_also_45(self):
        quotes = [q(1000, 80), q(1060, 38)]
        t = M.first_touches(quotes, 1000)
        self.assertEqual(t["t45_close"], 38)
        self.assertEqual(t["t40_close"], 38)
        self.assertIsNone(t["t35_close"])

    def test_gap_through_40_and_35(self):
        quotes = [q(1000, 80), q(1060, 22)]
        t = M.first_touches(quotes, 1000)
        self.assertEqual(t["t45_close"], 22)
        self.assertEqual(t["t40_close"], 22)
        self.assertEqual(t["t35_close"], 22)

    def test_survive_45_no_40(self):
        quotes = [q(1000, 80), q(1060, 43), q(1120, 70)]
        t = M.first_touches(quotes, 1000)
        self.assertEqual(t["t45_close"], 43)
        self.assertIsNone(t["t40_close"])
        self.assertIsNone(t["t35_close"])

    def test_wide_spread_skipped(self):
        quotes = [
            q(1000, 80, 82),
            q(1060, 10, 40),
            q(1120, 43, 45),
        ]
        t = M.first_touches(quotes, 1000)
        self.assertEqual(t["t45_close"], 43)
        self.assertIsNone(t["t40_close"])


class TestIdentity(unittest.TestCase):
    def test_frozen_book(self):
        self.assertEqual(M.EXPECTED_N, 1182)
        self.assertEqual(M.EXPECTED_WIN + M.EXPECTED_STOP, 1182)


if __name__ == "__main__":
    unittest.main()
