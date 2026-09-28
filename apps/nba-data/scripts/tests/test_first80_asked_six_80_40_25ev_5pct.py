#!/usr/bin/env python3
"""+2.5¢ planning-EV identity. Does not change live FIRST01."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]


def _load():
    path = SCRIPTS / "first80_asked_six_80_40_25ev_5pct.py"
    spec = importlib.util.spec_from_file_location(
        "first80_asked_six_80_40_25ev_5pct", path
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


M = _load()


class TestPlanningEV(unittest.TestCase):
    def test_exactly_two_point_five(self):
        self.assertEqual(M.EXPECTED_WIN * 20 - int(M.STOP_LOSS_BAG.sum()), 2955)
        self.assertEqual(M.planning_ev_cents(), 2.5)
        self.assertEqual(M.N_TRADES, 220)
        self.assertEqual(M.F_PCT, 5)

    def test_stop_bag_is_49_or_50(self):
        self.assertTrue(set(M.STOP_LOSS_BAG.tolist()) <= {49, 50})
        self.assertEqual(int(M.STOP_LOSS_BAG.sum()), 14705)


if __name__ == "__main__":
    unittest.main()
