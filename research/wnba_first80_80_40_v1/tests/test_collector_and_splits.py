"""Locked WNBA FIRST80 helpers. No candle scan."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path("/Users/user/Desktop/Momento/apps/wnba-data/scripts")
NBA = Path("/Users/user/Desktop/Momento/apps/nba-data/scripts")
sys.path.insert(0, str(NBA))
sys.path.insert(0, str(SCRIPTS))

import nba_80_40_execution_audit as A  # noqa: E402
import wnba_80_40_execution_audit as W  # noqa: E402
import wnba_collector_quotes as C  # noqa: E402


class DateAndQuality(unittest.TestCase):
    def test_game_date_from_event(self):
        self.assertEqual(
            C.game_date_from_event("KXWNBAGAME-26JUN18ATLIND"), "2026-06-18"
        )
        self.assertEqual(C.game_date_from_event("KXWNBAGAME-25MAY16NYLA"), "2025-05-16")
        self.assertIsNone(C.game_date_from_event("KXWNBAGAME-XX"))

    def test_volume_gate_waiver(self):
        self.assertTrue(C.quality_spread_only(8000, 8100, None, False))
        self.assertFalse(C.quality_spread_only(8000, 9200, None, False))
        self.assertFalse(A.quality(8000, 8100, None, False))

    def test_splits_locked_a_priori(self):
        self.assertEqual(A.SPLIT_RESEARCH_END, "2025-10-31")
        self.assertEqual(A.SPLIT_VAL_END, "2026-07-15")
        self.assertEqual(A.dataset_split("2025-10-31"), "IN_SAMPLE")
        self.assertEqual(A.dataset_split("2026-06-18"), "VALIDATION")
        self.assertEqual(A.dataset_split("2026-07-16"), "OOS")

    def test_demo_fixture_detected(self):
        self.assertTrue(W.is_demo_fixture(W.DEMO_SEASON))
        parquet = W.NORM / "markets" / "markets.parquet"
        self.assertEqual(W.warehouse_usable(), parquet.exists())


if __name__ == "__main__":
    unittest.main()
