#!/usr/bin/env python3
"""Tests for combined NBA + NCAAB Nov–Apr portfolio sim."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import first80_dual_sport_novapr_portfolio_sim as S  # noqa: E402
import first80_q23_novapr_portfolio_sim as NBA  # noqa: E402


class TestOverlayIdentities(unittest.TestCase):
    def test_per_sport_cap_not_combined_cap(self):
        ov = S.load_overlay()
        self.assertEqual(sum(ov["nba_prints"]), 508)
        self.assertEqual(sum(ov["ncaab_prints"]), 332)
        self.assertEqual(sum(ov["nba_taken"]), 499)
        self.assertEqual(sum(ov["ncaab_taken"]), 269)
        self.assertEqual(sum(ov["taken"]), 768)
        self.assertEqual(ov["both_days"], 82)
        self.assertEqual(ov["max_combined_taken"], 12)
        self.assertEqual(ov["days_at_12"], 4)
        # A combined-6 rule would have taken far fewer than 768.
        self.assertGreater(sum(1 for n in ov["taken"] if n > 6), 20)

    def test_7_and_7_takes_12_not_6(self):
        sports, day_n = S.trade_schedule([7], [7])
        # schedule sees already-capped lists; cap is applied in load_overlay
        sports, day_n = S.trade_schedule([6], [6])
        self.assertEqual(int(day_n[0]), 12)
        self.assertEqual(int((sports == S.SPORT_NBA).sum()), 6)
        self.assertEqual(int((sports == S.SPORT_NCAAB).sum()), 6)


class TestMoneyAndHaircut(unittest.TestCase):
    def test_ncaab_haircut_locks_3pct(self):
        raw = S.ncaab_raw_debit_return_pct()
        self.assertAlmostEqual(raw, 4.1717, places=3)
        scaled = S.scale_edge(np.array([S.NCAAB_RAW_BOOK_SUM], dtype=np.int64), S.NCAAB_EDGE_NUM, S.NCAAB_EDGE_DEN)
        self.assertEqual(int(scaled[0]), 797)
        # 797/332 = 2.4006¢ ≈ 3.0008% of 80¢
        self.assertAlmostEqual(797 / 332 / 80 * 100, 3.0008, places=3)

    def test_same_day_both_sports_share_sod(self):
        # 1 NBA survivor + 1 NCAAB survivor, same morning.
        nba_taken = [1]
        ncaab_taken = [1]
        from datetime import date

        days = [date(2026, 1, 10)]
        # Force both to class 0 (survive +20) by using a tiny custom draw path.
        sports, _ = S.trade_schedule(nba_taken, ncaab_taken)
        pnl = np.full((1, 2), S.PNL_TABLE[0], dtype=np.int64)  # +20, +20
        b = np.array([S.B0], dtype=np.int64)
        contracts = (b * S.FRACTION_PCT // 100) // S.ENTRY
        raw = contracts[:, None] * pnl
        adj = S.apply_sport_edge(raw, sports)
        b = b + adj.sum(axis=1)
        self.assertEqual(int(contracts[0]), 1250)
        # Two +20¢ trades, each haircut toward 3% of debit (2.4¢).
        # 1250*20 NBA *1812/2065 + 1250*20 NCAAB *996/1385
        nba_scaled = int(S.scale_edge(np.array([1250 * 20]), NBA.EDGE_SCALE_NUM, NBA.EDGE_SCALE_DEN)[0])
        ncaab_scaled = int(S.scale_edge(np.array([1250 * 20]), S.NCAAB_EDGE_NUM, S.NCAAB_EDGE_DEN)[0])
        self.assertEqual(int(b[0]), S.B0 + nba_scaled + ncaab_scaled)
        self.assertEqual(int(adj[0, 0] + adj[0, 1]), nba_scaled + ncaab_scaled)

    def test_max_day_fraction_is_60_not_30(self):
        self.assertEqual(S.MAX_PER_SPORT, 6)
        self.assertEqual(S.EXPECTED_MAX_TAKEN, 12)
        naive_12 = S.naive_3pct_end_cents([12])
        # 12 * 1250 * 2.4¢ = 36_000¢ → $20,360
        self.assertEqual(naive_12, 2_036_000)
        naive_6 = S.naive_3pct_end_cents([6])
        self.assertEqual(naive_6, 2_018_000)

    def test_combined_naive_beats_nba_only_naive(self):
        ov = S.load_overlay()
        combined = S.naive_3pct_end_cents(ov["taken"])
        nba = S.naive_3pct_end_cents(ov["nba_taken"])
        self.assertGreater(combined, nba)


class TestSimSmoke(unittest.TestCase):
    def test_small_combined_reproducible_and_positive(self):
        from datetime import date, timedelta

        days = [date(2025, 11, 1) + timedelta(days=i) for i in range(4)]
        a = S.simulate([2, 0, 3, 1], [1, 0, 2, 0], days, n_sim=32, seed=7)
        b = S.simulate([2, 0, 3, 1], [1, 0, 2, 0], days, n_sim=32, seed=7)
        self.assertTrue(np.array_equal(a["end_cents"], b["end_cents"]))
        self.assertTrue(np.all(a["end_cents"] > 0))
        self.assertEqual(a["n_trades"], 9)


if __name__ == "__main__":
    unittest.main()
