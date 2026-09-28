#!/usr/bin/env python3
"""Tests for as-of four-cell predictor. No live trading."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import firstq_fourcell_asof_predictor as M  # noqa: E402


class TestCellsAndProbs(unittest.TestCase):
    def test_four_cells(self):
        self.assertEqual(M.cell_of(True, False), "WIN_SURVIVE")
        self.assertEqual(M.cell_of(True, True), "WIN_T40")
        self.assertEqual(M.cell_of(False, False), "LOSE_SURVIVE")
        self.assertEqual(M.cell_of(False, True), "LOSE_T40")

    def test_laplace_sums_to_one(self):
        from collections import Counter

        p = M.probs_from_counts(Counter({"WIN_SURVIVE": 10}))
        self.assertAlmostEqual(sum(p.values()), 1.0)
        self.assertGreater(p["LOSE_T40"], 0.0)

    def test_unaligned_uses_uncond(self):
        train = [
            {
                "stratum": "2|0-4|LEAD|H",
                "cell": "WIN_SURVIVE",
                "matchable": True,
            }
        ] * 20 + [
            {
                "stratum": "2|0-4|LEAD|H",
                "cell": "LOSE_T40",
                "matchable": True,
            }
        ] * 5
        model = M.fit(train)
        unaligned = {"stratum": "UNALIGNED", "cell": "WIN_SURVIVE", "matchable": False}
        self.assertEqual(M.predict_row(unaligned, model), model["unconditional"])

    def test_features_exclude_future(self):
        train = [{"stratum": "2|0-4|LEAD|H", "cell": "WIN_SURVIVE", "matchable": True}]
        model = M.fit(train)
        for bad in ("W", "T40", "expiration", "first_40_close_ts"):
            self.assertNotIn(bad, model["features"])

    def test_decision_requires_oos_ci(self):
        val = {"n": 10, "model_better_logloss": True}
        oos = {
            "n": 10,
            "model_better_logloss": True,
            "delta_ci_excludes_0": False,
            "logloss_delta_ci95": [-0.01, 0.02],
        }
        self.assertFalse(M.decision(val, oos)["established"])


class TestArtifact(unittest.TestCase):
    def test_identity_if_written(self):
        path = M.REPORTS / "summary.json"
        if not path.exists():
            self.skipTest("summary not written")
        s = json.loads(path.read_text())
        self.assertEqual(s["first80"]["n"], 1230)
        self.assertEqual(s["first75"]["n"], 1176)
        self.assertTrue(s["no_future_in_F"])
        self.assertEqual(sum(s["first80"]["cells"].values()), 1230)


if __name__ == "__main__":
    unittest.main()
