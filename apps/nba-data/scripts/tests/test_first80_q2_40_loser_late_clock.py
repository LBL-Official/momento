#!/usr/bin/env python3
"""Binning tests for 2Q FIRST80→40 loser late-clock cut."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import first80_q2_40_loser_late_clock as L  # noqa: E402


class TestBins(unittest.TestCase):
    def test_exactly_6_is_in_last_6(self):
        self.assertTrue(L.hit_with_at_most_k_min(4, 360.0, 6))
        self.assertEqual(L.discrete_last6_bin(4, 360.0), "5:01–6:00")

    def test_just_over_6_is_before(self):
        self.assertFalse(L.hit_with_at_most_k_min(4, 360.1, 6))
        self.assertEqual(L.discrete_last6_bin(4, 360.1), "BEFORE_LAST_6")

    def test_q3_is_before(self):
        self.assertFalse(L.hit_with_at_most_k_min(3, 10.0, 6))
        self.assertEqual(L.discrete_last6_bin(3, 10.0), "BEFORE_LAST_6")

    def test_ot_is_not_k_min_4q(self):
        self.assertFalse(L.hit_with_at_most_k_min(5, 120.0, 6))
        self.assertEqual(L.discrete_last6_bin(5, 120.0), "OT")

    def test_nested_minutes(self):
        self.assertTrue(L.hit_with_at_most_k_min(4, 60.0, 6))
        self.assertTrue(L.hit_with_at_most_k_min(4, 60.0, 1))
        self.assertFalse(L.hit_with_at_most_k_min(4, 61.0, 1))
        self.assertEqual(L.discrete_last6_bin(4, 61.0), "1:01–2:00")
        self.assertEqual(L.discrete_last6_bin(4, 0.0), "0:00–1:00")

    def test_identity(self):
        s = L.analyze()
        self.assertEqual(s["n_losers"], 47)
        self.assertEqual(s["identity"]["q2"], 314)
        self.assertEqual(sum(b["n"] for b in s["discrete_bins"]), 47)

    def test_q3_identity(self):
        nba = L.analyze_nba_quarters()
        by = {s["bucket"]: s for s in nba["slices"]}
        self.assertEqual(by["Q3"]["n"], 290)
        self.assertEqual(by["Q3"]["n_losers"], 52)
        self.assertEqual(by["Q3"]["n_t40"], 79)
        self.assertEqual(sum(b["n"] for b in by["Q3"]["discrete_bins"]), 52)

    def test_ncaab_closing_period(self):
        self.assertTrue(L.hit_with_at_most_k_min(2, 360.0, 6, closing_period=2, ot_min_period=3))
        self.assertFalse(L.hit_with_at_most_k_min(1, 10.0, 6, closing_period=2, ot_min_period=3))
        self.assertEqual(
            L.discrete_last6_bin(3, 120.0, closing_period=2, ot_min_period=3),
            "OT",
        )


if __name__ == "__main__":
    unittest.main()
