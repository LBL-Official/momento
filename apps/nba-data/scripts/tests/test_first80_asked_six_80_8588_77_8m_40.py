#!/usr/bin/env python3
"""Unit tests for 80→[85,88]→77/8m path scanner."""

from __future__ import annotations

import unittest

import first80_asked_six_80_8588_77_8m_40 as M


def q(ts: int, bid: int, ask: int | None = None, vol: int = 100):
    # bid/ask in whole cents; 1¢ spread keeps quality() happy (MAX_SPREAD=10¢).
    ask = bid + 1 if ask is None else ask
    return {"ts": ts, "bid_c": bid * 100, "ask_c": ask * 100, "vol": vol}


class PathScanTests(unittest.TestCase):
    def test_qualify_happy_path(self):
        f80 = 1_000_000
        quotes = [
            q(f80 - 60, 79),
            q(f80, 80),
            q(f80 + 60, 86),
            q(f80 + 120, 87),
            q(f80 + 180, 77),
            q(f80 + 300, 40),
        ]
        got = M.scan_entry_path(quotes, f80)
        self.assertTrue(got["qualified"])
        self.assertEqual(got["entry_ts"], f80 + 180)
        self.assertEqual(got["peak_px_e4"], 8700)

    def test_reject_above_88(self):
        f80 = 1_000_000
        quotes = [q(f80 + 60, 89), q(f80 + 120, 77)]
        got = M.scan_entry_path(quotes, f80)
        self.assertFalse(got["qualified"])
        self.assertEqual(got["reject"], "PEAK_ABOVE_88")

    def test_reject_no_peak(self):
        f80 = 1_000_000
        quotes = [q(f80 + 60, 84), q(f80 + 120, 77)]
        got = M.scan_entry_path(quotes, f80)
        self.assertFalse(got["qualified"])
        self.assertEqual(got["reject"], "NO_PEAK_85_88")

    def test_reject_77_after_8m(self):
        f80 = 1_000_000
        quotes = [
            q(f80 + 60, 86),
            q(f80 + 8 * 60 + 60, 77),  # minute 9
        ]
        got = M.scan_entry_path(quotes, f80)
        self.assertFalse(got["qualified"])
        self.assertEqual(got["reject"], "NO_REVERT_77")

    def test_77_before_peak_does_not_enter(self):
        f80 = 1_000_000
        quotes = [
            q(f80 + 60, 77),  # before peak
            q(f80 + 120, 86),
            q(f80 + 180, 76),
        ]
        got = M.scan_entry_path(quotes, f80)
        self.assertTrue(got["qualified"])
        self.assertEqual(got["entry_ts"], f80 + 180)

    def test_exit_and_pnl(self):
        self.assertEqual(M.outcome_of(True, False), ("WIN", 23))
        self.assertEqual(M.outcome_of(True, True), ("STOP_40", -37))
        self.assertEqual(M.outcome_of(False, False), ("LOSS_HOLD", -77))


if __name__ == "__main__":
    unittest.main()
