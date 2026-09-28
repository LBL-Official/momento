#!/usr/bin/env python3
"""Tests for WNBA Q2∪Q3 FIRST80 80→40 and last-5-minute 40-losers.

Binning tests are synthetic. Identity uses the frozen warehouse tape.
Does not change live FIRST01.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import wnba_first80_q23_80_40 as S  # noqa: E402


class TestLast5Bins(unittest.TestCase):
    def test_exactly_300s_is_last_5(self):
        self.assertTrue(S.last5_t40(4, 300.0))
        self.assertEqual(S.LATE.discrete_last6_bin(4, 300.0), "4:01–5:00")

    def test_just_over_5_is_not_last_5(self):
        self.assertFalse(S.last5_t40(4, 300.1))
        self.assertEqual(S.LATE.discrete_last6_bin(4, 300.1), "5:01–6:00")

    def test_q3_remaining_is_not_last_5(self):
        self.assertFalse(S.last5_t40(3, 10.0))
        self.assertEqual(S.LATE.discrete_last6_bin(3, 10.0), "BEFORE_LAST_6")

    def test_ot_is_not_last_5(self):
        self.assertFalse(S.last5_t40(5, 120.0))
        self.assertEqual(S.LATE.discrete_last6_bin(5, 120.0), "OT")

    def test_zero_clock_is_last_5(self):
        self.assertTrue(S.last5_t40(4, 0.0))
        self.assertEqual(S.LATE.discrete_last6_bin(4, 0.0), "0:00–1:00")


class TestPublishedIdentity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = S.analyze()
        cls.summary = cls.result["summary"]

    def test_q2_q3_partition(self):
        self.assertEqual(self.summary["q2"]["n"], 127)
        self.assertEqual(self.summary["q3"]["n"], 119)
        self.assertEqual(self.summary["q23"]["n"], 246)

    def test_published_80_40_joints(self):
        for name, key in (("Q2", "q2"), ("Q3", "q3"), ("Q2∪Q3", "q23")):
            got = S._joint_keys(self.summary[key])
            self.assertEqual(got, S.EXPECTED_JOINTS[name], name)

    def test_no_loss_without_t40(self):
        self.assertEqual(self.summary["q23"]["loss_no_t40"], 0)

    def test_unaligned_stays_out(self):
        self.assertEqual(self.summary["excluded_from_q23"]["UNALIGNED"], 131)
        self.assertTrue(
            all(r["entry_quarter_bucket"] in ("Q2", "Q3") for r in self.result["rows"])
        )

    def test_last5_count_frozen(self):
        last = self.summary["last_5_minutes_40_losers"]
        union = last["Q2∪Q3"]
        self.assertEqual(union["n_losers"], 41)
        self.assertEqual(last["Q2"]["n_last_5_q4"], 13)
        self.assertEqual(last["Q3"]["n_last_5_q4"], 13)
        self.assertEqual(union["n_last_5_q4"], 26)
        self.assertEqual(last["Q2"]["n_last_5_q4"] + last["Q3"]["n_last_5_q4"], union["n_last_5_q4"])
        late = self.summary["late_clock"]["Q2∪Q3"]
        self.assertEqual(sum(b["n"] for b in late["discrete_bins"]), 41)
        last1 = next(c for c in late["cumulative_at_most_k_min"] if c["at_most_min"] == 1)
        self.assertEqual(last1["n"], 14)


if __name__ == "__main__":
    unittest.main()
