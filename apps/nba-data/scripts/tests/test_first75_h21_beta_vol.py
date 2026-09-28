#!/usr/bin/env python3
"""Unit math for post-FIRST75 β / vol. Does not change live FIRST01."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import first75_h21_beta_vol as M  # noqa: E402


class TestOls(unittest.TestCase):
    def test_slope_two(self):
        rec = M.ols_slope([0.0, 1.0, 2.0, 3.0], [0.0, 2.0, 4.0, 6.0])
        self.assertAlmostEqual(rec["beta"], 2.0)
        self.assertAlmostEqual(rec["intercept"], 0.0)
        self.assertAlmostEqual(rec["r"], 1.0)

    def test_empty(self):
        rec = M.ols_slope([], [])
        self.assertIsNone(rec["beta"])


class TestScoring(unittest.TestCase):
    def test_steps_after_tau(self):
        actions = [
            {"modeled_wall_ts": 10, "score_home": 40, "score_away": 38},
            {"modeled_wall_ts": 20, "score_home": 43, "score_away": 38},
            {"modeled_wall_ts": 30, "score_home": 43, "score_away": 41},
        ]
        steps = M.scoring_steps(actions, tau=15, team_is_home=True)
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0]["d_margin"], 3.0)
        self.assertEqual(steps[1]["d_margin"], -3.0)

    def test_bar_pairs_uses_score_change(self):
        quotes = [
            {"ts": 20, "bid_c": 7600, "ask_c": 7700, "vol": 100},
            {"ts": 80, "bid_c": 7800, "ask_c": 7900, "vol": 100},
        ]
        actions = [
            {"idx": 0, "modeled_wall_ts": 20, "score_home": 50, "score_away": 48},
            {"idx": 1, "modeled_wall_ts": 80, "score_home": 52, "score_away": 48},
        ]

        def snap(acts, ts):
            return {"snap_idx": 0 if ts <= 20 else 1}

        pairs = M.bar_pairs(quotes, actions, tau=10, window_s=600, team_is_home=True, snap_fn=snap)
        self.assertEqual(pairs, [(2.0, 2.0)])

    def test_bar_pairs_carries_zero_zero_reset(self):
        quotes = [
            {"ts": 20, "bid_c": 7600, "ask_c": 7700, "vol": 100},
            {"ts": 80, "bid_c": 7800, "ask_c": 7900, "vol": 100},
            {"ts": 140, "bid_c": 8000, "ask_c": 8100, "vol": 100},
        ]
        actions = [
            {"idx": 0, "modeled_wall_ts": 20, "score_home": 50, "score_away": 48},
            {"idx": 1, "modeled_wall_ts": 80, "score_home": 0, "score_away": 0},
            {"idx": 2, "modeled_wall_ts": 140, "score_home": 52, "score_away": 48},
        ]

        def snap(acts, ts):
            if ts <= 20:
                return {"snap_idx": 0}
            if ts <= 80:
                return {"snap_idx": 1}
            return {"snap_idx": 2}

        pairs = M.bar_pairs(quotes, actions, tau=10, window_s=600, team_is_home=True, snap_fn=snap)
        self.assertEqual(pairs, [(2.0, 2.0)])


class TestBetaGate(unittest.TestCase):
    def test_collapsed_nba_unusable(self):
        self.assertFalse(M.beta_usable({"beta": 0.014, "r": 0.05}))
        self.assertTrue(M.beta_usable({"beta": 1.49, "r": 0.78}))


if __name__ == "__main__":
    unittest.main()
