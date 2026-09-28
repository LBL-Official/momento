"""Frozen FIRST80 identity. Does not rescan candles."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import config as C  # noqa: E402
from build_first80_dataset import identity_gate, load_frozen_candidates  # noqa: E402


class TestFirst80Definition(unittest.TestCase):
    def test_frozen_counts(self):
        df, cands = load_frozen_candidates()
        gate = identity_gate(df)
        self.assertEqual(gate["status"], "PASS", gate)
        self.assertEqual(len(df), 1230)
        self.assertEqual(int(df["W"].sum()), 1019)
        statuses = {c.get("status") for c in cands}
        self.assertIn("FIRST_80", statuses)
        self.assertTrue((df["status"] == "FIRST_80").all())

    def test_one_per_event(self):
        df, _ = load_frozen_candidates()
        self.assertEqual(df["event_id"].nunique(), len(df))

    def test_definition_lock_mentions_audit(self):
        self.assertIn("yes_bid_close", C.SPECIFICATION_LOCKS["first80_definition"])


if __name__ == "__main__":
    unittest.main()
