#!/usr/bin/env python3
"""Locks the named Lebronner arithmetic. Does not change live FIRST01."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import lebronner as M  # noqa: E402


class TestLockedCounts(unittest.TestCase):
    def test_pooled_cells_sum(self):
        self.assertEqual(M.WIN_NO + M.WIN_T40 + M.LOSE_NO + M.LOSE_T40, M.N75)
        self.assertEqual(M.WIN_NO + M.WIN_T40, 871)
        self.assertEqual(M.LOSE_NO + M.LOSE_T40, 255)
        self.assertEqual(M.WIN_NO + M.LOSE_NO, 751)

    def test_slices_reconstruct_pool(self):
        self.assertEqual(sum(s["n"] for s in M.SLICES), 1126)
        self.assertEqual(sum(s["W"] for s in M.SLICES), 871)
        self.assertEqual(sum(s["win_no"] for s in M.SLICES), 750)
        self.assertEqual(sum(s["lose_no"] for s in M.SLICES), 1)

    def test_only_nba_q2_has_loser_survivor(self):
        survivors = [(s["sport"], s["slice"], s["lose_no"]) for s in M.SLICES if s["lose_no"]]
        self.assertEqual(survivors, [("NBA", "2Q", 1)])


class TestIdentities(unittest.TestCase):
    def test_product_and_total_probability(self):
        d = M.rates_from_cells(M.WIN_NO, M.WIN_T40, M.LOSE_NO, M.LOSE_T40)
        self.assertAlmostEqual(d["p"], 871 / 1126)
        self.assertAlmostEqual(d["s_W"], 750 / 871)
        self.assertAlmostEqual(d["s_L"], 1 / 255)
        self.assertAlmostEqual(d["joint_win_survive"], d["p"] * d["s_W"])
        self.assertAlmostEqual(d["S"], d["S_recon"])
        self.assertAlmostEqual(d["S"], 751 / 1126)
        self.assertAlmostEqual(d["dS_dp"], 750 / 871 - 1 / 255)

    def test_counterfactual_s_at_73(self):
        d = M.rates_from_cells(M.WIN_NO, M.WIN_T40, M.LOSE_NO, M.LOSE_T40)
        cf = M.four_cell_at_p(0.73, d["s_W"], d["s_L"])
        exact = (1 / 255) + 0.73 * (750 / 871 - 1 / 255)
        self.assertAlmostEqual(cf["S"], exact)
        self.assertAlmostEqual(cf["S"], 0.629647, places=5)
        self.assertAlmostEqual(cf["W_and_not_T40"], 0.73 * d["s_W"])
        cells = (
            cf["W_and_not_T40"]
            + cf["W_and_T40"]
            + cf["L_and_not_T40"]
            + cf["L_and_T40"]
        )
        self.assertAlmostEqual(cells, 1.0)


class TestNamedEv(unittest.TestCase):
    def test_lebronner_is_55s_minus_35(self):
        ev = M.ev_sl_zero(0.6296, 20, -35)
        self.assertAlmostEqual(ev["ev_cents"], 55 * 0.6296 - 35)
        self.assertAlmostEqual(ev["ev_cents"], -0.372, places=3)
        self.assertAlmostEqual(ev["breakeven_S"], 35 / 55)

    def test_native_and_true80_at_same_s(self):
        native = M.ev_sl_zero(0.6296, 25, -35)
        true80 = M.ev_sl_zero(0.6296, 20, -40)
        self.assertAlmostEqual(native["ev_cents"], 60 * 0.6296 - 35)
        self.assertAlmostEqual(native["ev_cents"], 2.776, places=3)
        self.assertAlmostEqual(true80["ev_cents"], 60 * 0.6296 - 40)
        self.assertAlmostEqual(true80["ev_cents"], -2.224, places=3)
        self.assertAlmostEqual(native["breakeven_S"], 35 / 60)
        self.assertAlmostEqual(true80["breakeven_S"], 40 / 60)

    def test_build_matches_published_cents(self):
        doc = M.build()
        lb = doc["named_ev"]["lebronner"]
        self.assertAlmostEqual(lb["ev_cents"], -0.37, places=2)
        self.assertAlmostEqual(lb["display_ev_cents"], -0.37, places=2)
        self.assertAlmostEqual(
            doc["named_ev"]["native_75_plus25_minus35_sl0"]["ev_cents"], 2.78, places=2
        )
        self.assertAlmostEqual(
            doc["named_ev"]["true_80_to_40_plus20_minus40_sl0"]["ev_cents"], -2.22, places=2
        )
        self.assertAlmostEqual(doc["named_ev"]["historical_four_cell_native75"], 4.93, places=2)
        self.assertAlmostEqual(
            doc["named_ev"]["cf73_survivor_mix_native75"]["ev_cents"], 2.69, places=2
        )
        self.assertAlmostEqual(doc["named_ev"]["cf73_four_cell_native75"], 2.67, places=2)
        self.assertTrue(doc["research_only"])
        self.assertFalse(doc["live_execution_changed"])
        self.assertEqual(doc["asof_fourcell"]["token_first75"], "NO_ASOF_LIFT")
        self.assertEqual(doc["asof_fourcell"]["token_first80"], "NO_ASOF_LIFT")


class TestProgram(unittest.TestCase):
    def test_spec_only_and_not_authorized(self):
        p = M.build()["program"]
        self.assertEqual(p["status"], "SPEC_ONLY")
        self.assertFalse(p["implementation_authorized"])
        self.assertFalse(p["live_authorized"])
        self.assertFalse(p["iti"]["weights_pnl_optimized"])
        self.assertTrue(p["not_the_failed_scoreboard_asof"])

    def test_mechanism_a_lowers_breakeven_by_1_97pp(self):
        pull = M.ev_sl_zero(0.6296, 23, -37)
        lebr = M.ev_sl_zero(0.6296, 20, -35)
        self.assertAlmostEqual(pull["breakeven_S"], 37 / 60)
        self.assertAlmostEqual(lebr["breakeven_S"], 35 / 55)
        self.assertAlmostEqual(100.0 * (lebr["breakeven_S"] - pull["breakeven_S"]), 1.97, places=2)
        self.assertAlmostEqual(pull["ev_cents"], 23 * 0.6296 - 37 * 0.3704)

    def test_gap_to_breakeven_and_lifts(self):
        p = M.build()["program"]
        self.assertAlmostEqual(p["baseline"]["pp_to_breakeven"], 0.68, places=2)
        want = {1: 0.18, 2: 0.73, 3: 1.28}
        for row in p["delta_S_targets"]:
            self.assertAlmostEqual(row["S"], 0.6296 + row["delta_S_pp"] / 100.0)
            self.assertAlmostEqual(row["ev_cents"], 55.0 * row["S"] - 35.0)
            self.assertAlmostEqual(row["ev_cents"], want[row["delta_S_pp"]], places=2)


class TestWrite(unittest.TestCase):
    def test_report_contains_name_and_banners(self):
        M.write_outputs()
        text = (M.REPORTS / "REPORT.md").read_text()
        self.assertIn("# Lebronner", text)
        self.assertIn("LIVE EXECUTION = FALSE", text)
        self.assertIn("55S − 35", text)
        self.assertIn("NO_ASOF_LIFT", text)
        self.assertIn("LIVE DEPLOYMENT: NOT AUTHORIZED", text)
        self.assertIn("research/lebronner/PROGRAM.md", text)
        raw = (M.REPORTS / "summary.json").read_text()
        self.assertIn('"name": "Lebronner"', raw)
        prog = (M.REPORTS / "PROGRAM.md").read_text()
        self.assertIn("SPEC_ONLY", prog)
        self.assertIn("Ian Tali Index", prog)
        self.assertIn("Mechanism A", prog)
        self.assertIn("viability should not require terminal miscalibration", prog.lower())
        self.assertIn("The new distribution at a 73% terminal rate", prog)
        self.assertIn("62.8588%", prog)
        self.assertIn("26.8941%", prog)
        self.assertIn("mathematically consistent counterfactual", prog)
        tables = (M.REPORTS / "TABLES.md").read_text()
        self.assertIn("p Wilson", tables)
        self.assertIn("FIRST80", tables)
        self.assertIn("asked six", tables.lower())
        self.assertIn("Event-weighted", tables)


class TestTables(unittest.TestCase):
    def test_asked_six_and_universe(self):
        import lebronner_tables as T

        doc = T.build_table_doc(T.load_decomp())
        self.assertEqual(doc["asked_six_FIRST75_n"], 1126)
        self.assertEqual(doc["asked_six_FIRST80_n"], 1182)
        self.assertEqual(doc["universe_totals"]["FIRST75_full_sum_three_sports"], 566 + 1176 + 683)
        self.assertEqual(doc["universe_totals"]["FIRST80_full_sum_three_sports"], 589 + 1230 + 721)
        wnba_q2_75 = next(
            r
            for r in doc["rows"]
            if r["sport"] == "wnba" and r["slice"] == "Q2" and r["rule"] == "FIRST75"
        )
        self.assertEqual(wnba_q2_75["n"], 128)
        self.assertEqual(wnba_q2_75["W"], 105)
        self.assertEqual(wnba_q2_75["p_wilson"], [74.4782, 87.7176])
        self.assertEqual(wnba_q2_75["s_W_wilson"], [78.8563, 91.8887])
        self.assertAlmostEqual(
            doc["distributions"]["FIRST75_asked_six"]["objects"]["p"]["event_weighted_pct"],
            77.3535,
        )


if __name__ == "__main__":
    unittest.main()
