"""Entry-state features must be labeled causal-at-entry. No terminal in features."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pyarrow.parquet as pq

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import config as C  # noqa: E402


class TestNoLookahead(unittest.TestCase):
    def test_feature_status_causal(self):
        feat = pq.read_table(C.GPE_V2 / "features_entry.parquet", columns=["feature_status", "feature_maximum_source_timestamp", "first_80_timestamp"]).to_pandas()
        self.assertTrue((feat["feature_status"] == "CAUSAL_AT_ENTRY").all())
        ok = feat["feature_maximum_source_timestamp"].isna() | (
            feat["feature_maximum_source_timestamp"] <= feat["first_80_timestamp"]
        )
        self.assertTrue(bool(ok.all()), msg="feature timestamp after first_80")

    def test_pade_future_columns_not_in_alpha_feature_list(self):
        src = (C.SRC / "alpha_persistence.py").read_text()
        self.assertNotIn("future_min", src)
        self.assertNotIn("y_min_le_40", src)
        self.assertIn("TRAIN", src)


if __name__ == "__main__":
    unittest.main()
