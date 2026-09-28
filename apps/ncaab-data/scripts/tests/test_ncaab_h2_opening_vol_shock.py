#!/usr/bin/env python3
"""Unit math for NCAAB P5 H2 opening vol-shock. Does not change live FIRST01."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import ncaab_h2_opening_vol_shock as M  # noqa: E402


class TestBaseline(unittest.TestCase):
    def test_p80_and_z(self):
        diffs = [1.0, -1.0, 2.0, -2.0, 3.0, -1.0, 4.0, -2.0]
        b = M.h1_baseline(diffs)
        self.assertEqual(b["n"], 8)
        self.assertAlmostEqual(b["mean_abs"], 2.0)
        self.assertGreater(b["p80_abs"], 2.0)
        z = M.z_vol(4.0, b)
        self.assertIsNotNone(z["z_abs"])
        self.assertGreater(z["r_shock"], 1.0)

    def test_thin_rejected(self):
        self.assertIsNone(M.h1_baseline([1.0, -1.0, 2.0]))


class TestClockWindow(unittest.TestCase):
    def test_h2_open(self):
        self.assertTrue(M.in_h2_open(2, 1200.0, "IN_PERIOD"))
        self.assertTrue(M.in_h2_open(2, 901.0, "IN_PERIOD"))
        self.assertFalse(M.in_h2_open(2, 900.0, "IN_PERIOD"))
        self.assertFalse(M.in_h2_open(2, 1199.0, "INTERMISSION"))
        self.assertFalse(M.in_h2_open(1, 1100.0, "IN_PERIOD"))

    def test_h1_in_period(self):
        self.assertTrue(M.in_h1_baseline(1, "IN_PERIOD"))
        self.assertFalse(M.in_h1_baseline(1, "INTERMISSION"))
        self.assertFalse(M.in_h1_baseline(2, "IN_PERIOD"))


class TestScoreTags(unittest.TestCase):
    def test_lead_shrink_example(self):
        rec = M.score_tags(m_pre=8.0, m_post=5.0)
        self.assertEqual(rec["abs_dm"], 3.0)
        self.assertAlmostEqual(rec["pct_abs_dm"], 0.375)
        self.assertTrue(rec["bounded_info"])
        self.assertTrue(rec["prop_band"])
        self.assertTrue(rec["deterioration"])
        self.assertTrue(rec["close_10"])
        self.assertFalse(rec["close_5"])

    def test_near_zero_pct_suppressed(self):
        rec = M.score_tags(m_pre=2.0, m_post=1.0)
        self.assertTrue(rec["bounded_info"])
        self.assertIsNone(rec["pct_abs_dm"])
        self.assertFalse(rec["prop_band"])

    def test_blowout_not_close(self):
        rec = M.score_tags(m_pre=18.0, m_post=15.0)
        self.assertTrue(rec["bounded_info"])
        self.assertFalse(rec["close_12"])


class TestAdversePick(unittest.TestCase):
    def test_argmin(self):
        side, tie = M.pick_adverse({"home": -3.0, "away": 2.0})
        self.assertEqual(side, "home")
        self.assertFalse(tie)

    def test_tie(self):
        side, tie = M.pick_adverse({"home": -1.0, "away": -1.0})
        self.assertIsNone(side)
        self.assertTrue(tie)


class TestVolNorm(unittest.TestCase):
    def test_returns_toward_mean(self):
        self.assertTrue(M.vol_normalized(1.2, 2.0))
        self.assertFalse(M.vol_normalized(2.1, 2.0))
        self.assertIsNone(M.vol_normalized(None, 2.0))


class TestIdentity(unittest.TestCase):
    def test_p5_gate(self):
        self.assertEqual(M.P5_GAMES_EXPECTED, 849)

    def test_verdict_negative_and_closed(self):
        self.assertEqual(M.VERDICT["status"], "NEGATIVE")
        self.assertFalse(M.VERDICT["further_optimization_authorized"])
        self.assertFalse(M.VERDICT["entry_rule_authorized"])
        self.assertEqual(M.VERDICT["close_5"], "DESCRIPTIVE_OBSERVATION")


class TestPairs(unittest.TestCase):
    def test_gap_rejects_halftime(self):
        qs = [
            {"ts": 100, "bid_c": 6000, "ask_c": 6100, "vol": 1},
            {"ts": 1000, "bid_c": 5500, "ask_c": 5600, "vol": 1},
        ]
        pairs = M.quality_pairs(qs, max_gap_s=90)
        self.assertEqual(pairs, [])

    def test_minute_pair(self):
        qs = [
            {"ts": 100, "bid_c": 6000, "ask_c": 6100, "vol": 1},
            {"ts": 160, "bid_c": 5700, "ask_c": 5800, "vol": 1},
        ]
        pairs = M.quality_pairs(qs, max_gap_s=90)
        self.assertEqual(len(pairs), 1)
        self.assertAlmostEqual(pairs[0]["dp_cents"], -3.0)


if __name__ == "__main__":
    unittest.main()
