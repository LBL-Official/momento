#!/usr/bin/env python3
"""Unit math for asked-six 80/40 path sims. Does not change live FIRST01."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import numpy as np

SCRIPTS = Path(__file__).resolve().parents[1]


def _load():
    path = SCRIPTS / "first80_asked_six_80_40_quant_paths.py"
    spec = importlib.util.spec_from_file_location("first80_asked_six_80_40_quant_paths", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


M = _load()


class TestWeekPayoff(unittest.TestCase):
    def test_chatgpt_5pct_formula(self):
        self.assertAlmostEqual(M.week_return_frac(7, 5), 0.0125)
        self.assertAlmostEqual(M.week_return_frac(5, 5), -0.0625)
        self.assertAlmostEqual(M.week_return_frac(10, 5), 0.125)
        self.assertAlmostEqual(M.week_return_frac(0, 5), -0.25)

    def test_integer_matches_formula_when_qty_exact(self):
        b = 2_000_000
        f = 5
        qty = M.qty_from_bankroll(b, f)
        self.assertEqual(qty, 1250)
        pnl = M.week_pnl_cents(7, b, f)
        self.assertEqual(pnl, 1250 * (20 * 7 - 40 * 3))
        self.assertEqual(pnl, int(round(b * M.week_return_frac(7, 5))))

    def test_breakeven_six_and_two_thirds(self):
        b = 2_000_000
        # 7 wins is above breakeven; 6 wins: 6*20 - 4*40 = -40 per contract
        self.assertGreater(M.week_pnl_cents(7, b, 5), 0)
        self.assertLess(M.week_pnl_cents(6, b, 5), 0)


class TestIdentity(unittest.TestCase):
    def test_frozen_book(self):
        self.assertEqual(M.EXPECTED_N, 1182)
        self.assertEqual(M.EXPECTED_WIN + M.EXPECTED_STOP, 1182)
        self.assertFalse(M.BREAKEVEN == 0.72)


class TestStreak(unittest.TestCase):
    def test_longest_run(self):
        x = np.array([1, 0, 0, 0, 1, 0, 0], dtype=np.int8)
        self.assertEqual(M.longest_run(x, 0), 3)
        self.assertEqual(M.longest_run(x, 1), 1)


if __name__ == "__main__":
    unittest.main()
