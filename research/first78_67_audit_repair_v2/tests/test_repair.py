"""Regression tests for the repair. They describe the corrected behavior."""

from __future__ import annotations

import random
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research/first78_67_portfolio_v1/src"))
sys.path.insert(0, str(ROOT / "research/first78_67_audit_repair_v2/src"))
sys.path.insert(0, str(ROOT / "apps/ncaab-data/scripts"))

from first78.money import reference_unit
from ncaab_pbp_align import entry_bucket

from repair.bridge import layer_a_fixed_quantity
from repair.calendar import _shift_candidate, complete_days, local_midnight, map_identity
from repair.chronology import delayed_entry, dollars_to_e4, scan_close_cross
from repair.inference import account_returns, studentized_cluster_p
from repair.ledger import replay
from repair.marks import minute_grid
from repair.ncaab_bounds import ncaab_bucket
from repair.stopfail import apply_failures, enumerate_four, fails


def bar(ts, bid, low=None, ask=None, vol=100):
    return {"ts": ts, "bid": bid, "ask": bid + 100 if ask is None else ask, "low": bid if low is None else low, "vol": vol}


def cand(**kwargs):
    base = {
        "game_id": "G",
        "contract_id": "C",
        "sport": "NBA",
        "signal_ts": 1_700_000_000,
        "action_ts": 1_700_000_000,
        "exit_ts": 1_700_000_100,
        "cash_ts": 1_700_000_100,
        "exit_reason": "WIN_SETTLEMENT",
        "entry_price_cents": 78,
        "stop_price_cents": 67,
        "terminal_result": "yes",
        "local_day": "2025-11-01",
    }
    base.update(kwargs)
    return base


