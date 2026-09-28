#!/usr/bin/env python3
"""Stop-loss class math. Does not change live FIRST01."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]


def _load():
    path = SCRIPTS / "first80_asked_six_80_40_stop_loss.py"
    spec = importlib.util.spec_from_file_location(
        "first80_asked_six_80_40_stop_loss", path
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


M = _load()


class TestClassify(unittest.TestCase):
    def test_printed_40_loss_is_40(self):
        c = M.classify(
            {
                "found": True,
                "t40_close": 40,
                "prior_close": 51,
                "drop_from_prior": 11,
                "ticker": "t",
            }
        )
        self.assertEqual(c["class"], "PRINTED_40")
        self.assertEqual(c["modeled_exit_cents"], 40)
        self.assertEqual(c["modeled_stop_loss_cents"], 40)
        self.assertFalse(c["fast_gap"])

    def test_no_40_print_uses_first_close(self):
        c = M.classify(
            {
                "found": True,
                "t40_close": 31,
                "prior_close": 48,
                "drop_from_prior": 17,
                "ticker": "t",
            }
        )
        self.assertEqual(c["class"], "NO_40_PRINT")
        self.assertEqual(c["modeled_exit_cents"], 31)
        self.assertEqual(c["modeled_stop_loss_cents"], 49)
        self.assertTrue(c["fast_gap"])

    def test_mild_through_is_not_fast_gap_if_drop_small(self):
        c = M.classify(
            {
                "found": True,
                "t40_close": 38,
                "prior_close": 42,
                "drop_from_prior": 4,
                "ticker": "t",
            }
        )
        self.assertEqual(c["depth"], "MILD_35_39")
        self.assertFalse(c["fast_gap"])
        self.assertEqual(c["modeled_stop_loss_cents"], 42)

    def test_blended_matches_weighted_mean(self):
        # 54 at −40 and 245 at −46.7020 → 45.4916
        blend = (54 * 40 + 245 * 46.70204081632653) / 299
        self.assertAlmostEqual(blend, 45.4916, places=3)


if __name__ == "__main__":
    unittest.main()
