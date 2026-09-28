#!/usr/bin/env python3
"""Tests for FIRST75 P(¬T40|W) slice helper.

Synthetic reach/T40 tests plus artifact identity after the warehouse run.
Does not change live FIRST01.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import first75_slice_not40_given_w as M  # noqa: E402


def q(ts: int, bid: int, ask: int | None = None, vol: int = 100) -> dict:
    return {"ts": ts, "bid_c": bid, "ask_c": bid + 100 if ask is None else ask, "vol": vol}


class TestReach(unittest.TestCase):
    def test_needs_prior_close_below_75(self):
        rows = [q(1, 7600), q(2, 7700)]
        self.assertIsNone(M.first_tradable_reach(rows, M.HIT75))

    def test_first_cross_after_below(self):
        rows = [q(1, 7400), q(2, 7600), q(3, 8000)]
        hit = M.first_tradable_reach(rows, M.HIT75)
        self.assertEqual(hit["ts"], 2)

    def test_uncrossed_rejected(self):
        rows = [q(1, 7400, ask=7300), q(2, 7600)]
        # first bar crossed (bid>ask) so quality fails; second is the first quality bar
        # and is already >=75 without a prior below → no reach
        self.assertIsNone(M.first_tradable_reach(rows, M.HIT75))

    def test_t40_must_be_after_reach(self):
        rows = [q(1, 7400), q(2, 3900), q(3, 7600), q(4, 3800)]
        hit = M.first_tradable_reach(rows, M.HIT75)
        t40 = M.first_close_le_after(rows, hit["ts"])
        self.assertEqual(hit["ts"], 3)
        self.assertEqual(t40["ts"], 4)

    def test_same_minute_tie_excluded(self):
        markets = [
            {"event_id": "e", "ticker": "A", "team": "a", "result": "yes", "settlement_value_e4": 10000},
            {"event_id": "e", "ticker": "B", "team": "b", "result": "no", "settlement_value_e4": 0},
        ]
        games = [{"event_id": "e", "game_date": "2026-01-01"}]
        quotes = {
            "A": [q(10, 7400), q(20, 7600)],
            "B": [q(10, 7400), q(20, 7700)],
        }
        rows = M.build_first_reach(markets, games, quotes, M.HIT75, "FIRST_75")
        self.assertEqual(rows[0]["status"], "TIE_SAME_MINUTE")


class TestFourCellDecomp(unittest.TestCase):
    def test_product_identity_and_s_l_zero(self):
        rows = (
            [{"W": True, "T40": False}] * 10
            + [{"W": True, "T40": True}] * 2
            + [{"W": False, "T40": True}] * 5
        )
        d = M.decomp_of_rows(rows, 0.75, "FIRST75")
        self.assertEqual(d["cells"]["L_and_not_T40"], 0)
        self.assertEqual(d["loser_path"]["estimate"], 0.0)
        self.assertAlmostEqual(d["reconstruction"]["p_times_s_W"], 10 / 17)
        self.assertAlmostEqual(d["reconstruction"]["S"], 10 / 17)
        self.assertAlmostEqual(d["joint_win_survive"]["estimate"], 10 / 17)
        self.assertAlmostEqual(sum(d["cell_probs"].values()), 1.0)

    def test_loser_survivor_enters_S(self):
        rows = [{"W": True, "T40": False}] * 3 + [{"W": False, "T40": False}] * 1
        d = M.decomp_of_rows(rows, 0.75, "FIRST75")
        self.assertEqual(d["cells"]["L_and_not_T40"], 1)
        self.assertAlmostEqual(d["reconstruction"]["S"], 1.0)
        self.assertAlmostEqual(d["reconstruction"]["p_times_s_W"], 0.75)


class TestTerminalCalibration(unittest.TestCase):
    def test_alpha_is_p_minus_75(self):
        rec = M.p_w_given_first75(78, 100)
        self.assertEqual(rec["pct"], 78.0)
        self.assertEqual(rec["alpha_75_pct_points"], 3.0)
        self.assertAlmostEqual(rec["alpha_75_terminal"], 0.03)
        self.assertFalse(rec["ci_excludes_75"])

    def test_perfect_calibration_alpha_zero(self):
        rec = M.p_w_given_first75(75, 100)
        self.assertEqual(rec["pct"], 75.0)
        self.assertEqual(rec["alpha_75_pct_points"], 0.0)

    def test_pooled_six_from_artifact(self):
        path = M.REPORTS / "summary.json"
        if not path.exists():
            self.skipTest("summary not written yet")
        raw = json.loads(path.read_text())
        # Recompute from slice counts even if calibration block is stale.
        n = w = 0
        for sport, sl, _ in M.ASKED_SIX:
            rec = raw["sports"][sport]["slices"][sl]["FIRST75"]
            n += rec["n_total"]
            w += rec["n_wins"]
        self.assertEqual((n, w), (1126, 871))
        cal = M.p_w_given_first75(w, n)
        self.assertEqual(cal["pct"], 77.3535)
        self.assertFalse(cal["ci_excludes_75"])

    def test_pooled_decomp_if_written(self):
        path = M.REPORTS / "summary.json"
        if not path.exists():
            self.skipTest("summary not written yet")
        s = json.loads(path.read_text())
        if "pooled_six_decomp" not in s:
            self.skipTest("decomp not written yet")
        d = s["pooled_six_decomp"]["FIRST75"]
        self.assertEqual(d["n"], 1126)
        self.assertEqual(d["N_W"], 871)
        self.assertEqual(d["winner_path"]["k"], 750)
        self.assertAlmostEqual(d["reconstruction"]["p_times_s_W"], d["cell_probs"]["W_and_not_T40"])
        self.assertEqual(sum(d["cells"].values()), 1126)


class TestArtifactIdentity(unittest.TestCase):
    def test_published_slice_counts(self):
        path = M.REPORTS / "summary.json"
        if not path.exists():
            self.skipTest("summary not written yet")
        s = json.loads(path.read_text())
        p = s["sports"]["nba"]["FIRST75_full"]
        self.assertEqual(p["n_total"], 1176)
        self.assertEqual(p["n_wins"], 915)
        self.assertEqual(p["k_not_t40"], 781)
        want = {
            ("wnba", "Q2"): (105, 91),
            ("wnba", "Q3"): (70, 59),
            ("nba", "Q2"): (242, 208),
            ("nba", "Q3"): (192, 167),
            ("ncaab_p5", "H1_2"): (152, 126),
            ("ncaab_p5", "H2_1"): (110, 99),
        }
        for (sport, sl), (w, k) in want.items():
            rec = s["sports"][sport]["slices"][sl]["FIRST75"]
            self.assertEqual((rec["n_wins"], rec["k_not_t40"]), (w, k), f"{sport} {sl}")


if __name__ == "__main__":
    unittest.main()
