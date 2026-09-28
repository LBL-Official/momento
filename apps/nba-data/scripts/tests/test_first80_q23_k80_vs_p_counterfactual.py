#!/usr/bin/env python3
"""Tests for 2Q/3Q K=80 vs observed P and P=0.75 counterfactual."""

from __future__ import annotations

import sys
import unittest
from fractions import Fraction
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import first80_q23_k80_vs_p_counterfactual as M  # noqa: E402


class TestObservedP(unittest.TestCase):
    def test_combined_identity_and_definitions(self):
        s = M.analyze()
        c = next(x for x in s["cells"] if x["cell"] == "2Q+3Q")
        self.assertEqual(c["n"], 604)
        self.assertEqual(c["w"], 505)
        self.assertEqual(c["w_not"], 450)
        self.assertEqual(c["lose"], 99)
        self.assertEqual(c["l_not"], 0)
        p = c["observed_p"]
        self.assertEqual(p["K_cents"], 80)
        self.assertAlmostEqual(p["P_term_pct"], 83.6093, places=3)
        self.assertAlmostEqual(p["P_bar_pct"], 74.5033, places=3)
        self.assertAlmostEqual(p["P_bar_given_W_pct"], 89.1089, places=3)
        self.assertLess(p["K_cents"], p["P_term"] * 100)

    def test_k_is_not_p(self):
        s = M.analyze()
        for cell in s["cells"]:
            self.assertNotAlmostEqual(cell["observed_p"]["P_term"], 0.80, places=2)


class TestFutureP75(unittest.TestCase):
    def test_world_a_combined_loses_slip_edge(self):
        s = M.analyze()
        a = next(x for x in s["cells"] if x["cell"] == "2Q+3Q")["future_p75_world_A"]
        self.assertAlmostEqual(a["P_term"], 0.75, places=6)
        self.assertFalse(a["has_slip_edge"])
        self.assertLess(a["ev_slip_cents"], 0)

    def test_world_s_combined_keeps_thin_slip_edge(self):
        s = M.analyze()
        w = next(x for x in s["cells"] if x["cell"] == "2Q+3Q")["future_p75_world_S"]
        self.assertAlmostEqual(w["P_term"], 0.75, places=6)
        self.assertAlmostEqual(w["P_bar"], 450 / 604, places=6)
        self.assertEqual(w["required_loser_no_t40"], False)
        self.assertTrue(w["has_slip_edge"])

    def test_q2_world_s_needs_loser_no_t40(self):
        s = M.analyze()
        q2 = next(x for x in s["cells"] if x["cell"] == "2Q")
        self.assertGreater(q2["observed_p"]["P_bar"], 0.75)
        self.assertTrue(q2["future_p75_world_S"]["required_loser_no_t40"])

    def test_tiny_book_world_a_formula(self):
        c = {"n": 100, "w": 80, "w_not": 70, "w_touch": 10, "lose": 20, "t40": 30, "l_not": 0}
        a = M.world_a_path_conditionals_held(c, Fraction(75, 100))
        # W=75, ¬T40|W=70/80, survive=65.625, wt=9.375, L=25
        # 65.625*20 + 9.375*(-40) + 25*(-52) = 1312.5 - 375 - 1300 = -362.5
        self.assertAlmostEqual(a["ev_slip_cents"], -3.625, places=3)


if __name__ == "__main__":
    unittest.main()
