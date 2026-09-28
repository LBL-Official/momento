"""Acceptance tests for the two-window study. They do not read the warehouse."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research/first78_67_portfolio_v1/src"))
sys.path.insert(0, str(ROOT / "research/first78_67_oos_adverse_v1/src"))

from first78.money import reference_unit  # noqa: E402
from first78.portfolio import replay  # noqa: E402
from oos_adverse.eligibility import choose_contract, in_window, scan_bars  # noqa: E402
from oos_adverse.inference import marked_drawdown, minute_marks  # noqa: E402
from oos_adverse.oracle import assert_baseline, oracle_tail_ids, worst_acceptance  # noqa: E402
from oos_adverse.scenarios import play, with_stop_failures  # noqa: E402

LA = ZoneInfo("America/Los_Angeles")


def ts(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> int:
    return int(datetime(year, month, day, hour, minute, tzinfo=LA).timestamp())


def bar(stamp: int, bid: int, ask: int, low: int, vol: int = 100) -> dict:
    return {"ts": stamp, "bid": bid, "ask": ask, "low": low, "vol": vol}


class ArithmeticTest(unittest.TestCase):
    def test_reference_fixture(self) -> None:
        unit = reference_unit()
        self.assertEqual(unit["contracts"], 1538)
        self.assertEqual(unit["principal_cents"], 119964)
        self.assertEqual(unit["entry_fee_cents"], 462)
        self.assertEqual(unit["stop_fee_cents"], 596)
        self.assertEqual(unit["net_win_cents"], 33374)
        self.assertEqual(unit["net_stop_cents"], -17976)


class WindowTest(unittest.TestCase):
    def test_boundaries_observe_dst(self) -> None:
        self.assertTrue(in_window(ts(2025, 10, 15), "OCT_2025"))
        self.assertFalse(in_window(ts(2025, 10, 14, 23, 59), "OCT_2025"))
        self.assertFalse(in_window(ts(2025, 11, 1), "OCT_2025"))
        self.assertTrue(in_window(ts(2025, 4, 1), "APR_2025"))
        self.assertTrue(in_window(ts(2025, 4, 30, 23, 59), "APR_2025"))
        self.assertFalse(in_window(ts(2025, 5, 1), "APR_2025"))


class SignalTest(unittest.TestCase):
    def test_unproven_opening_print(self) -> None:
        scanned = scan_bars([bar(1, 8000, 8100, 7900)])
        self.assertEqual(scanned["reason"], "UNPROVEN_FIRST")
        self.assertFalse(scanned["cross_found"])

    def test_chronology_unresolved_is_not_a_win(self) -> None:
        scanned = scan_bars(
            [
                bar(1, 7000, 7100, 6900),
                bar(2, 7800, 7900, 6600),
            ]
        )
        self.assertEqual(scanned["reason"], "CHRONOLOGY_UNRESOLVED")

    def test_proven_cross_then_later_stop(self) -> None:
        scanned = scan_bars(
            [
                bar(1, 7000, 7100, 6900),
                bar(2, 8100, 8200, 7800),
                bar(3, 6700, 6800, 6600),
            ]
        )
        self.assertTrue(scanned["cross_found"])
        self.assertEqual(scanned["stop_ts"], 3)
        self.assertEqual(scanned["observed_close_cents"], 81)

    def test_ticker_tie_and_clock_unavailable(self) -> None:
        contracts = [
            {
                "contract_id": "B",
                "cross_found": True,
                "tradable": True,
                "window_eligible": True,
                "date_eligible": True,
                "signal_ts": 5,
                "clock_bucket": "Q2",
            },
            {
                "contract_id": "A",
                "cross_found": True,
                "tradable": True,
                "window_eligible": True,
                "date_eligible": True,
                "signal_ts": 5,
                "clock_bucket": "Q2",
            },
        ]
        self.assertEqual(choose_contract(contracts)["chosen"]["contract_id"], "A")
        unaligned = [
            {
                "contract_id": "A",
                "cross_found": True,
                "tradable": True,
                "window_eligible": False,
                "date_eligible": True,
                "signal_ts": 5,
                "clock_bucket": "UNALIGNED",
            }
        ]
        self.assertEqual(choose_contract(unaligned)["rejection_reason"], "CLOCK_UNAVAILABLE")


class LedgerTest(unittest.TestCase):
    def _cand(self, game: str, signal: int, exit_ts: int, reason: str = "STOP", sport: str = "NBA") -> dict:
        return {
            "game_id": game,
            "contract_id": game,
            "sport": sport,
            "signal_ts": signal,
            "exit_ts": exit_ts,
            "cash_ts": exit_ts,
            "exit_reason": reason,
            "local_day": "2025-10-15",
            "terminal_result": "yes",
            "settlement_ts": 5000,
        }

    def test_eighth_candidate_is_rejected(self) -> None:
        cands = [self._cand(f"G{i}", 100, 200) for i in range(8)]
        book = replay(
            [{k: c[k] for k in ("game_id", "contract_id", "sport", "signal_ts", "exit_ts", "cash_ts", "exit_reason")} for c in cands],
            cap=7,
        )
        self.assertEqual(len(book.trades), 7)
        self.assertTrue(any(row["reason"] == "CAP" for row in book.rejections))

    def test_cash_delay_keeps_the_receivable_unavailable(self) -> None:
        first = self._cand("A", 0, 100)
        second = self._cand("B", 150, 200)
        prompt = play([first, second], "REF", balance_cents=100_000)
        # 60% is not the study rule; this fixture forces one debit to exhaust cash.
        from decimal import Decimal

        from first78.portfolio import replay as replay_fn

        def rows(delay: int) -> list[dict]:
            out = []
            for cand in (first, second):
                out.append(
                    {
                        "game_id": cand["game_id"],
                        "contract_id": cand["contract_id"],
                        "sport": "NBA",
                        "signal_ts": cand["signal_ts"],
                        "exit_ts": cand["exit_ts"],
                        "cash_ts": cand["exit_ts"] + delay,
                        "exit_reason": "WIN_SETTLEMENT",
                    }
                )
            return out

        ready = replay_fn(rows(0), balance_cents=100_000, allocation_bps=6000, fee_coef=Decimal("0.0175"))
        delayed = replay_fn(rows(1000), balance_cents=100_000, allocation_bps=6000, fee_coef=Decimal("0.0175"))
        self.assertEqual(len(ready.trades), 2)
        self.assertEqual(len(delayed.trades), 1)
        self.assertTrue(any(row["reason"] == "INSUFFICIENT_CASH" for row in delayed.rejections))
        self.assertGreater(prompt.ending_equity_cents, 0)

    def test_failed_stop_holds_the_slot(self) -> None:
        first = self._cand("A", 0, 50)
        second = self._cand("B", 100, 150)
        held = with_stop_failures([first], {"A"})
        self.assertEqual(held[0]["exit_reason"], "WIN_SETTLEMENT")
        self.assertEqual(held[0]["exit_ts"], 5000)
        open_book = play(held + [second], "REF", cap=1)
        free_book = play([first, second], "REF", cap=1)
        self.assertEqual(len(open_book.trades), 1)
        self.assertTrue(any(row["reason"] == "CAP" for row in open_book.rejections))
        self.assertEqual(len(free_book.trades), 2)

    def test_completion_order_is_not_entry_order(self) -> None:
        cands = []
        for i in range(10):
            cands.append(self._cand(f"G{i}", 10 + i, 1000 - i, reason="WIN_SETTLEMENT"))
            cands[-1]["cash_ts"] = cands[-1]["exit_ts"]
            cands[-1]["exit_reason"] = "WIN_SETTLEMENT"
        book = play(cands, "REF", cap=10)
        by_entry = {int(trade["entry_sequence"]): int(trade["completion_sequence"]) for trade in book.trades}
        self.assertEqual(by_entry[10], 1)
        batches = sorted({int(trade["completion_batch_id"]) for trade in book.trades})
        self.assertEqual(batches, sorted(batches))

    def test_accounts_do_not_share_cash(self) -> None:
        one = play([self._cand("A", 0, 10, reason="WIN_SETTLEMENT")], "REF")
        two = play([self._cand("B", 0, 10, reason="LOSS_SETTLEMENT")], "REF")
        self.assertNotEqual(one.ending_equity_cents, two.ending_equity_cents)


class OracleIsolationTest(unittest.TestCase):
    def test_primary_source_has_no_later_threshold(self) -> None:
        text = (ROOT / "research/first78_67_oos_adverse_v1/src/oos_adverse/eligibility.py").read_text()
        self.assertNotIn("8000", text)
        self.assertNotIn("FIRST80", text)
        self.assertNotIn("first80", text)

    def test_baseline_ids_cannot_enter_the_oracle(self) -> None:
        with self.assertRaises(RuntimeError):
            assert_baseline("ORACLE_TAIL_BOUND")
        stops = [{"game_id": f"L{i}", "contract_id": f"L{i}", "terminal_result": "no"} for i in range(1)]
        stops += [{"game_id": f"W{i}", "contract_id": f"W{i}", "terminal_result": "yes"} for i in range(19)]
        self.assertEqual(oracle_tail_ids(stops, 0.05), ["L0"])
        worst = worst_acceptance(
            [
                {"sport": "NBA", "contract_id": "A", "exit_reason": "WIN_SETTLEMENT"},
                {"sport": "NBA", "contract_id": "B", "exit_reason": "LOSS_SETTLEMENT"},
            ],
            0.5,
        )
        self.assertEqual([row["contract_id"] for row in worst], ["B"])


class MinuteMarkTest(unittest.TestCase):
    def test_dip_between_events_is_visible(self) -> None:
        trades = [
            {
                "contract_id": "C",
                "contracts": 100,
                "entry_ts": 0,
                "exit_ts": 180,
            }
        ]
        events = [
            {"ts": 0, "cash_cents": 1_000_000, "receivable_cents": 0, "equity_cents": 1_900_000},
            {"ts": 180, "cash_cents": 1_900_000, "receivable_cents": 0, "equity_cents": 1_900_000},
        ]
        paths = {"C": [(0, 78), (60, 40), (120, 78)]}
        rows = minute_marks(trades, events, paths, 0, 120)
        marked = [row["bid_marked_gross_equity_cents"] for row in rows if row["ts"] == 60][0]
        self.assertEqual(marked, 1_000_000 + 100 * 40)
        dd = marked_drawdown(rows)
        self.assertGreater(dd["max_drawdown_fraction"], 0)


if __name__ == "__main__":
    unittest.main()
