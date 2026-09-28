"""Locked classification rule: OOS path difference CI must exclude 0."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from report import classify  # noqa: E402


def _term(n, k, p_one):
    p = k / n
    return {
        "n": n,
        "k": k,
        "estimate": p,
        "wilson": {"lo": p - 0.02, "hi": p + 0.02},
        "vs_null": {"p_one_sided": p_one},
    }


def _path(n, k):
    return {"n": n, "k": k, "estimate": k / n}


class TestClassification(unittest.TestCase):
    def _ctx(self, oos80, n80, oos75, n75, p_one_full=0.006, oos_pw=0.86, almost=False):
        cal = {
            "FULL": _term(1230, 1019, p_one_full),
            "TRAIN": _term(504, 407, 0.36),
            "OOS": _term(243, 209, 0.01) | {"estimate": oos_pw},
        }
        path = {
            "FIRST80": {
                "full": _path(1019, 910),
                "splits": {"OOS": _path(n80, int(round(oos80 * n80)))},
            },
            "FIRST75": {
                "full": _path(915, 781),
                "splits": {"OOS": _path(n75, int(round(oos75 * n75)))},
            },
            "control_validity": {"first75_almost_identical_to_first80": almost},
        }
        # Force the OOS point estimates used by classify (integer k can drift).
        path["FIRST80"]["splits"]["OOS"]["estimate"] = oos80
        path["FIRST75"]["splits"]["OOS"]["estimate"] = oos75
        return classify(cal, path, {}, {})

    def test_overlapping_oos_path_ci_is_terminal_only(self):
        clf = self._ctx(oos80=0.8756, n80=209, oos75=0.8359, n75=195)
        self.assertLessEqual(clf["oos_path_diff_lo"], 0.0)
        self.assertGreaterEqual(clf["oos_path_diff_hi"], 0.0)
        self.assertEqual(clf["letter"], "A_TERMINAL_CALIBRATION_ONLY")
        self.assertEqual(clf["path_independence_token"], "NO_OOS_CI_SEPARATION")

    def test_separated_oos_path_ci_is_both(self):
        clf = self._ctx(oos80=0.95, n80=400, oos75=0.70, n75=400)
        self.assertGreater(clf["oos_path_diff_lo"], 0.0)
        self.assertEqual(clf["letter"], "C_BOTH")
        self.assertEqual(clf["path_independence_token"], "OOS_DIFFERENCE_CI_EXCLUDES_ZERO")

    def test_point_gap_without_ci_separation_is_not_path_evidence(self):
        # ~4pp gap, n≈200: historically tempting, but CI includes 0.
        clf = self._ctx(oos80=0.88, n80=200, oos75=0.84, n75=200)
        self.assertLessEqual(clf["oos_path_diff_lo"], 0.0)
        self.assertNotEqual(clf["letter"], "C_BOTH")
        self.assertNotEqual(clf["letter"], "B_PATH_EFFECT_ONLY")

    def test_terminal_null_not_rejected_without_path_is_inconclusive(self):
        clf = self._ctx(oos80=0.88, n80=200, oos75=0.86, n75=200, p_one_full=0.20, oos_pw=0.81)
        self.assertEqual(clf["letter"], "D_INCONCLUSIVE")


if __name__ == "__main__":
    unittest.main()
