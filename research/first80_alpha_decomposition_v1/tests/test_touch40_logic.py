"""Primary T40 is post-entry close-path 40. Wick is not substituted."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from build_first80_dataset import load_frozen_candidates  # noqa: E402


class TestTouch40Logic(unittest.TestCase):
    def test_tree_partition(self):
        df, _ = load_frozen_candidates()
        self.assertEqual(int(df["win_and_not_T40"].sum()), 910)
        self.assertEqual(int(df["win_and_T40"].sum()), 109)
        self.assertEqual(int(df["loss_and_not_T40"].sum()), 0)
        self.assertEqual(int(df["loss_and_T40"].sum()), 211)
        self.assertEqual(int(df["T40"].sum()), 320)

    def test_t40_after_entry(self):
        df, _ = load_frozen_candidates()
        hit = df[df["T40"] & df["first_40_close_ts"].notna()]
        self.assertTrue((hit["first_40_close_ts"] > hit["first_80_timestamp"]).all())

    def test_primary_is_close_not_wick(self):
        df, _ = load_frozen_candidates()
        self.assertIn("stop_close_triggered", df.columns)
        self.assertIn("stop_low_triggered", df.columns)
        self.assertEqual(int(df["T40"].sum()), int(df["stop_close_triggered"].sum()))


if __name__ == "__main__":
    unittest.main()
