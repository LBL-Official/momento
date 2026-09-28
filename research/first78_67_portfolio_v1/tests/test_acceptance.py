"""Acceptance tests for money, selection, clocks, and the portfolio ledger."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from first78.money import fee_charged_cents, fee_raw, reference_unit  # noqa: E402
from first78.portfolio import replay  # noqa: E402
from first78.select import select_game  # noqa: E402
from first78.timeutil import in_historical_entry_window  # noqa: E402


def _cand(game, ts, exit_ts, reason="WIN_SETTLEMENT", cash_ts=None, sport="NBA"):
    return {
        "game_id": game,
        "contract_id": game + "-YES",
        "sport": sport,
        "signal_ts": ts,
        "exit_ts": exit_ts,
        "cash_ts": cash_ts if cash_ts is not None else exit_ts,
        "exit_reason": reason,
    }


class MoneyTests(unittest.TestCase):
    def test_reference_1538(self):
        row = reference_unit()
        self.assertEqual(row["principal_target_cents"], 120_000)
        self.assertEqual(row["contracts"], 1538)
        self.assertEqual(row["principal_cents"], 119_964)
        self.assertEqual(row["entry_fee_cents"], 462)
        self.assertEqual(row["initial_debit_cents"], 120_426)
        self.assertEqual(row["stop_fee_cents"], 596)
        self.assertEqual(row["gross_win_cents"], 33_836)
        self.assertEqual(row["net_win_cents"], 33_374)
        self.assertEqual(row["gross_stop_cents"], -16_918)
        self.assertEqual(row["net_stop_cents"], -17_976)
        self.assertEqual(Decimal(row["gross_breakeven"]).quantize(Decimal("0.000001")), Decimal("0.333333"))
        self.assertEqual(Decimal(row["fee_adjusted_breakeven"]).quantize(Decimal("0.000001")), Decimal("0.350068"))

    def test_raw_fee_below_charged(self):
        raw = fee_raw(1538, 78)
        self.assertLess(raw, Decimal("4.62"))
        self.assertEqual(fee_charged_cents(raw), 462)

    def test_price_bounds(self):
        with self.assertRaises(ValueError):
            fee_raw(1, 0)
        with self.assertRaises(ValueError):
            fee_raw(1, 100)
        with self.assertRaises(ValueError):
            reference_unit(entry_cents=67, stop_cents=67)


class SelectTests(unittest.TestCase):
    def test_rules_differ_when_other_side_is_earlier(self):
        early = {
            "contract_id": "A",
            "signal_ts": 10,
            "cross_found": True,
            "window_eligible": False,
            "date_eligible": True,
            "tradable": True,
        }
        later = {
            "contract_id": "B",
            "signal_ts": 20,
            "cross_found": True,
            "window_eligible": True,
            "date_eligible": True,
            "tradable": True,
        }
        contract = select_game([early, later], "CONTRACT_WISE_FIRST")
        game = select_game([early, later], "GAME_WIDE_FIRST")
        self.assertEqual(contract["chosen"]["contract_id"], "B")
        self.assertIsNone(game["chosen"])
        self.assertEqual(game["rejection_reason"], "GAME_WIDE_OUTSIDE_WINDOW")

    def test_tie_is_ticker_not_outcome(self):
        a = {"contract_id": "B", "signal_ts": 5, "cross_found": True, "window_eligible": True, "date_eligible": True, "tradable": True, "terminal_yes": True}
        b = {"contract_id": "A", "signal_ts": 5, "cross_found": True, "window_eligible": True, "date_eligible": True, "tradable": True, "terminal_yes": False}
        chosen = select_game([a, b], "CONTRACT_WISE_FIRST")["chosen"]
        self.assertEqual(chosen["contract_id"], "A")


class ClockTests(unittest.TestCase):
    def test_april_1_inclusive_and_dst(self):
        # 2026-04-01 23:30 PDT = 2026-04-02 06:30 UTC
        inside = datetime(2026, 4, 2, 6, 30, tzinfo=timezone.utc)
        outside = datetime(2026, 4, 2, 7, 0, tzinfo=timezone.utc)
        self.assertTrue(in_historical_entry_window(inside))
        self.assertFalse(in_historical_entry_window(outside))
        # January is PST (UTC−8); March 9 2026 is PDT (UTC−7)
        jan = datetime(2026, 1, 15, 8, 0, tzinfo=timezone.utc)
        mar = datetime(2026, 3, 9, 7, 0, tzinfo=timezone.utc)
        from first78.timeutil import iso_la

        self.assertIn("PST", iso_la(jan))
        self.assertIn("PDT", iso_la(mar))


class PortfolioTests(unittest.TestCase):
    def test_eight_candidates_admit_seven_and_no_reentry(self):
        rows = [_cand(f"G{i}", 1_000, 2_000, sport="NBA" if i % 2 == 0 else "NCAAB") for i in range(8)]
        rows.append(_cand("G7", 1_500, 2_500))
        book = replay(rows, cap=7)
        self.assertEqual(len(book.trades), 7)
        self.assertEqual(book.max_open, 7)
        reasons = [r["reason"] for r in book.rejections]
        self.assertIn("CAP", reasons)
        self.assertIn("REENTRY_CONSUMED", reasons)
        sports = {t["sport"] for t in book.trades}
        self.assertEqual(sports, {"NBA", "NCAAB"})

    def test_same_time_exit_frees_slot_before_entry(self):
        rows = [_cand(f"G{i}", 1_000, 2_000) for i in range(7)]
        rows.append(_cand("GNEW", 2_000, 3_000))
        book = replay(rows, cap=7)
        self.assertEqual(len(book.trades), 8)
        reverse = replay(rows, cap=7, reverse_priority=True)
        self.assertEqual(len(reverse.trades), 7)
        self.assertTrue(any(r["reason"] == "CAP" and r["game_id"] == "GNEW" for r in reverse.rejections))

    def test_ten_completions_resize_once_and_keep_open_quantity(self):
        # Non-overlapping so each signal arrives after the prior slot is free.
        rows = [
            _cand(f"G{i}", 1_000 + i * 100, 1_050 + i * 100, reason="LOSS_SETTLEMENT")
            for i in range(12)
        ]
        book = replay(rows, cap=7, balance_cents=2_000_000)
        self.assertEqual(len(book.trades), 12)
        resized = [t for t in book.trades if t["resized_after"]]
        self.assertEqual(len(resized), 1)
        self.assertEqual(resized[0]["completion_sequence"], 10)
        epoch0 = [t["contracts"] for t in book.trades if t["epoch_id"] == 0]
        self.assertEqual(len(epoch0), 10)
        self.assertEqual(len(set(epoch0)), 1)
        self.assertEqual(book.trades[10]["epoch_id"], 1)
        self.assertNotEqual(book.trades[10]["contracts"], epoch0[0])

    def test_strict_batch_waits(self):
        rows = [_cand(f"G{i}", 100 + i, 100 + i + 5, reason="LOSS_SETTLEMENT") for i in range(12)]
        book = replay(rows, cap=7, mode="strict_batches")
        reasons = [r["reason"] for r in book.rejections]
        self.assertIn("BATCH_WAIT", reasons)
        self.assertLessEqual(sum(1 for t in book.trades if t["strict_batch_id"] == 0), 10)

    def test_insufficient_cash_and_no_negative(self):
        rows = [_cand(f"G{i}", 10, 5_000, reason="WIN_SETTLEMENT") for i in range(20)]
        book = replay(rows, balance_cents=2_000_000, cap=20)
        self.assertTrue(any(r["reason"] == "INSUFFICIENT_CASH" for r in book.rejections))
        self.assertGreaterEqual(book.ending_cash_cents, 0)
        self.assertLessEqual(book.max_open, 20)

    def test_stop_loss_not_forced_to_eleven_cents_when_settlement_loses_without_stop(self):
        book = replay([_cand("G1", 10, 50, reason="LOSS_SETTLEMENT")], balance_cents=2_000_000)
        trade = book.trades[0]
        self.assertEqual(trade["exit_reason"], "LOSS_SETTLEMENT")
        self.assertLess(trade["net_pnl_cents"], -trade["contracts"] * 11)
        self.assertEqual(trade["gross_pnl_cents"], -trade["principal_cents"])

    def test_cash_identity(self):
        book = replay(
            [
                _cand("G1", 10, 40, reason="WIN_SETTLEMENT", cash_ts=80),
                _cand("G2", 20, 50, reason="STOP"),
            ],
            balance_cents=2_000_000,
        )
        net = sum(t["net_pnl_cents"] for t in book.trades)
        fees = sum(t["entry_fee_cents"] + t["exit_fee_cents"] for t in book.trades)
        gross = sum(t["gross_pnl_cents"] for t in book.trades)
        self.assertEqual(gross - fees, net)
        self.assertEqual(book.ending_equity_cents, 2_000_000 + net)
        self.assertEqual(book.ending_receivable_cents, 0)


if __name__ == "__main__":
    unittest.main()
