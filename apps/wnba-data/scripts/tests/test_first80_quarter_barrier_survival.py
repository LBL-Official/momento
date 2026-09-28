#!/usr/bin/env python3
"""Unit tests for WNBA FIRST80 quarter barrier survival.

Synthetic PBP/candles plus the frozen candidates identity gate.
Does not require a live Kalshi or ESPN session.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import first80_quarter_barrier_survival as Q  # noqa: E402
import wnba_pbp_align as P  # noqa: E402
import wnba_pbp_espn_ingest as I  # noqa: E402


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


def quarter_actions() -> list[dict]:
    return [
        _action(0, 1, 600, 1000, typ="period", sub="start"),
        _action(1, 1, 0, 4000, typ="period", sub="end"),
        _action(2, 2, 600, 4500, typ="period", sub="start"),
        _action(3, 2, 0, 7500, typ="period", sub="end"),
        _action(4, 3, 600, 8000, typ="period", sub="start"),
        _action(5, 3, 300, 10000),
        _action(6, 3, 0, 12000, typ="period", sub="end"),
        _action(7, 4, 600, 12500, typ="period", sub="start"),
        _action(8, 4, 200, 15000),
        _action(9, 4, 0, 17000, typ="period", sub="end"),
    ]


def jump_quotes(t0: int) -> list[dict]:
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
        self.assertEqual(gate["observed"]["n"], 589)
        self.assertEqual(gate["observed"]["W"], 492)
        self.assertEqual(gate["observed"]["T40"], 153)
        self.assertEqual(gate["observed"]["W_and_not_T40"], 436)
        self.assertEqual(gate["observed"]["L_and_not_T40"], 0)

    def test_identity_halt(self):
        with self.assertRaises(Q.IdentityHalt):
            Q.halt_unless_identity([{"expiration_result_yes": True, "stop_close_triggered": False}])


class TestEntryBucket(unittest.TestCase):
    def test_quarters(self):
        self.assertEqual(P.entry_bucket("HIGH", "IN_PERIOD", 1, 500), "Q1")
        self.assertEqual(P.entry_bucket("MEDIUM", "INTERMISSION", 2, 0), "Q2")
        self.assertEqual(P.entry_bucket("HIGH", "IN_PERIOD", 3, 300), "Q3")
        self.assertEqual(P.entry_bucket("HIGH", "IN_PERIOD", 4, 100), "Q4")
        self.assertEqual(P.entry_bucket("HIGH", "IN_PERIOD", 5, 200), "OT")

    def test_unaligned(self):
        self.assertEqual(P.entry_bucket("UNUSABLE", "IN_PERIOD", 3, 300), "UNALIGNED")
        self.assertEqual(P.entry_bucket("LOW", "IN_PERIOD", 1, 500), "UNALIGNED")
        self.assertEqual(P.entry_bucket("MEDIUM", "GAME_NOT_STARTED", 1, 600), "UNALIGNED")
        self.assertEqual(P.entry_bucket("HIGH", "IN_PERIOD", None, 300), "UNALIGNED")


class TestClock(unittest.TestCase):
    def test_regulation_remaining_no_future_ot(self):
        self.assertEqual(P.game_seconds_remaining(1, 300), 2100)
        self.assertEqual(P.game_seconds_remaining(2, 300), 1500)
        self.assertEqual(P.game_seconds_remaining(3, 300), 900)
        self.assertEqual(P.game_seconds_remaining(4, 300), 300)
        self.assertEqual(P.game_seconds_remaining(5, 200), 200)
        self.assertTrue(Q.regulation_remaining_formula_ok(1, 300, 2100))
        self.assertTrue(Q.regulation_remaining_formula_ok(4, 100, 100))

    def test_snap_q3(self):
        rows = quarter_actions()
        ck = P.snap_clock(rows, 10000)
        self.assertEqual(ck["period"], 3)
        self.assertEqual(ck["period_remaining_s"], 300)
        self.assertEqual(ck["game_seconds_remaining"], 900)
        self.assertEqual(P.entry_bucket("HIGH", ck["phase"], ck["period"], ck["period_remaining_s"]), "Q3")

    def test_intermission_stays_prior_quarter(self):
        rows = quarter_actions()
        snap = P.snap_to_entry(rows, 7700)
        self.assertEqual(snap["game_phase"], "INTERMISSION")
        clock = P.snap_clock(rows, 7700)
        self.assertEqual(clock["period"], 2)
        self.assertEqual(P.entry_bucket("MEDIUM", clock["phase"], clock["period"], clock["period_remaining_s"]), "Q2")

    def test_pre_tip_unaligned(self):
        rows = quarter_actions()
        snap = P.snap_to_entry(rows, 500)
        self.assertEqual(snap["game_phase"], "GAME_NOT_STARTED")

    def test_clock_order(self):
        rows = quarter_actions()
        early = P.snap_clock(rows, 4000)
        late = P.snap_clock(rows, 15000)
        self.assertGreater(early["game_seconds_remaining"], late["game_seconds_remaining"])


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
        self.assertEqual(found[60], t0 + 60)
        self.assertEqual(found[50], t0 + 120)
        self.assertEqual(found[40], t0 + 180)
        self.assertTrue(Q.nested_ok(found))

    def test_nested_rejects_40_without_60(self):
        self.assertFalse(Q.nested_ok({60: None, 50: None, 40: 1}))


class TestClockParse(unittest.TestCase):
    def test_mmss_and_tenths(self):
        self.assertEqual(P.parse_clock_seconds("10:00"), 600)
        self.assertEqual(P.parse_clock_seconds("1:48"), 108)
        self.assertEqual(P.parse_clock_seconds("0.0"), 0.0)
        self.assertEqual(P.parse_clock_seconds("56.1"), 56.1)
        self.assertIsNone(P.parse_clock_seconds(None))


class TestTeamCanon(unittest.TestCase):
    def test_event_id(self):
        self.assertEqual(I.parse_event_codes("KXWNBAGAME-26AUG30CONNDAL"), ("CONN", "DAL"))
        self.assertEqual(I.parse_event_codes("KXWNBAGAME-26AUG30GSPDX"), ("GS", "PDX"))
        self.assertEqual(I.parse_event_codes("KXWNBAGAME-25AUG01GSCHI"), ("GS", "CHI"))
        self.assertEqual(I.parse_event_codes("KXWNBAGAME-26JUL01INDLVA"), ("IND", "LV"))
        self.assertEqual(I.parse_event_codes("KXWNBAGAME-26JUL01NYLPHX"), ("NY", "PHX"))

    def test_espn_aliases(self):
        self.assertEqual(I.canon_code("CON"), "CONN")
        self.assertEqual(I.canon_code("POR"), "PDX")
        self.assertEqual(I.canon_code("Connecticut"), "CONN")
        self.assertEqual(I.canon_code("Portland Fire"), "PDX")


class TestScanWindow(unittest.TestCase):
    def test_postponed_uses_close_not_stale_52h(self):
        rec = {
            "game_date": "2026-07-16",
            "first_80_timestamp": 1784420940,
            "close_ts": 1784601270,
        }
        end = Q.scan_window_end(rec)
        self.assertEqual(end, 1784601270)
        self.assertGreater(end, rec["first_80_timestamp"])


class TestEv(unittest.TestCase):
    def test_stop_ev(self):
        ev = Q.ev_stop_gross(100, 70, 30, 40)
        self.assertEqual(ev["stop_pnl_cents"], -40)
        self.assertEqual(ev["sum_pnl_cents"], 70 * 20 + 30 * (-40))


if __name__ == "__main__":
    unittest.main()
