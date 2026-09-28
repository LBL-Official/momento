#!/usr/bin/env python3
"""Tests for 2Q/3Q Nov–Apr daily-compound portfolio sim."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import first80_q23_novapr_portfolio_sim as S  # noqa: E402


class TestWindowAndMix(unittest.TestCase):
    def test_nov_apr_identity(self):
        rows = S.window_rows()
        self.assertEqual(len(rows), 508)
        arr = S.arrival_from_window(rows)
        self.assertEqual(arr["n_trades"], 508)
        self.assertEqual(arr["n_trades_capped"], 499)
        self.assertEqual(arr["n_dropped_over_cap"], 9)
        self.assertEqual(arr["days_over_cap"], 9)
        self.assertEqual(arr["n_iso_weeks"], 24)
        self.assertEqual(arr["max_same_day"], 7)
        self.assertEqual(arr["max_same_day_traded"], 6)
        self.assertEqual(arr["window_class"]["survive"], 384)
        self.assertEqual(arr["window_class"]["winner_touch"], 44)
        self.assertEqual(arr["window_class"]["lose"], 80)

    def test_raw_mix_is_50_30_20_then_haircut_to_3pct(self):
        self.assertEqual(S.loser_mix_pnl_cents(), -52)
        self.assertEqual(S.LOSE_AT_40_WGT, 50)
        self.assertEqual(S.LOSE_AT_20_WGT, 30)
        self.assertEqual(S.LOSE_AT_10_WGT, 20)
        self.assertAlmostEqual(S.expected_debit_return_pct(), 3.4189, places=3)
        self.assertEqual(S.CONSERVATIVE_DEBIT_RETURN_PCT, 3)
        self.assertEqual(sum(S.WEIGHTS_6040), 6040)
        # 1,652¢ raw book * 1812/2065 = 1,449.6¢ = 2.4¢ * 604
        scaled = S.apply_conservative_edge(np.array([S.RAW_BOOK_SUM_CENTS], dtype=np.int64))
        self.assertEqual(int(scaled[0]), 1450)

    def test_exit_signal_is_still_t40(self):
        self.assertEqual(S.PNL_WTOUCH, -40)
        self.assertEqual(S.PNL_L40, -40)
        self.assertEqual(S.PNL_L20, -60)
        self.assertEqual(S.PNL_L10, -70)
        # Slip classes are fills on the 40 signal, not a later 20/10 stop.


class TestMoney(unittest.TestCase):
    def test_start_is_1250_contracts(self):
        self.assertEqual(S.contracts_from_bankroll_cents(S.B0_CENTS), 1250)

    def test_same_day_does_not_resize(self):
        # 2 survivors same day: 1250*(20+20)=50_000 cents, then one −70 next day.
        daily_n = [2, 1]
        # Force outcomes: survive, survive, lose_10
        rng_draws = np.array([[0, 0, 4]], dtype=np.int64)
        pnl = S.PNL_TABLE[rng_draws]
        b = np.array([S.B0_CENTS], dtype=np.int64)
        cursor = 0
        for n in daily_n:
            contracts = (b * S.FRACTION_PCT // 100) // S.ENTRY_CENTS
            b = b + contracts * pnl[:, cursor : cursor + n].sum(axis=1)
            cursor += n
        self.assertEqual(int(b[0]), 1_960_330)

    def test_naive_3pct_two_trades_one_day(self):
        # 1250 contracts * 2.4¢ * 2 = 6_000 cents → $20,060
        self.assertEqual(S.naive_3pct_end_cents([2]), 2_006_000)

    def test_day_cap_is_6_bets_not_5pct_per_day(self):
        self.assertEqual(S.MAX_TRADES_PER_DAY, 6)
        self.assertEqual(S.MAX_DAY_FRACTION_PCT, 30)
        self.assertEqual(S.cap_daily_n([0, 1, 6, 7, 10]), [0, 1, 6, 6, 6])
        # 7th print is not taken: 6 * $30 = $180, not 7 * $30
        self.assertEqual(S.naive_3pct_end_cents([7]), 2_018_000)

    def test_seven_survivors_pay_six_bets(self):
        daily_n = [7]
        pnl = S.PNL_TABLE[np.zeros((1, 6), dtype=np.int64)]
        b = np.array([S.B0_CENTS], dtype=np.int64)
        contracts = (b * S.FRACTION_PCT // 100) // S.ENTRY_CENTS
        taken = S.cap_daily_n(daily_n)[0]
        b = b + contracts * pnl[:, :taken].sum(axis=1)
        self.assertEqual(int(contracts[0]), 1250)
        self.assertEqual(taken, 6)
        self.assertEqual(int(b[0]), 2_150_000)


class TestSimSmoke(unittest.TestCase):
    def test_small_sim_stays_positive_and_reproducible(self):
        a = S.simulate_paths([2, 0, 3, 1], n_sim=64, seed=1)
        b = S.simulate_paths([2, 0, 3, 1], n_sim=64, seed=1)
        self.assertTrue(np.array_equal(a["end_cents"], b["end_cents"]))
        self.assertTrue(np.all(a["end_cents"] > 0))
        self.assertTrue(np.all(a["min_cents"] > 0))


if __name__ == "__main__":
    unittest.main()
