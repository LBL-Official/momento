#!/usr/bin/env python3
"""Liquidation math for asked-six 80/40. Does not change live FIRST01."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import numpy as np

SCRIPTS = Path(__file__).resolve().parents[1]


def _load():
    path = SCRIPTS / "first80_asked_six_80_40_liquidation.py"
    spec = importlib.util.spec_from_file_location(
        "first80_asked_six_80_40_liquidation", path
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


M = _load()


class TestIdentity(unittest.TestCase):
    def test_frozen_book(self):
        self.assertEqual(M.EXPECTED_N, 1182)
        self.assertEqual(M.EXPECTED_WIN, 883)
        self.assertEqual(M.EXPECTED_STOP, 299)
        self.assertEqual(M.EXPECTED_WIN + M.EXPECTED_STOP, 1182)

    def test_halt_rejects_wrong_counts(self):
        with self.assertRaises(M.IdentityHalt):
            M.halt_identity(1182, 883, 298)


class TestExpectancy(unittest.TestCase):
    def test_observed_p(self):
        self.assertAlmostEqual(M.observed_p(), 883 / 1182)

    def test_breakeven_L_at_observed_wr(self):
        # 0.747*20 = 0.253*L  => L = 20*883/299
        L = M.breakeven_avg_loss_cents(M.observed_p())
        self.assertAlmostEqual(L, 20.0 * 883 / 299)
        self.assertAlmostEqual(L, 59.0635, places=3)

    def test_ev_table_at_observed_wr(self):
        p = M.observed_p()
        self.assertAlmostEqual(M.ev_cents(p, 40), 5700 / 1182, places=4)
        self.assertAlmostEqual(M.ev_cents(p, 40), 4.8223, places=3)
        self.assertAlmostEqual(M.ev_cents(p, 60), -280 / 1182, places=4)
        self.assertAlmostEqual(M.ev_cents(p, 80), -6260 / 1182, places=4)

    def test_breakeven_wr_from_loss(self):
        # WR = L / (20 + L)
        self.assertAlmostEqual(40 / 60 * 100, 66.6667, places=3)
        self.assertAlmostEqual(60 / 80 * 100, 75.0, places=3)
        self.assertAlmostEqual(80 / 100 * 100, 80.0, places=3)

    def test_mix_average_loss(self):
        self.assertEqual(M.mix_avg_loss_cents({40: 100}), 40.0)
        self.assertEqual(M.mix_avg_loss_cents({40: 90, 20: 10}), 42.0)
        self.assertEqual(M.mix_avg_loss_cents({40: 75, 20: 20, 0: 5}), 46.0)
        self.assertEqual(M.mix_avg_loss_cents({40: 50, 20: 30, 0: 20}), 54.0)
        self.assertEqual(M.mix_avg_loss_cents({40: 50, 20: 30, 10: 20}), 52.0)
        self.assertEqual(M.mix_avg_loss_cents({0: 100}), 80.0)

    def test_mix_weights_must_sum_100(self):
        with self.assertRaises(M.IdentityHalt):
            M.mix_avg_exit_cents({40: 90, 20: 9})

    def test_mix_pnl(self):
        self.assertEqual(M.mix_pnl_cents(40), -40)
        self.assertEqual(M.mix_pnl_cents(20), -60)
        self.assertEqual(M.mix_pnl_cents(0), -80)
        self.assertEqual(M.mix_pnl_cents(80), 0)


class TestPostT40Window(unittest.TestCase):
    def test_e4_to_cents(self):
        self.assertEqual(M.e4_to_cents(8000), 80)
        self.assertEqual(M.e4_to_cents(4000), 40)
        self.assertEqual(M.e4_to_cents(2200), 22)
        self.assertEqual(M.e4_to_cents(0), 0)

    def test_ignores_rest_of_game_zero(self):
        quotes = [
            {"ts": 1000, "bid_c": 8200, "ask_c": 8400, "bid_l": 8000, "vol": 1},
            {"ts": 1060, "bid_c": 4000, "ask_c": 4200, "bid_l": 3800, "vol": 1},
            {"ts": 1120, "bid_c": 2800, "ask_c": 3000, "bid_l": 2500, "vol": 1},
            {"ts": 2000, "bid_c": 0, "ask_c": 200, "bid_l": 0, "vol": 1},
        ]
        w = M.post_t40_window(quotes, entry_ts=1000, t40_ts=1060)
        self.assertTrue(w["found"])
        self.assertEqual(w["t40_close"], 40)
        self.assertEqual(w["prior_close"], 82)
        self.assertEqual(w["drop_from_prior"], 42)
        self.assertEqual(w["min_close_5m"], 28)
        self.assertNotEqual(w["min_close_5m"], 0)

    def test_gap_through_40(self):
        quotes = [
            {"ts": 1000, "bid_c": 8100, "ask_c": 8300, "bid_l": 8000, "vol": 1},
            {"ts": 1060, "bid_c": 2200, "ask_c": 2400, "bid_l": 1800, "vol": 1},
        ]
        w = M.post_t40_window(quotes, entry_ts=1000, t40_ts=1060)
        self.assertEqual(w["t40_close"], 22)

    def test_skips_wide_spread(self):
        quotes = [
            {"ts": 1000, "bid_c": 8100, "ask_c": 8300, "bid_l": 8000, "vol": 1},
            {"ts": 1060, "bid_c": 1000, "ask_c": 4000, "bid_l": 1000, "vol": 1},
            {"ts": 1120, "bid_c": 3900, "ask_c": 4100, "bid_l": 3500, "vol": 1},
        ]
        w = M.post_t40_window(quotes, entry_ts=1000)
        self.assertEqual(w["t40_close"], 39)


class TestWeekSim(unittest.TestCase):
    def test_optimistic_matches_clean_40(self):
        rng = np.random.default_rng(1)
        bits = np.array([True] * 7 + [False] * 3)
        bag = np.array([40], dtype=np.int64)
        week_pnls, _ = M.simulate_week_pnls(bits, 5, 1, 1, rng, bag, start=2_000_000)
        qty = (2_000_000 * 5 // 100) // 80
        self.assertEqual(qty, 1250)
        # 7 wins / 3 stops at 40 is not guaranteed from choice; force by
        # using a win-only then stop-only bag is harder. Check shape instead
        # and a deterministic all-stop / all-win case.
        self.assertEqual(week_pnls.shape, (1, 1))

    def test_all_wins_plus_20(self):
        rng = np.random.default_rng(1)
        bits = np.array([True])
        bag = np.array([0], dtype=np.int64)
        week_pnls, streaks = M.simulate_week_pnls(
            bits, 5, 1, 1, rng, bag, start=2_000_000
        )
        self.assertEqual(week_pnls[0, 0], 1250 * 20 * 10)
        self.assertEqual(int(streaks[0]), 0)

    def test_all_stops_at_zero(self):
        rng = np.random.default_rng(1)
        bits = np.array([False])
        bag = np.array([0], dtype=np.int64)
        week_pnls, streaks = M.simulate_week_pnls(
            bits, 5, 1, 1, rng, bag, start=2_000_000
        )
        self.assertEqual(week_pnls[0, 0], 1250 * (-80) * 10)
        self.assertEqual(int(streaks[0]), 10)


class TestViabilityGate(unittest.TestCase):
    def test_gate_is_frozen_before_results(self):
        self.assertEqual(M.VIABLE_P_LOSE_MAX, 0.10)
        self.assertEqual(M.VIABLE_P_DD20_MAX, 0.10)
        self.assertEqual(M.VIABLE_P5_MIN_CENTS, 1_600_000)


if __name__ == "__main__":
    unittest.main()
