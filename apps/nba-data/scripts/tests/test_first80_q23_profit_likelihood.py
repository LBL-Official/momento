#!/usr/bin/env python3
"""Tests for realistic 2Q+3Q FIRST80 P(season EV>0)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import first80_q23_profit_likelihood as M  # noqa: E402


class TestIdentities(unittest.TestCase):
    def test_frozen_books(self):
        self.assertEqual(M.BOOK_N, 604)
        self.assertEqual(M.BOOK_SURVIVE, 450)
        self.assertEqual(M.BOOK_WTOUCH, 55)
        self.assertEqual(M.BOOK_LOSE, 99)
        self.assertEqual(M.DEC_N, 85)
        self.assertEqual(M.DEC_SURVIVE, 56)
        self.assertEqual(M.WINDOW_N, 508)
        self.assertEqual(M.WINDOW_SURVIVE, 384)
        self.assertEqual(M.WEEK50_SURVIVE / M.WEEK50_N, 5 / 11)

    def test_world_a_is_not_december(self):
        self.assertAlmostEqual(M.P_BAR_WORLD_A, 0.75 * 450 / 505, places=12)
        self.assertAlmostEqual(M.P_BAR_DEC, 56 / 85, places=12)
        self.assertNotAlmostEqual(M.P_BAR_WORLD_A, M.P_BAR_DEC, places=3)

    def test_clean_breakeven_is_two_thirds(self):
        self.assertAlmostEqual(M.CLEAN_BE, 2.0 / 3.0, places=12)

    def test_slip_breakeven_book_near_70_5(self):
        p = M.slip_breakeven_p(M.Q_WT_BOOK)
        self.assertGreater(p, 0.70)
        self.assertLess(p, 0.71)
        # 74.50% is above; World A and December are below.
        self.assertGreater(M.P_BAR_BOOK, p)
        self.assertLess(M.P_BAR_WORLD_A, p)
        self.assertLess(M.P_BAR_DEC, p)


class TestWeekBlocks(unittest.TestCase):
    def test_nov_apr_weeks_locked(self):
        w = M.week_blocks()
        self.assertEqual(len(w["n"]), 24)
        self.assertEqual(int(w["n"].sum()), 508)
        self.assertEqual(int(w["survive"].sum()), 384)
        self.assertAlmostEqual(w["week50_p"], 5 / 11, places=12)
        self.assertAlmostEqual(w["p_season"], 384 / 508, places=12)


class TestNaiveVsRealistic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = M.analyze()

    def test_naive_persist_matches_old_iid_table(self):
        n = self.s["naive_iid"]["persist_7450"]
        self.assertGreater(n["p_clean_gt0"], 0.995)
        self.assertGreater(n["p_slip_gt0"], 0.96)
        self.assertLess(n["p_slip_gt0"], 0.99)

    def test_naive_world_a_and_dec_are_the_old_small_numbers(self):
        a = self.s["naive_iid"]["world_a_6683"]
        d = self.s["naive_iid"]["december_6588"]
        self.assertGreater(a["p_clean_gt0"], 0.50)
        self.assertLess(a["p_clean_gt0"], 0.58)
        self.assertGreater(a["p_slip_gt0"], 0.015)
        self.assertLess(a["p_slip_gt0"], 0.05)
        self.assertGreater(d["p_clean_gt0"], 0.30)
        self.assertLess(d["p_clean_gt0"], 0.42)
        self.assertGreater(d["p_slip_gt0"], 0.005)
        self.assertLess(d["p_slip_gt0"], 0.035)

    def test_realistic_persist_is_below_naive_because_p_is_unknown(self):
        naive = self.s["naive_iid"]["persist_7450"]["p_slip_gt0"]
        real = self.s["realistic"]["persist_unknown_p"]["p_slip_gt0"]
        self.assertLess(real, naive - 0.02)
        self.assertGreater(real, 0.88)
        self.assertLess(real, 0.96)

    def test_realistic_losing_worlds_gain_tail_mass(self):
        a_naive = self.s["naive_iid"]["world_a_6683"]["p_slip_gt0"]
        d_naive = self.s["naive_iid"]["december_6588"]["p_slip_gt0"]
        a_real = self.s["realistic"]["world_a_known_mean"]["p_slip_gt0"]
        d_real = self.s["realistic"]["december_known_mean"]["p_slip_gt0"]
        self.assertGreater(a_real, a_naive)
        self.assertGreater(d_real, d_naive)
        self.assertGreater(a_real, 0.04)
        self.assertLess(a_real, 0.12)
        self.assertGreater(d_real, 0.03)
        self.assertLess(d_real, 0.10)

    def test_worlds_are_not_averaged(self):
        rows = self.s["table"]
        self.assertEqual(len(rows), 3)
        slips = [r["realistic_p_slip"] for r in rows]
        self.assertGreater(slips[0] - slips[1], 0.70)
        self.assertTrue(any("Do not average" in x for x in self.s["do_not"]))

    def test_seed_reproducible(self):
        again = M.analyze()
        self.assertEqual(
            again["realistic"]["persist_unknown_p"]["p_slip_gt0"],
            self.s["realistic"]["persist_unknown_p"]["p_slip_gt0"],
        )

    def test_no_fee_no_live(self):
        self.assertEqual(self.s["fee_cents"], 0)
        self.assertTrue(self.s["live_first01_unchanged"])
        self.assertEqual(self.s["l2"], "UNAVAILABLE")


class TestSlipFills(unittest.TestCase):
    def test_sequential_50_30_20_is_multinomial(self):
        rng = __import__("numpy").random.default_rng(0)
        n = __import__("numpy").full(50_000, 100)
        a, b, c = M._fill_losers(rng, n)
        self.assertAlmostEqual(float(a.mean()), 50.0, places=0)
        self.assertAlmostEqual(float(b.mean()), 30.0, places=0)
        self.assertAlmostEqual(float(c.mean()), 20.0, places=0)
        self.assertTrue(((a + b + c) == n).all())


if __name__ == "__main__":
    unittest.main()
