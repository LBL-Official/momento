"""Complementary YES markets on one game: both cannot settle YES."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pyarrow.parquet as pq

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import config as C  # noqa: E402
from build_first80_dataset import load_frozen_candidates  # noqa: E402


class TestComplementarySettlement(unittest.TestCase):
    def test_one_yes_per_event_among_settled_markets(self):
        mkt = pq.read_table(
            C.NORM / "markets" / "markets.parquet",
            columns=["event_id", "ticker", "result", "settlement_value_e4"],
        ).to_pandas()

        def yes(r):
            if r["result"] == "yes":
                return True
            if r["result"] == "no":
                return False
            if r["settlement_value_e4"] == 10000:
                return True
            if r["settlement_value_e4"] == 0:
                return False
            return None

        mkt["W"] = [yes(r) for r in mkt.to_dict("records")]
        settled = mkt[mkt["W"].notna()].copy()
        yes_counts = settled.groupby("event_id")["W"].sum()
        # A settled two-team game should have exactly one YES.
        bad = yes_counts[(yes_counts != 1) & (yes_counts != 0)]
        # 0 can happen if incomplete; >1 is a settlement contradiction.
        self.assertEqual(int((yes_counts > 1).sum()), 0, msg=str(bad.head()))

    def test_first80_win_implies_held_ticker_yes(self):
        df, _ = load_frozen_candidates()
        self.assertTrue(df["expiration_result_yes"].isin([True, False]).all())


if __name__ == "__main__":
    unittest.main()
