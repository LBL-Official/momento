#!/usr/bin/env python3
"""Tests for combined-book dependence and cap-architecture stress."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import first80_dual_sport_portfolio_stress as M  # noqa: E402


class TestEmpiricalAndCaps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.days, cls.nba_by, cls.ncaab_by = M._rows_by_day()
        cls.emp = M.empirical_same_night(cls.days, cls.nba_by, cls.ncaab_by)
        cls.arch = M.architecture_taken(cls.days, cls.nba_by, cls.ncaab_by)

    def test_overlap_and_joint_crashes(self):
        self.assertEqual(self.emp["n_both_sport_days"], 82)
        self.assertEqual(self.emp["joint_below_two_thirds"]["n_joint_bad"], 2)
        self.assertLess(self.emp["pearson_p_bar"], 0.05)
        # Last year did not show positive same-night tail dependence.
        j = self.emp["joint_below_two_thirds"]
        self.assertLessEqual(j["n_joint_bad"], 4)

    def test_architectures_lock_exposure(self):
        a = self.arch["cap_6_plus_6"]
        b = self.arch["cap_combined_6"]
        c = self.arch["cap_hier_8"]
        self.assertEqual(a["n_taken"], 768)
        self.assertEqual(a["max_sod_pct"], 60)
        self.assertEqual(b["n_taken"], 668)
        self.assertEqual(b["max_sod_pct"], 30)
        self.assertEqual(c["n_taken"], 729)
        self.assertEqual(c["max_sod_pct"], 40)
        self.assertLess(b["n_taken"], a["n_taken"])
        self.assertLess(c["n_taken"], a["n_taken"])
        self.assertGreater(c["n_taken"], b["n_taken"])


class TestSharedFactorSmoke(unittest.TestCase):
    def test_alpha_zero_is_finite_and_alpha_high_is_worse_left_tail(self):
        days, nba_by, ncaab_by = M._rows_by_day()
        arch = M.architecture_taken(days, nba_by, ncaab_by)
        rec = arch["cap_6_plus_6"]
        # Small n so this stays a unit test.
        old = M.N_SIM
        M.N_SIM = 256
        try:
            z = M.simulate_shared_factor(rec["nba_taken"], rec["ncaab_taken"], days, 0.0, 1)
            h = M.simulate_shared_factor(rec["nba_taken"], rec["ncaab_taken"], days, 0.20, 2)
        finally:
            M.N_SIM = old
        self.assertGreater(z["terminal"]["percentiles_dollars"]["p50"], 20_000)
        self.assertGreater(
            h["risk_of_ruin"]["p95_max_dd_pct"],
            z["risk_of_ruin"]["p95_max_dd_pct"] - 1.0,
        )


if __name__ == "__main__":
    unittest.main()
