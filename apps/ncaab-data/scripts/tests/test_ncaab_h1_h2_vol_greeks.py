#!/usr/bin/env python3
"""Unit math for H1-20 vs H2-first-5 discovery. Does not change live FIRST01."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import ncaab_h1_h2_vol_greeks as M  # noqa: E402


class TestWindows(unittest.TestCase):
    def test_h1_20(self):
        self.assertTrue(M.in_window("H1_20", 1, 600.0, "IN_PERIOD"))
        self.assertFalse(M.in_window("H1_20", 1, 600.0, "INTERMISSION"))
        self.assertFalse(M.in_window("H1_20", 2, 1100.0, "IN_PERIOD"))

    def test_first_five(self):
        self.assertTrue(M.in_window("H1_5", 1, 1100.0, "IN_PERIOD"))
        self.assertFalse(M.in_window("H1_5", 1, 800.0, "IN_PERIOD"))
        self.assertTrue(M.in_window("H2_5", 2, 1100.0, "IN_PERIOD"))
        self.assertFalse(M.in_window("H2_5", 1, 1100.0, "IN_PERIOD"))


class TestMath(unittest.TestCase):
    def test_ols(self):
        rec = M.ols_slope([0.0, 1.0, 2.0], [0.0, 2.0, 4.0])
        self.assertAlmostEqual(rec["beta"], 2.0)
        self.assertAlmostEqual(rec["r"], 1.0)

    def test_ar1_alternating(self):
        self.assertAlmostEqual(M.ar1([1.0, -1.0, 1.0, -1.0, 1.0, -1.0]), -1.0)

    def test_sign_flip(self):
        self.assertAlmostEqual(M.sign_flip_rate([2.0, -1.0, 3.0, -2.0]), 1.0)
        self.assertAlmostEqual(M.sign_flip_rate([1.0, 1.0, 1.0]), 0.0)

    def test_ratio(self):
        self.assertAlmostEqual(M.safe_ratio(3.0, 2.0), 1.5)
        self.assertIsNone(M.safe_ratio(1.0, 0.0))


if __name__ == "__main__":
    unittest.main()
