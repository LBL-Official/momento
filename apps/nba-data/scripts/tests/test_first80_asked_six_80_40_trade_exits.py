#!/usr/bin/env python3
"""Per-trade exit averages. Does not change live FIRST01."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]


def _load():
    path = SCRIPTS / "first80_asked_six_80_40_trade_exits.py"
    spec = importlib.util.spec_from_file_location(
        "first80_asked_six_80_40_trade_exits", path
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


M = _load()


class TestIdentity(unittest.TestCase):
    def test_frozen_book(self):
        self.assertEqual(M.EXPECTED_N, 1182)
        self.assertEqual(M.EXPECTED_WIN, 883)
        self.assertEqual(M.EXPECTED_STOP, 299)


class TestExitMath(unittest.TestCase):
    def test_pnl_is_exit_minus_entry(self):
        self.assertEqual(M.pnl_from_exit(100), 20)
        self.assertEqual(M.pnl_from_exit(40), -40)
        self.assertEqual(M.pnl_from_exit(35), -45)
        self.assertEqual(M.pnl_from_exit(0), -80)

    def test_labeled_book_average(self):
        labeled = (883 * 100 + 299 * 40) / 1182
        self.assertAlmostEqual(labeled, 84.8223, places=3)
        self.assertAlmostEqual(labeled - 80, 4.8223, places=3)

    def test_t40_close_book_average_from_stop_mean(self):
        # 299 * 34.5084 + 883 * 100, from the frozen scan mean
        stop_mean = 34.5084
        book = (883 * 100 + 299 * stop_mean) / 1182
        self.assertAlmostEqual(book, 83.4334, places=3)
        self.assertAlmostEqual(book - 80, 3.4334, places=3)


if __name__ == "__main__":
    unittest.main()
