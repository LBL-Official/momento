#!/usr/bin/env python3
"""Unit math for conditional path decomp. Does not change live FIRST01."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import ncaab_conditional_path_decomp as M  # noqa: E402


class TestBins(unittest.TestCase):
    def test_clock(self):
        self.assertEqual(M.clock_bin(1, 1100.0), "H1_1")
        self.assertEqual(M.clock_bin(1, 400.0), "H1_2")
        self.assertEqual(M.clock_bin(2, 1100.0), "H2_OPEN")
        self.assertEqual(M.clock_bin(2, 600.0), "H2_MID")
        self.assertEqual(M.clock_bin(2, 120.0), "H2_LATE")
        self.assertEqual(M.clock_bin(3, 120.0), "OT")
        self.assertIsNone(M.clock_bin(1, None))

    def test_margin_and_price(self):
        self.assertEqual(M.margin_band(2.0), "M0_3")
        self.assertEqual(M.margin_band(7.0), "M4_7")
        self.assertEqual(M.margin_band(12.0), "M8_12")
        self.assertEqual(M.margin_band(18.0), "M13P")
        self.assertEqual(M.price_band(35.0), "P_LT40")
        self.assertEqual(M.price_band(80.0), "P75P")

    def test_residual_bucket_frozen(self):
        self.assertEqual(M.residual_bucket(-3.0), "EXTREME_NEG")
        self.assertEqual(M.residual_bucket(-1.5), "MOD_NEG")
        self.assertEqual(M.residual_bucket(0.2), "NORMAL")
        self.assertEqual(M.residual_bucket(2.0), "MOD_POS")
        self.assertEqual(M.residual_bucket(4.0), "EXTREME_POS")
        self.assertIsNone(M.residual_bucket(None))


class TestExpected(unittest.TestCase):
    def test_residual_is_observed_minus_beta_dm(self):
        self.assertAlmostEqual(M.residual(-6.0, 2.0, 1.5), -9.0)
        self.assertAlmostEqual(M.residual(-3.0, -2.0, 1.5), 0.0)

    def test_shrink_uses_cell_then_clock_then_global(self):
        b, src = M.shrink_beta(50, 1.8, 80, 1.2, 1.0)
        self.assertAlmostEqual(b, 1.8)
        self.assertEqual(src, "clock_margin")
        b, src = M.shrink_beta(10, 9.0, 80, 1.2, 1.0)
        self.assertAlmostEqual(b, 1.2)
        self.assertEqual(src, "clock")
        b, src = M.shrink_beta(10, 9.0, 5, 9.0, 1.0)
        self.assertAlmostEqual(b, 1.0)
        self.assertEqual(src, "global")

    def test_h1_vol_only_after_half(self):
        self.assertIsNone(M.h1_vol_for_period(1, 2.5))
        self.assertEqual(M.h1_vol_for_period(2, 2.5), 2.5)


class TestTransition(unittest.TestCase):
    def test_three_point_examples_are_distinct(self):
        self.assertEqual(M.trans_class(10.0, 7.0), "LEAD_SHRINK")
        self.assertEqual(M.trans_class(2.0, -1.0), "LEAD_TO_TRAIL")
        self.assertEqual(M.trans_class(-3.0, -6.0), "TRAIL_WIDEN")

    def test_variance_reduction(self):
        self.assertAlmostEqual(M.rel_reduction(80.0, 100.0), 0.2)
        self.assertFalse(
            0.04 >= M.MATERIAL_VAL_REDUCTION and 0.04 >= M.MATERIAL_OOS_REDUCTION
        )


class TestStatus(unittest.TestCase):
    def test_not_a_strategy(self):
        self.assertEqual(M.STATUS["level"], 2)
        self.assertFalse(M.STATUS["strategy_authorized"])
        self.assertFalse(M.STATUS["cell_selection_authorized"])
        self.assertTrue(M.STATUS["possession_unavailable"])
        self.assertEqual(M.STATUS["next_objective"], "STOP_THIS_BRANCH")
        self.assertEqual(
            M.STATUS["state_transition"], "EXPLANATORY_IMPROVEMENT_FAILED"
        )
        self.assertIn("RECOVERY_HYPOTHESIS_FAILED", M.STATUS["level_2"])


if __name__ == "__main__":
    unittest.main()