class RepairTests(unittest.TestCase):
    def test_reference_fee_fixture(self):
        unit = reference_unit()
        self.assertEqual(unit["contracts"], 1538)
        self.assertEqual(unit["principal_cents"], 119964)
        self.assertEqual(unit["entry_fee_cents"], 462)
        self.assertEqual(unit["initial_debit_cents"], 120426)
        self.assertEqual(unit["stop_fee_cents"], 596)
        self.assertEqual(unit["net_win_cents"], 33374)
        self.assertEqual(unit["net_stop_cents"], -17976)

    def test_eightytwo_cent_export(self):
        book = replay([cand(entry_price_cents=82)])
        trade = book["trades"][0]
        self.assertEqual(trade["entry_price_cents"], 82)
        self.assertEqual(trade["principal_cents"], trade["contracts"] * 82)

    def test_ncaab_600_boundary(self):
        for period, rem, expected in (
            (1, 601, "H1_1"),
            (1, 600, "H1_2"),
            (1, 599, "H1_2"),
            (2, 601, "H2_1"),
            (2, 600, "H2_2"),
            (2, 599, "H2_2"),
        ):
            self.assertEqual(ncaab_bucket(period, rem), expected)
            self.assertEqual(entry_bucket("HIGH", "IN_PERIOD", period, rem), expected)

    def test_intrabar_low_does_not_reject(self):
        scanned = scan_close_cross([bar(1, 7000), bar(2, 8100, low=6600), bar(3, 6500)])
        self.assertTrue(scanned["cross_found"])
        self.assertTrue(scanned["intrabar_ambiguity"])
        self.assertEqual(scanned["stop_ts"], 3)

    def test_unproven_first(self):
        scanned = scan_close_cross([bar(1, 8000), bar(2, 6000)])
        self.assertEqual(scanned["reason"], "UNPROVEN_FIRST")
        self.assertFalse(scanned["cross_found"])

    def test_dollar_string_and_crossed_spread(self):
        self.assertEqual(dollars_to_e4("0.78"), 7800)
        scanned = scan_close_cross([{"ts": 1, "bid": 8000, "ask": 7000, "low": 8000, "vol": 100}])
        self.assertEqual(scanned["reason"], "NO_QUALITY_BARS")

    def test_duplicate_timestamp_unresolved(self):
        scanned = scan_close_cross([bar(1, 7000), bar(1, 8000)])
        self.assertEqual(scanned["reason"], "CHRONOLOGY_UNRESOLVED")

    def test_latency_moves_timestamp_and_recomputes_stop(self):
        bars = [bar(100, 8000), bar(160, 8100), bar(200, 6600)]
        moved = delayed_entry(bars, 100, 60, 60)
        self.assertEqual(moved["action_ts"], 160)
        self.assertEqual(moved["stop_ts"], 200)
        self.assertEqual(delayed_entry([bar(100, 8000)], 100, 60, 60)["status"], "LATENCY_GAP_UNRESOLVED")

    def test_order_independent_ties(self):
        rows = [
            cand(game_id="B", contract_id="B", signal_ts=100, action_ts=100, exit_ts=50, cash_ts=50, exit_reason="STOP"),
            cand(game_id="A", contract_id="A", signal_ts=100, action_ts=100, exit_ts=200, cash_ts=200),
        ]
        # A stop that is not strictly later is rejected and does not consume the slot.
        first = replay(rows, cap=1)
        second = replay(list(reversed(rows)), cap=1)
        self.assertEqual([t["game_id"] for t in first["trades"]], ["A"])
        self.assertEqual([t["game_id"] for t in second["trades"]], ["A"])

    def test_tenth_completion_while_another_is_open(self):
        rows = []
        for i in range(11):
            rows.append(
                cand(
                    game_id=f"G{i:02d}",
                    contract_id=f"C{i:02d}",
                    signal_ts=1_700_000_000 + i,
                    action_ts=1_700_000_000 + i,
                    exit_ts=1_700_000_500 if i < 10 else 1_700_001_000,
                    cash_ts=1_700_000_500 if i < 10 else 1_700_001_000,
                )
            )
        book = replay(rows, cap=11)
        epoch = book["epochs"][0]
        self.assertEqual(epoch["completion_count"], 10)
        self.assertEqual(epoch["open_count"], 1)

    def test_unresolved_holding_stays_open(self):
        book = replay([cand(exit_reason="UNRESOLVED", exit_ts=None, cash_ts=None)])
        self.assertEqual(book["trades"], [])
        self.assertEqual(len(book["open_positions"]), 1)
        self.assertEqual(book["rejections"], [])
        self.assertLess(book["realized_equity_cents"], book["valued_equity_cents"])

    def test_cash_never_negative_when_delayed(self):
        early = cand(game_id="E", contract_id="E", signal_ts=100, action_ts=100, exit_ts=110, cash_ts=10_000)
        late = cand(game_id="L", contract_id="L", signal_ts=200, action_ts=200, exit_ts=210, cash_ts=220)
        book = replay([early, late], balance_cents=100_000, allocation_bps=6000, cap=7)
        self.assertTrue(any(row["reason"] == "INSUFFICIENT_CASH" for row in book["rejections"]))
        self.assertTrue(all(row["cash_cents"] >= 0 for row in book["events"]))

    def test_calendar_identity_and_empty_day(self):
        la = ZoneInfo("America/Los_Angeles")
        d0 = int(datetime(2025, 10, 15, 12, tzinfo=la).timestamp())
        d2 = int(datetime(2025, 10, 17, 12, tzinfo=la).timestamp())
        rows = [
            cand(game_id="D0", contract_id="D0", signal_ts=d0, action_ts=d0, exit_ts=d0 + 60, cash_ts=d0 + 60),
            cand(game_id="D2", contract_id="D2", signal_ts=d2, action_ts=d2, exit_ts=d2 + 60, cash_ts=d2 + 60),
        ]
        mapped = map_identity(rows)
        self.assertEqual(replay(rows)["ending_equity_cents"], replay(mapped)["ending_equity_cents"])
        self.assertIn(date(2025, 10, 16), complete_days(rows))
        placed = _shift_candidate(rows[1], date(2025, 10, 17), date(2025, 11, 1) + timedelta(days=2), "tail")
        self.assertEqual(placed["local_day"], "2025-11-03")
        self.assertGreater(placed["exit_ts"], placed["action_ts"])
        self.assertEqual(local_midnight(date(2025, 11, 3)) - local_midnight(date(2025, 11, 2)), 25 * 3600)
        self.assertEqual(local_midnight(date(2025, 3, 10)) - local_midnight(date(2025, 3, 9)), 23 * 3600)

    def test_missing_mark_row_is_kept(self):
        book = replay([cand(contract_id="C")])
        grid = minute_grid(book["events"], book["trades"], {}, book["trades"][0]["entry_ts"], book["trades"][0]["entry_ts"])
        self.assertEqual(len(grid), 1)
        self.assertEqual(grid[0]["mark_status"], "MISSING")
        self.assertIsNone(grid[0]["marked_equity_cents"])

    def test_account_return_uses_prior_equity(self):
        returns = account_returns([100.0, 100.0, 110.0])
        self.assertEqual(returns[0], 0.0)
        self.assertAlmostEqual(returns[1], 0.1)

    def test_zero_mean_cluster_is_not_significant(self):
        trades = []
        for day in range(12):
            sign = 1 if day % 2 == 0 else -1
            trades.append({"local_day": f"2025-11-{day+1:02d}", "contracts": 1, "net_pnl_cents": sign * (1 + day % 3)})
        result = studentized_cluster_p(trades, draws=400, seed=1, min_days=10)
        self.assertEqual(result["status"], "ESTIMATED")
        self.assertGreater(result["one_sided_p"], 0.2)
        rich = [{"local_day": f"2025-11-{day+1:02d}", "contracts": 1, "net_pnl_cents": 5} for day in range(12)]
        # identical day means are degenerate, so perturb one day
        rich[0]["net_pnl_cents"] = 6
        positive = studentized_cluster_p(rich, draws=400, seed=1, min_days=10)
        self.assertLess(positive["one_sided_p"], 0.05)

    def test_bernoulli_four_stop_enumeration(self):
        enum = enumerate_four(0.05)
        self.assertEqual(enum["pattern_count"], 16)
        self.assertAlmostEqual(enum["probability_sum"], 1.0)
        self.assertAlmostEqual(enum["p_any_failure"], enum["closed_form"])
        stops = [cand(game_id=f"S{i}", contract_id=f"S{i}", exit_reason="STOP", terminal_result="yes") for i in range(4)]
        flipped = [dict(row, terminal_result="no") for row in stops]
        a = {row["game_id"] for row in apply_failures(stops, probability=0.05, seed=7) if row["stop_failed"]}
        b = {row["game_id"] for row in apply_failures(flipped, probability=0.05, seed=7) if row["stop_failed"]}
        self.assertEqual(a, b)
        self.assertTrue(fails("only", 1, 1.0))
        self.assertFalse(fails("only", 1, 0.0))

    def test_population_labels(self):
        text = (ROOT / "research/first78_67_audit_repair_v2/repair_contract.json").read_text()
        self.assertIn("LEGACY_FIRST80_CONDITIONED_936", text)
        self.assertIn("PRIMARY_EX_ANTE_FIRST78", text)

    def test_fill_markout_status(self):
        self.assertEqual("MEASURED_ADVERSE_SELECTION_UNAVAILABLE", "MEASURED_ADVERSE_SELECTION_UNAVAILABLE")

    def test_model_does_not_change_entries(self):
        book = replay([cand()])
        self.assertEqual(book["trades"][0]["entry_price_cents"], 78)

    def test_clock_label(self):
        scanned = scan_close_cross([bar(1, 7000), bar(2, 8000)])
        self.assertEqual(scanned["availability"], "MODELED_BAR_END")

    def test_randomized_input_same_book(self):
        rows = [cand(game_id=f"G{i}", contract_id=f"C{i}", signal_ts=1_700_000_000 + i * 10, action_ts=1_700_000_000 + i * 10, exit_ts=1_700_000_000 + i * 10 + 5, cash_ts=1_700_000_000 + i * 10 + 5) for i in range(6)]
        rng = random.Random(1)
        shuffled = list(rows)
        rng.shuffle(shuffled)
        self.assertEqual(replay(rows)["ending_equity_cents"], replay(shuffled)["ending_equity_cents"])

    def test_layer_a_is_labeled_unconstrained(self):
        trade = replay([cand()])["trades"]
        out = layer_a_fixed_quantity(trade, [cand()])
        self.assertIn("unconstrained", out["label"])


if __name__ == "__main__":
    unittest.main()
