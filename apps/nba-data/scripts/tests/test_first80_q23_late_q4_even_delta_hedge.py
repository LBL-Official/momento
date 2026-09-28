#!/usr/bin/env python3
"""Unit tests for NBA 2Q/3Q late-4Q even-delta hedge.

Synthetic clocks and quotes. Frozen Q2=314 / Q3=290 identity uses the
warehouse ledger. Does not require a live Kalshi session.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
GPE = SCRIPTS / "game_path_engine_v2"
if str(GPE) not in sys.path:
    sys.path.insert(0, str(GPE))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import first80_q23_late_q4_even_delta_hedge as H  # noqa: E402
import first80_quarter_barrier_survival as Q  # noqa: E402


def q4_actions() -> list[dict]:
    """Q4 remaining 720 → 0 with linear modeled walls 10_000 → 17_200."""
    rows = []
    for i, rem in enumerate((720, 480, 360, 300, 180, 60, 0)):
        rows.append(
            {
                "idx": i,
                "period": 4,
                "remaining_s": float(rem),
                "modeled_wall_ts": 10_000 + (720 - rem) * 10,
                "actionType": "period" if rem in (720, 0) else "shot",
                "subType": "start" if rem == 720 else ("end" if rem == 0 else ""),
            }
        )
    return rows


def q(ts: int, bid: int, ask: int, vol: int = 100) -> dict:
    return {"ts": ts, "bid_c": bid, "ask_c": ask, "vol": vol}


class TestClock(unittest.TestCase):
    def test_marks_interpolate(self):
        acts = q4_actions()
        m6 = H.wall_at_remaining(acts, 4, 360)
        m3 = H.wall_at_remaining(acts, 4, 180)
        self.assertEqual(m6, 13_600)
        self.assertEqual(m3, 15_400)

    def test_never_reached_mark_is_none(self):
        acts = [
            {"period": 4, "remaining_s": 720.0, "modeled_wall_ts": 1000},
            {"period": 4, "remaining_s": 500.0, "modeled_wall_ts": 2000},
        ]
        self.assertIsNone(H.wall_at_remaining(acts, 4, 360))

    def test_already_past_uses_first_observed(self):
        acts = [
            {"period": 4, "remaining_s": 300.0, "modeled_wall_ts": 5000},
            {"period": 4, "remaining_s": 100.0, "modeled_wall_ts": 6000},
        ]
        self.assertEqual(H.wall_at_remaining(acts, 4, 360), 5000)


class TestEarlyTouch(unittest.TestCase):
    def test_q3_is_early(self):
        self.assertTrue(H.touched_by_q4_6(True, 3, 100.0))

    def test_q4_at_6_is_early(self):
        self.assertTrue(H.touched_by_q4_6(True, 4, 360.0))

    def test_q4_after_6_is_not_early(self):
        self.assertFalse(H.touched_by_q4_6(True, 4, 359.0))
        self.assertFalse(H.touched_by_q4_6(True, 4, 180.0))

    def test_ot_is_not_early(self):
        self.assertFalse(H.touched_by_q4_6(True, 5, 120.0))

    def test_no_touch(self):
        self.assertFalse(H.touched_by_q4_6(False, 2, 400.0))

    def test_missing_clock(self):
        self.assertIsNone(H.touched_by_q4_6(True, None, 360.0))


class TestLockPnl(unittest.TestCase):
    def test_even_delta(self):
        self.assertEqual(H.lock_pnl_cents(30), -10)
        self.assertEqual(H.lock_pnl_cents(20), 0)
        self.assertEqual(H.lock_pnl_cents(40), -20)
        self.assertEqual(H.stop_pnl_cents(40), -40)
        self.assertEqual(H.stop_pnl_cents(50), -30)
        self.assertEqual(H.stop_pnl_cents(60), -20)


class TestClassify(unittest.TestCase):
    def setUp(self):
        self.t0 = 1_000
        self.mark6 = 13_600
        self.mark3 = 15_400
        self.held = [
            q(1_060, 8200, 8300),
            q(13_600, 8000, 8100),
            q(14_200, 7400, 7600),
            q(15_000, 7000, 7200),
            q(16_000, 6800, 7000),
        ]
        self.opp = [
            q(1_060, 1800, 2000),
            q(13_600, 1900, 2100),
            q(14_200, 2500, 2700),
            q(15_000, 2900, 3100),
            q(16_000, 3100, 3300),
        ]

    def _cls(self, **kw):
        args = dict(
            won=True,
            level=40,
            touched=False,
            touch_period=None,
            touch_remaining_s=None,
            mark6=self.mark6,
            mark3=self.mark3,
            held_quotes=self.held,
            opp_quotes=self.opp,
            t0=self.t0,
            scan_end=None,
        )
        args.update(kw)
        return H.classify_trade(**args)

    def test_early_stop(self):
        rec = self._cls(touched=True, touch_period=3, touch_remaining_s=200.0, won=False)
        self.assertEqual(rec["path"], H.PATH_EARLY)
        self.assertEqual(rec["pnl_cents"], -40)

    def test_hedge_at_6_when_below_75(self):
        held = [q(1_060, 8200, 8300), q(13_600, 7400, 7600)]
        rec = self._cls(held_quotes=held)
        self.assertEqual(rec["path"], H.PATH_HEDGE_A)
        self.assertEqual(rec["hedge_H_cents"], 21)
        self.assertEqual(rec["pnl_cents"], -1)

    def test_75_does_not_hedge_at_6(self):
        held = [
            q(1_060, 8200, 8300),
            q(13_600, 7500, 7600),
            q(14_200, 7500, 7600),
        ]
        rec = self._cls(held_quotes=held)
        self.assertEqual(rec["path"], H.PATH_UNHEDGED)

    def test_hedge_b_after_6_before_3(self):
        rec = self._cls()
        self.assertEqual(rec["path"], H.PATH_HEDGE_B)
        self.assertEqual(rec["held_bid_e4"], 7400)
        self.assertEqual(rec["hedge_H_cents"], 27)
        self.assertEqual(rec["pnl_cents"], -7)

    def test_drop_after_3_is_unhedged(self):
        held = [
            q(1_060, 8200, 8300),
            q(13_600, 8000, 8100),
            q(15_400, 8000, 8100),
            q(16_000, 6000, 6200),
        ]
        rec = self._cls(held_quotes=held, won=False)
        self.assertEqual(rec["path"], H.PATH_UNHEDGED)
        self.assertEqual(rec["pnl_cents"], -80)

    def test_unhedged_winner(self):
        held = [
            q(1_060, 8200, 8300),
            q(13_600, 8000, 8100),
            q(14_200, 7800, 7900),
        ]
        rec = self._cls(held_quotes=held, won=True)
        self.assertEqual(rec["path"], H.PATH_UNHEDGED)
        self.assertEqual(rec["pnl_cents"], 20)

    def test_unpriced_without_opponent(self):
        held = [q(1_060, 8200, 8300), q(13_600, 7000, 7200)]
        rec = self._cls(held_quotes=held, opp_quotes=None)
        self.assertEqual(rec["path"], H.PATH_UNPRICED)
        self.assertFalse(rec["priced"])

    def test_no_clock(self):
        rec = self._cls(mark6=None, mark3=None)
        self.assertEqual(rec["path"], H.PATH_NO_CLOCK)

    def test_touch_ts_fallback_early(self):
        rec = self._cls(
            touched=True,
            touch_period=None,
            touch_remaining_s=None,
            touch_ts=13_000,
        )
        self.assertEqual(rec["path"], H.PATH_EARLY)


class TestIdentity(unittest.TestCase):
    def test_q2_q3_counts(self):
        frozen = Q.load_frozen_first80()
        gate = Q.halt_unless_identity(frozen)
        self.assertTrue(gate["ok"])
        ledger = H.load_quarter_trades()
        q2 = sum(1 for r in ledger if r["entry_quarter_bucket"] == "Q2")
        q3 = sum(1 for r in ledger if r["entry_quarter_bucket"] == "Q3")
        self.assertEqual(q2, 314)
        self.assertEqual(q3, 290)


if __name__ == "__main__":
    unittest.main()
