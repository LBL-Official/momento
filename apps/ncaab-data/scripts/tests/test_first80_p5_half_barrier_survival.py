#!/usr/bin/env python3
"""Unit tests for NCAAB P5 FIRST80 half-bin barrier survival.

Synthetic PBP/candles plus the frozen P5 candidates identity gate.
Does not require a live Kalshi or ESPN session.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import first80_p5_half_barrier_survival as H  # noqa: E402
import ncaab_pbp_align as P  # noqa: E402


def _action(
    idx: int,
    period: int,
    remaining: float,
    wall: int,
    *,
    typ: str = "shot",
    sub: str = "",
) -> dict:
    return {
        "idx": idx,
        "actionType": typ,
        "subType": sub,
        "period": period,
        "clock": None,
        "remaining_s": remaining,
        "elapsed_s": P.game_seconds_elapsed(period, remaining),
        "score_home": 0,
        "score_away": 0,
        "description": "",
        "knot_wall_ts": wall,
        "modeled_wall_ts": wall,
        "wall_source": "OBSERVED",
    }


def half_actions() -> list[dict]:
    """H1 start 1000, H1 10:00 at 4000, H2 start 8000, H2 10:00 at 11000."""
    return [
        _action(0, 1, 1200, 1000, typ="period", sub="start"),
        _action(1, 1, 601, 3900),
        _action(2, 1, 600, 4000),
        _action(3, 1, 0, 7000, typ="period", sub="end"),
        _action(4, 2, 1200, 8000, typ="period", sub="start"),
        _action(5, 2, 601, 10900),
        _action(6, 2, 600, 11000),
        _action(7, 2, 0, 14000, typ="period", sub="end"),
        _action(8, 3, 300, 14500, typ="period", sub="start"),
        _action(9, 3, 0, 16000, typ="period", sub="end"),
    ]


def jump_quotes(t0: int) -> list[dict]:
    return [
        {"ts": t0 - 60, "bid_c": 7900, "ask_c": 8000, "vol": 100},
        {"ts": t0, "bid_c": 8100, "ask_c": 8200, "vol": 100},
        {"ts": t0 + 60, "bid_c": 3800, "ask_c": 4000, "vol": 100},
    ]


class TestFrozenIdentity(unittest.TestCase):
    def test_candidates_identity(self):
        trades = H.load_frozen_p5_first80()
        gate = H.halt_unless_identity(trades)
        self.assertTrue(gate["ok"])
        self.assertEqual(gate["observed"]["n"], 721)
        self.assertEqual(gate["observed"]["W"], 601)
        self.assertEqual(gate["observed"]["T40"], 188)
        self.assertEqual(gate["observed"]["W_and_not_T40"], 533)
        self.assertEqual(gate["observed"]["L_and_not_T40"], 0)

    def test_identity_halt(self):
        with self.assertRaises(H.IdentityHalt):
            H.halt_unless_identity([{"expiration_result_yes": True, "stop_close_triggered": False}])


class TestEntryBucket(unittest.TestCase):
    def test_halves(self):
        self.assertEqual(P.entry_bucket("HIGH", "IN_PERIOD", 1, 1199), "H1_1")
        self.assertEqual(P.entry_bucket("HIGH", "IN_PERIOD", 1, 601), "H1_1")
        self.assertEqual(P.entry_bucket("HIGH", "IN_PERIOD", 1, 600), "H1_2")
        self.assertEqual(P.entry_bucket("MEDIUM", "INTERMISSION", 1, 0), "H1_2")
        self.assertEqual(P.entry_bucket("HIGH", "IN_PERIOD", 2, 601), "H2_1")
        self.assertEqual(P.entry_bucket("HIGH", "IN_PERIOD", 2, 600), "H2_2")
        self.assertEqual(P.entry_bucket("HIGH", "IN_PERIOD", 3, 200), "OT")

    def test_unaligned(self):
        self.assertEqual(P.entry_bucket("UNUSABLE", "IN_PERIOD", 1, 900), "UNALIGNED")
        self.assertEqual(P.entry_bucket("LOW", "IN_PERIOD", 1, 900), "UNALIGNED")
        self.assertEqual(P.entry_bucket("MEDIUM", "GAME_NOT_STARTED", 1, 1200), "UNALIGNED")
        self.assertEqual(P.entry_bucket("HIGH", "IN_PERIOD", None, 900), "UNALIGNED")
        self.assertEqual(P.entry_bucket("HIGH", "IN_PERIOD", 1, None), "UNALIGNED")


class TestClock(unittest.TestCase):
    def test_regulation_remaining_no_future_ot(self):
        self.assertEqual(P.game_seconds_remaining(1, 600), 1800)
        self.assertEqual(P.game_seconds_remaining(2, 600), 600)
        self.assertEqual(P.game_seconds_remaining(3, 200), 200)
        self.assertTrue(H.regulation_remaining_formula_ok(1, 600, 1800))
        self.assertTrue(H.regulation_remaining_formula_ok(2, 100, 100))

    def test_snap_half_split(self):
        rows = half_actions()
        early = P.snap_clock(rows, 3900)
        self.assertEqual(early["period"], 1)
        self.assertEqual(early["period_remaining_s"], 601)
        self.assertEqual(P.entry_bucket("HIGH", early["phase"], early["period"], early["period_remaining_s"]), "H1_1")
        late = P.snap_clock(rows, 4000)
        self.assertEqual(late["period_remaining_s"], 600)
        self.assertEqual(P.entry_bucket("HIGH", late["phase"], late["period"], late["period_remaining_s"]), "H1_2")
        h2 = P.snap_clock(rows, 11000)
        self.assertEqual(h2["period"], 2)
        self.assertEqual(P.entry_bucket("HIGH", h2["phase"], h2["period"], h2["period_remaining_s"]), "H2_2")

    def test_halftime_stays_h1_2(self):
        rows = half_actions()
        snap = P.snap_to_entry(rows, 7500)
        self.assertEqual(snap["game_phase"], "INTERMISSION")
        clock = P.snap_clock(rows, 7500)
        self.assertEqual(clock["period"], 1)
        self.assertEqual(P.entry_bucket("MEDIUM", clock["phase"], clock["period"], clock["period_remaining_s"]), "H1_2")

    def test_pre_tip_unaligned(self):
        rows = half_actions()
        snap = P.snap_to_entry(rows, 500)
        self.assertEqual(snap["game_phase"], "GAME_NOT_STARTED")
        self.assertEqual(P.entry_bucket("MEDIUM", "GAME_NOT_STARTED", 1, 1200), "UNALIGNED")

    def test_clock_order(self):
        rows = half_actions()
        early = P.snap_clock(rows, 3900)
        late = P.snap_clock(rows, 11000)
        self.assertGreater(early["game_seconds_remaining"], late["game_seconds_remaining"])


class TestCloseTouches(unittest.TestCase):
    def test_jump_through_40_nests(self):
        t0 = 10_000
        found = H.first_close_touches(jump_quotes(t0), t0)
        self.assertEqual(found[60], t0 + 60)
        self.assertEqual(found[50], t0 + 60)
        self.assertEqual(found[40], t0 + 60)
        self.assertTrue(H.nested_ok(found))

    def test_staggered_then_nested(self):
        t0 = 100
        quotes = [
            {"ts": t0 + 60, "bid_c": 5900, "ask_c": 6000, "vol": 10},
            {"ts": t0 + 120, "bid_c": 4900, "ask_c": 5000, "vol": 10},
            {"ts": t0 + 180, "bid_c": 3900, "ask_c": 4000, "vol": 10},
        ]
        found = H.first_close_touches(quotes, t0)
        self.assertEqual(found[60], t0 + 60)
        self.assertEqual(found[50], t0 + 120)
        self.assertEqual(found[40], t0 + 180)
        self.assertTrue(H.nested_ok(found))

    def test_nested_rejects_40_without_60(self):
        self.assertFalse(H.nested_ok({60: None, 50: None, 40: 1}))
        self.assertFalse(H.nested_ok({60: 10, 50: 5, 40: 20}))


class TestEv(unittest.TestCase):
    def test_stop_ev_and_vs_hold(self):
        ev = H.ev_stop_gross(100, 70, 30, 40)
        self.assertEqual(ev["stop_pnl_cents"], -40)
        self.assertEqual(ev["sum_pnl_cents"], 70 * 20 + 30 * (-40))
        hold = H.ev_hold_gross(100, 80)
        self.assertEqual(hold["ev_cents_per_contract"], (80 * 20 + 20 * (-80)) / 100)


class TestEspnClockParse(unittest.TestCase):
    def test_mmss(self):
        self.assertEqual(P.parse_clock_seconds("20:00"), 1200)
        self.assertEqual(P.parse_clock_seconds("10:00"), 600)
        self.assertEqual(P.parse_clock_seconds("1:48"), 108)
        self.assertEqual(P.parse_clock_seconds("0:01"), 1)
        self.assertIsNone(P.parse_clock_seconds(None))

    def test_enrich_observed_wall(self):
        plays = [
            {
                "text": "Start game",
                "type_text": "Jumpball",
                "period": 1,
                "clock": "20:00",
                "wallclock": "2025-12-03T00:31:32Z",
                "homeScore": 0,
                "awayScore": 0,
            },
            {
                "text": "End of 1st half",
                "type_text": "End Period",
                "period": 1,
                "clock": "0:00",
                "wallclock": "2025-12-03T01:20:00Z",
                "homeScore": 30,
                "awayScore": 28,
            },
        ]
        rows = P.enrich_actions(plays)
        self.assertEqual(rows[0]["subType"], "start")
        self.assertEqual(rows[1]["subType"], "end")
        self.assertEqual(rows[0]["wall_source"], "OBSERVED")
        self.assertEqual(rows[0]["remaining_s"], 1200)


if __name__ == "__main__":
    unittest.main()
