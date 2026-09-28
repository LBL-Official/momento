#!/usr/bin/env python3
"""Tests for modeled 2Q/3Q loser 50/20/30 slip EV."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import first80_q23_40_loser_slip20_ev as M  # noqa: E402


class TestMix(unittest.TestCase):
    def test_expected_loser_pnl_is_minus_53(self):
        self.assertEqual(M.loser_mix_pnl_cents(), -53)
        self.assertEqual(M.EXIT_40_PNL, -40)
        self.assertEqual(M.EXIT_20_PNL, -60)
        self.assertEqual(M.EXIT_10_PNL, -70)
        self.assertEqual(M.LOSE_AT_40_WGT + M.LOSE_AT_20_WGT + M.LOSE_AT_10_WGT, 100)

    def test_formula_on_tiny_book(self):
        rows = (
            [{"W": True, "T40": False}] * 10
            + [{"W": True, "T40": True}] * 2
            + [{"W": False, "T40": True}] * 5
        )
        ev = M.ev_modeled(M.counts_of(rows))
        # 10*(+20) + 2*(-40) + 5*(-53) = 200 - 80 - 265 = -145; /17
        self.assertEqual(ev["sum_pnl_cents"], -145)
        self.assertAlmostEqual(ev["ev_cents_per_contract"], -145 / 17, places=4)

    def test_identity_and_published_ev(self):
        s = M.analyze()
        by = {c["cell"]: c for c in s["cells"]}
        self.assertEqual(by["2Q 40"]["n"], 314)
        self.assertEqual(by["3Q 40"]["n"], 290)
        self.assertEqual(by["2Q+3Q 40"]["n"], 604)
        self.assertEqual(by["2Q 40"]["ev_modeled_slip20"]["sum_pnl_cents"], 1169)
        self.assertEqual(by["3Q 40"]["ev_modeled_slip20"]["sum_pnl_cents"], 384)
        self.assertEqual(by["2Q+3Q 40"]["ev_modeled_slip20"]["sum_pnl_cents"], 1553)
        self.assertEqual(by["2Q 40"]["ev_modeled_slip20"]["ev_cents_per_contract"], 3.7229)
        self.assertEqual(by["3Q 40"]["ev_modeled_slip20"]["ev_cents_per_contract"], 1.3241)
        self.assertEqual(by["2Q+3Q 40"]["ev_modeled_slip20"]["ev_per_1000_debit_dollars"], 32.14)


if __name__ == "__main__":
    unittest.main()
