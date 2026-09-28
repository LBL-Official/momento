#!/usr/bin/env python3
"""Tests for P5 H1_2 ∪ H2_1 FIRST80 P(season EV>0)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import first80_p5_h12_h21_profit_likelihood as M  # noqa: E402
import first80_q23_profit_likelihood as NBA  # noqa: E402


class TestIdentities(unittest.TestCase):
    def test_frozen_h12_h21_book(self):
        self.assertEqual(M.BOOK_N, 332)
        self.assertEqual(M.BOOK_W, 281)
        self.assertEqual(M.BOOK_SURVIVE, 250)
        self.assertEqual(M.BOOK_WTOUCH, 31)
        self.assertEqual(M.BOOK_LOSE, 51)
        self.assertEqual(M.H12_N + M.H21_N, 332)
        self.assertEqual(M.DEC_SURVIVE / M.DEC_N, 24 / 31)
        self.assertEqual(M.JAN_SURVIVE / M.JAN_N, 72 / 101)

    def test_world_a_is_not_december(self):
        self.assertAlmostEqual(M.P_BAR_WORLD_A, 0.75 * 250 / 281, places=12)
        self.assertAlmostEqual(M.P_BAR_DEC, 24 / 31, places=12)
        self.assertGreater(M.P_BAR_DEC, M.P_BAR_BOOK)
        self.assertLess(M.P_BAR_WORLD_A, M.P_BAR_BOOK)
        self.assertLess(M.P_BAR_JAN, M.P_BAR_BOOK)
        self.assertGreater(M.P_BAR_JAN, M.P_BAR_WORLD_A)

    def test_same_slip_hurdles_as_nba(self):
        self.assertAlmostEqual(NBA.CLEAN_BE, 2.0 / 3.0, places=12)
        p = NBA.slip_breakeven_p(M.Q_WT_BOOK)
        self.assertGreater(p, 0.70)
        self.assertLess(p, 0.71)
        self.assertGreater(M.P_BAR_BOOK, p)
        self.assertLess(M.P_BAR_WORLD_A, p)
        self.assertGreater(M.P_BAR_DEC, p)
        self.assertGreater(M.P_BAR_JAN, p)


class TestCalendar(unittest.TestCase):
    def test_season_weeks_and_6_cap(self):
        rows = M.load_book_rows()
        caps = M.cap_stats(rows)
        weeks = M.week_blocks(rows)
        self.assertEqual(caps["n_taken"], 269)
        self.assertEqual(caps["n_dropped"], 63)
        self.assertEqual(caps["days_over_cap"], 21)
        self.assertEqual(len(weeks["n"]), 21)
        self.assertAlmostEqual(weeks["worst_week_p"], 7 / 12, places=12)
        self.assertEqual(weeks["december"]["n"], 31)
        self.assertEqual(weeks["january"]["n"], 101)


class TestNaiveVsRealistic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = M.analyze()

    def test_naive_persist_is_high_but_smaller_n_than_nba(self):
        n = self.s["naive_iid"]["persist"]
        self.assertEqual(self.s["naive_iid"]["n"], 269)
        self.assertGreater(n["p_clean_gt0"], 0.98)
        self.assertGreater(n["p_slip_gt0"], 0.88)
        self.assertLess(n["p_slip_gt0"], 0.97)

    def test_realistic_persist_is_below_naive(self):
        naive = self.s["naive_iid"]["persist"]["p_slip_gt0"]
        real = self.s["realistic"]["persist_unknown_p"]["p_slip_gt0"]
        self.assertLess(real, naive - 0.02)
        self.assertGreater(real, 0.70)
        self.assertLess(real, 0.92)

    def test_world_a_is_still_a_losing_book(self):
        a = self.s["realistic"]["world_a_known_mean"]
        self.assertLess(a["p_slip_gt0"], 0.15)
        self.assertLess(a["ev_slip_p50"], 0)

    def test_december_is_not_the_crash(self):
        d = self.s["realistic"]["december_known_mean"]
        p = self.s["realistic"]["persist_unknown_p"]
        self.assertGreater(d["p_slip_gt0"], p["p_slip_gt0"])
        self.assertGreater(d["ev_slip_p50"], 0)

    def test_january_is_the_thin_month(self):
        j = self.s["realistic"]["january_known_mean"]
        d = self.s["realistic"]["december_known_mean"]
        a = self.s["realistic"]["world_a_known_mean"]
        self.assertLess(j["p_slip_gt0"], d["p_slip_gt0"])
        self.assertGreater(j["p_slip_gt0"], a["p_slip_gt0"])

    def test_vs_nba_world_a_is_the_same_kind_of_object(self):
        ncaab_a = self.s["realistic"]["world_a_known_mean"]["p_slip_gt0"]
        nba_a = self.s["vs_nba_q23"]["nba_realistic_p_slip"]["world_a"]
        self.assertLess(abs(ncaab_a - nba_a), 0.08)

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
        self.assertTrue(any("Do not average" in x for x in self.s["do_not"]))


if __name__ == "__main__":
    unittest.main()
