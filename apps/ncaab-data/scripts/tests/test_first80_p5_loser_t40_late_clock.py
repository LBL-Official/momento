#!/usr/bin/env python3
"""Identity tests for P5 H1_2 / H2_1 loser late-clock cut."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
NBA = Path("/Users/user/Desktop/Momento/apps/nba-data/scripts")
for p in (SCRIPTS, NBA):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import first80_p5_loser_t40_late_clock as C  # noqa: E402


class TestP5LateClock(unittest.TestCase):
    def test_identity(self):
        s = C.analyze()
        by = {x["bucket"]: x for x in s["slices"]}
        self.assertEqual(by["H1_2"]["n"], 193)
        self.assertEqual(by["H1_2"]["n_losers"], 30)
        self.assertEqual(by["H2_1"]["n"], 139)
        self.assertEqual(by["H2_1"]["n_losers"], 21)
        self.assertEqual(sum(b["n"] for b in by["H1_2"]["discrete_bins"]), 30)
        self.assertEqual(sum(b["n"] for b in by["H2_1"]["discrete_bins"]), 21)


if __name__ == "__main__":
    unittest.main()
