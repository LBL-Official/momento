#!/usr/bin/env python3
"""Tests for 2Q/3Q barrier-carryover protocol."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import first80_q23_barrier_carryover_protocol as M  # noqa: E402


class TestProtocol(unittest.TestCase):
    def test_identity_and_world_targets(self):
        s = M.analyze()
        self.assertEqual(s["observed_2025_26"]["n"], 604)
        self.assertEqual(s["observed_2025_26"]["w_not"], 450)
        self.assertAlmostEqual(s["world_predictions_if_k80_means_p75"]["A"]["P_bar_pct"], 66.8317, places=2)
        self.assertAlmostEqual(s["world_predictions_if_k80_means_p75"]["S"]["P_bar_pct"], 74.5033, places=2)
        self.assertGreater(s["how_to_decide"]["sample"]["approx_n_for_95_separation"], 100)

    def test_december_already_near_world_a(self):
        s = M.analyze()
        self.assertEqual(s["intra_season_move"]["nov_P_bar_pct"], 80.2198)
        self.assertEqual(s["intra_season_move"]["dec_P_bar_pct"], 65.8824)
        dec = next(m for m in s["months"] if m["label"] == "2025-12")
        self.assertEqual(dec["n"], 85)


if __name__ == "__main__":
    unittest.main()
