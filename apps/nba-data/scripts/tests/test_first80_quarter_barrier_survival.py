#!/usr/bin/env python3
"""Unit tests for NBA FIRST80 quarter barrier survival.

Synthetic PBP/candles plus the frozen candidates identity gate.
Does not require a live Kalshi session.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import first80_quarter_barrier_survival as Q  # noqa: E402
from pbp import game_seconds_remaining, snap_to_entry  # noqa: E402


def _action(
    idx: int,
    period: int,
    remaining: float,
    wall: int,
    *,
    typ: str = "shot",
    sub: str = "",
    knot: int | None = None,
) -> dict:
    return {
        "idx": idx,
        "actionNumber": idx,
        "actionType": typ,
        "subType": sub,
        "period": period,
        "clock": None,
        "remaining_s": remaining,
        "elapsed_s": None,
        "score_home": 0,
        "score_away": 0,
        "team_tricode": None,
        "description": "",
        "knot_wall_ts": knot,
        "modeled_wall_ts": wall,
    }


def q3_actions() -> list[dict]:
    """Linear modeled walls: Q1 start 1000, Q3 mid remaining 500s at wall 10000."""
    return [
        _action(0, 1, 720, 1000, typ="period", sub="start", knot=1000),
        _action(1, 1, 0, 4000, typ="period", sub="end", knot=4000),
        _action(2, 2, 720, 4500, typ="period", sub="start", knot=4500),
        _action(3, 2, 0, 7500, typ="period", sub="end", knot=7500),
        _action(4, 3, 720, 8000, typ="period", sub="start", knot=8000),
        _action(5, 3, 500, 10000),
        _action(6, 3, 400, 11000),
        _action(7, 3, 0, 14000, typ="period", sub="end", knot=14000),
        _action(8, 4, 720, 14500, typ="period", sub="start", knot=14500),
        _action(9, 4, 200, 18000),
        _action(10, 4, 0, 20000, typ="period", sub="end", knot=20000),
    ]


def jump_quotes(t0: int) -> list[dict]:
    """Post-entry jump 81 → 38 on one tradable bar. Nested same timestamp."""
    return [
        {"ts": t0 - 60, "bid_c": 7900, "ask_c": 8000, "vol": 100},
        {"ts": t0, "bid_c": 8100, "ask_c": 8200, "vol": 100},
        {"ts": t0 + 60, "bid_c": 3800, "ask_c": 4000, "vol": 100},
    ]


class TestFrozenIdentity(unittest.TestCase):
    def test_candidates_identity(self):
        trades = Q.load_frozen_first80()
        gate = Q.halt_unless_identity(trades)
        self.assertTrue(gate["ok"])
        self.assertEqual(gate["observed"]["n"], 1230)
        self.assertEqual(gate["observed"]["W"], 1019)
        self.assertEqual(gate["observed"]["T40"], 320)
        self.assertEqual(gate["observed"]["W_and_not_T40"], 910)
        self.assertEqual(gate["observed"]["L_and_not_T40"], 0)

    def test_identity_halt(self):
        with self.assertRaises(Q.IdentityHalt):
            Q.halt_unless_identity([{"expiration_result_yes": True, "stop_close_triggered": False}])


class TestEntryBucket(unittest.TestCase):
    def test_quarters(self):
        self.assertEqual(Q.entry_bucket("HIGH", "IN_PERIOD", 1), "Q1")
        self.assertEqual(Q.entry_bucket("MEDIUM", "INTERMISSION", 2), "Q2")
        self.assertEqual(Q.entry_bucket("HIGH", "IN_PERIOD", 3), "Q3")
        self.assertEqual(Q.entry_bucket("HIGH", "IN_PERIOD", 4), "Q4")
        self.assertEqual(Q.entry_bucket("HIGH", "IN_PERIOD", 5), "OT")

    def test_unaligned(self):
        self.assertEqual(Q.entry_bucket("UNUSABLE", "IN_PERIOD", 3), "UNALIGNED")
        self.assertEqual(Q.entry_bucket("LOW", "IN_PERIOD", 1), "UNALIGNED")
        self.assertEqual(Q.entry_bucket("MEDIUM", "GAME_NOT_STARTED", 1), "UNALIGNED")
        self.assertEqual(Q.entry_bucket("HIGH", "UNALIGNED", 3), "UNALIGNED")
        self.assertEqual(Q.entry_bucket("HIGH", "IN_PERIOD", None), "UNALIGNED")


class TestCloseTouches(unittest.TestCase):
    def test_jump_through_40_nests(self):
        t0 = 10_000
        found = Q.first_close_touches(jump_quotes(t0), t0)
        self.assertEqual(found[60], t0 + 60)
        self.assertEqual(found[50], t0 + 60)
        self.assertEqual(found[40], t0 + 60)
        self.assertTrue(Q.nested_ok(found))

    def test_staggered_then_nested(self):
        t0 = 100
        quotes = [
            {"ts": t0 + 60, "bid_c": 5900, "ask_c": 6000, "vol": 10},
            {"ts": t0 + 120, "bid_c": 4900, "ask_c": 5000, "vol": 10},
            {"ts": t0 + 180, "bid_c": 3900, "ask_c": 4000, "vol": 10},
        ]
        found = Q.first_close_touches(quotes, t0)
        self.assertEqual(found, {60: t0 + 60, 50: t0 + 120, 40: t0 + 180})
        self.assertTrue(Q.nested_ok(found))

    def test_entry_bar_excluded(self):
        t0 = 50
        quotes = [{"ts": t0, "bid_c": 3000, "ask_c": 3100, "vol": 10}]
        found = Q.first_close_touches(quotes, t0)
        self.assertEqual(found, {60: None, 50: None, 40: None})

    def test_non_tradable_ignored(self):
        t0 = 50
        quotes = [
            {"ts": t0 + 60, "bid_c": 3000, "ask_c": 2000, "vol": 10},  # crossed
            {"ts": t0 + 120, "bid_c": 3900, "ask_c": 4000, "vol": 10},
        ]
        found = Q.first_close_touches(quotes, t0)
        self.assertEqual(found[40], t0 + 120)

    def test_nested_violation(self):
        self.assertFalse(Q.nested_ok({60: None, 50: None, 40: 1}))
        self.assertFalse(Q.nested_ok({60: 10, 50: 5, 40: 20}))


class TestQ3AndUnalignedSnaps(unittest.TestCase):
    def test_q3_entry_clock(self):
        actions = q3_actions()
        ck = Q.snap_clock(actions, 10000)
        self.assertEqual(ck["period"], 3)
        self.assertEqual(ck["period_remaining_s"], 500)
        self.assertEqual(ck["game_seconds_remaining"], 500 + 720)
        self.assertEqual(Q.format_clock(ck["game_seconds_remaining"]), "20:20")
        self.assertEqual(Q.entry_bucket("HIGH", ck["phase"], ck["period"]), "Q3")

    def test_jump_touch_later_in_q3(self):
        actions = q3_actions()
        t0 = 10000
        found = Q.first_close_touches(jump_quotes(t0), t0)
        ck = Q.snap_clock(actions, found[40])
        self.assertEqual(found[60], found[50])
        self.assertEqual(found[50], found[40])
        self.assertEqual(ck["period"], 3)
        self.assertLessEqual(ck["game_seconds_remaining"], 500 + 720)

    def test_unaligned_no_actions(self):
        bucket = Q.entry_bucket("UNUSABLE", "UNALIGNED", None)
        self.assertEqual(bucket, "UNALIGNED")
        snap = snap_to_entry([], 1000)
        self.assertIn(snap.get("game_phase"), ("UNALIGNED", "GAME_NOT_STARTED"))


class TestClockOrderAndOt(unittest.TestCase):
    def test_regulation_remaining_not_increase(self):
        actions = q3_actions()
        early = Q.snap_clock(actions, 10000)
        late = Q.snap_clock(actions, 18000)
        self.assertGreaterEqual(early["game_seconds_remaining"], late["game_seconds_remaining"])
        self.assertTrue(
            Q.regulation_remaining_formula_ok(
                early["period"],
                early["period_remaining_s"],
                early["game_seconds_remaining"],
            )
        )

    def test_no_invented_future_ot(self):
        # Q4 with 100s left must be 100, not 100+300.
        rem = game_seconds_remaining(4, 100)
        self.assertEqual(rem, 100.0)
        self.assertTrue(Q.regulation_remaining_formula_ok(4, 100, rem))
        # OT remaining is the OT clock only.
        ot = game_seconds_remaining(5, 200)
        self.assertEqual(ot, 200.0)
        self.assertTrue(Q.regulation_remaining_formula_ok(5, 200, ot))

    def test_timestamp_order(self):
        found = {60: 10, 50: 20, 40: 30}
        self.assertTrue(Q.nested_ok(found))
        self.assertLessEqual(found[60], found[50])
        self.assertLessEqual(found[50], found[40])


class TestPartitionAndStats(unittest.TestCase):
    def test_partition_sums(self):
        rows = (
            [{"entry_quarter_bucket": "Q1"}] * 324
            + [{"entry_quarter_bucket": "Q2"}] * 314
            + [{"entry_quarter_bucket": "Q3"}] * 290
            + [{"entry_quarter_bucket": "Q4"}] * 227
            + [{"entry_quarter_bucket": "OT"}] * 3
            + [{"entry_quarter_bucket": "UNALIGNED"}] * 72
        )
        counts = {b: sum(1 for r in rows if r["entry_quarter_bucket"] == b) for b in Q.PARTITION_BUCKETS}
        self.assertEqual(sum(counts.values()), 1230)
        self.assertEqual(set(counts), set(Q.PARTITION_BUCKETS))

    def test_clock_stats_mmss(self):
        # 22:00, 26:00, 31:00 remaining
        xs = [22 * 60, 26 * 60, 31 * 60]
        st = Q.clock_stats(xs)
        self.assertEqual(st["n"], 3)
        self.assertEqual(st["min_clock"], "22:00")
        self.assertEqual(st["median_clock"], "26:00")
        self.assertEqual(st["max_clock"], "31:00")
        self.assertEqual(st["p25_clock"], "24:00")
        self.assertEqual(st["p75_clock"], "28:30")
        self.assertIsNotNone(st["sd_clock"])
        self.assertIsNotNone(st["iqr_clock"])

    def test_bucket_summary_nested_winner_before(self):
        rows = [
            {
                "entry_quarter_bucket": "Q3",
                "W": True,
                "T60": False,
                "T50": False,
                "T40": False,
                "t60_remaining_s": None,
                "t50_remaining_s": None,
                "t40_remaining_s": None,
                "t60_period": None,
                "t50_period": None,
                "t40_period": None,
            },
            {
                "entry_quarter_bucket": "Q3",
                "W": True,
                "T60": True,
                "T50": True,
                "T40": True,
                "t60_remaining_s": 31 * 60,
                "t50_remaining_s": 26 * 60,
                "t40_remaining_s": 22 * 60,
                "t60_period": 3,
                "t50_period": 3,
                "t40_period": 3,
            },
            {
                "entry_quarter_bucket": "Q3",
                "W": False,
                "T60": True,
                "T50": True,
                "T40": True,
                "t60_remaining_s": 20 * 60,
                "t50_remaining_s": 18 * 60,
                "t40_remaining_s": 15 * 60,
                "t60_period": 3,
                "t50_period": 3,
                "t40_period": 3,
            },
        ]
        s = Q.bucket_summary(rows, "Q3")
        self.assertEqual(s["n"], 3)
        self.assertTrue(s["nested_touch_ok"])
        self.assertEqual(s["levels"]["40"]["n_touch"], 2)
        self.assertEqual(s["levels"]["50"]["n_touch"], 2)
        self.assertEqual(s["levels"]["60"]["n_touch"], 2)
        # 1 of 3 expired winner without touching 40/50/60
        self.assertEqual(s["levels"]["40"]["n_winner_before_touch"], 1)
        self.assertEqual(s["levels"]["40"]["pct_winner_before_touch"], 33.33)
        # 1 survive-win @ +20, 2 stop-40 @ −40 → EV = (20-80)/3 = −20¢
        self.assertEqual(s["levels"]["40"]["ev_stop"]["ev_cents_per_contract"], -20.0)
        self.assertEqual(s["ev_hold"]["ev_cents_per_contract"], -13.3333)


class TestGrossEV(unittest.TestCase):
    def test_40_stop_matches_locked_1_minus_3q(self):
        n, t = 314, 75
        q = t / n
        ev = Q.ev_stop_gross(n, n - t, t, 40)
        self.assertAlmostEqual(ev["ev_R"], 1.0 - 3.0 * q, places=4)
        self.assertEqual(ev["sum_pnl_cents"], 239 * 20 + 75 * (-40))
        self.assertAlmostEqual(ev["ev_cents_per_contract"], 1780 / 314, places=4)

    def test_2q_60_50_40_exact(self):
        e60 = Q.ev_stop_gross(314, 188, 126, 60)
        e50 = Q.ev_stop_gross(314, 221, 93, 50)
        e40 = Q.ev_stop_gross(314, 239, 75, 40)
        self.assertEqual(e60["sum_pnl_cents"], 1240)
        self.assertEqual(e50["sum_pnl_cents"], 1630)
        self.assertEqual(e40["sum_pnl_cents"], 1780)
        self.assertAlmostEqual(e60["ev_pct_of_1_dollar"], 1240 / 314, places=4)
        self.assertAlmostEqual(e50["ev_pct_of_1_dollar"], 1630 / 314, places=4)
        self.assertAlmostEqual(e40["ev_pct_of_1_dollar"], 1780 / 314, places=4)

    def test_3q_60_exact(self):
        e = Q.ev_stop_gross(290, 186, 104, 60)
        self.assertEqual(e["sum_pnl_cents"], 1640)
        self.assertAlmostEqual(e["ev_pct_of_1_dollar"], 1640 / 290, places=4)

    def test_no_fees_invented(self):
        e = Q.ev_stop_gross(10, 6, 4, 50)
        self.assertIn("ZERO FEE", e["label"])
        self.assertEqual(e["stop_pnl_cents"], -30)
        self.assertEqual(e["win_pnl_cents"], 20)


if __name__ == "__main__":
    unittest.main()
