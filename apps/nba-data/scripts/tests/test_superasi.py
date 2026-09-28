#!/usr/bin/env python3
"""Locks SuperASI EV identities. Does not change live FIRST01."""

from __future__ import annotations

import sys
import unittest
from fractions import Fraction
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import superasi as M  # noqa: E402


class TestLockedCounts(unittest.TestCase):
    def test_first80_cells(self):
        self.assertEqual(
            M.F80_WIN_NO + M.F80_WIN_T40 + M.F80_LOSE_NO + M.F80_LOSE_T40,
            M.N80,
        )
        self.assertEqual(M.F80_WIN_NO + M.F80_WIN_T40, 991)
        self.assertEqual(M.F80_WIN_T40 + M.F80_LOSE_T40, M.T40_N)
        self.assertEqual(M.T40_PRINTED_40 + M.T40_LT40, M.T40_N)

    def test_t40_sums(self):
        self.assertEqual(M.T40_CLOSE_SUM, 10318)
        self.assertEqual(M.T40_N * M.ENTRY_CENTS - M.T40_CLOSE_SUM, 13602)
        self.assertEqual(M.SURROUND[0][1], M.T40_CLOSE_SUM)
        self.assertEqual(M.PRE_T40_38_40_TRADES, 1)


class TestIdentities(unittest.TestCase):
    def test_product_and_rule_S(self):
        r = M.rates_from_cells(
            M.F80_WIN_NO, M.F80_WIN_T40, M.F80_LOSE_NO, M.F80_LOSE_T40
        )
        self.assertEqual(r["p"], Fraction(991, 1182))
        self.assertEqual(r["s_W"], Fraction(883, 991))
        self.assertEqual(r["s_L"], Fraction(0, 1))
        self.assertEqual(r["S"], Fraction(883, 1182))
        self.assertEqual(r["joint_win_survive"], r["p"] * r["s_W"])
        self.assertEqual(r["S"], r["p"] * r["s_W"])

    def test_ledger_ev(self):
        s = Fraction(883, 1182)
        ev = M.ev_survive_stop(s, 20, 40)
        self.assertEqual(ev["ev_cents"], Fraction(5700, 1182))
        self.assertEqual(ev["breakeven_S"], Fraction(40, 60))
        self.assertEqual(ev["breakeven_L"], Fraction(17660, 299))

    def test_t40_close_ev(self):
        s = Fraction(883, 1182)
        loss = Fraction(13602, 299)
        ev = M.ev_survive_stop(s, 20, loss)
        self.assertEqual(ev["ev_cents"], Fraction(4058, 1182))

    def test_planning_2_5(self):
        s = Fraction(883, 1182)
        plan_l = M.implied_stop_loss(s, 20, Fraction(5, 2))
        self.assertEqual(plan_l, Fraction(14705, 299))
        ev = M.ev_survive_stop(s, 20, plan_l)
        self.assertEqual(ev["ev_cents"], Fraction(5, 2))


class TestBuild(unittest.TestCase):
    def test_build_matches_published(self):
        doc = M.build()
        self.assertEqual(doc["name"], "SuperASI")
        self.assertEqual(doc["legacy_name"], "Lebronner")
        self.assertFalse(doc["live_authorized"])
        self.assertEqual(doc["status"], "SPEC_ONLY")
        self.assertAlmostEqual(doc["in_production_ev"]["ev_cents"], 4.8223, places=4)
        self.assertAlmostEqual(doc["stop_path"]["ev_cents"], 3.4332, places=4)
        self.assertAlmostEqual(doc["research_planning_ev"]["ev_cents"], 2.50, places=2)
        self.assertAlmostEqual(
            doc["research_planning_ev"]["implied_mean_stop_loss"], 49.1806, places=4
        )
        self.assertEqual(doc["stop_path"]["printed_40"], 54)
        self.assertEqual(doc["stop_path"]["pre_t40_38_40_trades"], 1)


if __name__ == "__main__":
    unittest.main()
