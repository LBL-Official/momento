#!/usr/bin/env python3
"""MOMENTO DYNAMIC RISK ENGINE V3 — offline research runner.

Does not modify PADE V1, DRE V2, FIRST01, Risk, or live execution.
CANDLE PATH ≠ ACTUAL FILL
THEORETICAL EXPOSURE ≠ EXECUTED EXPOSURE
MODELED STATE VALUE ≠ TRADABLE EDGE
"""

from __future__ import annotations

import platform
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))

from dre_v3 import config as C
from dre_v3 import diagnostics as D
from dre_v3 import exposure_grid as G
from dre_v3 import exposure_surface as E
from dre_v3 import frozen_universe as U
from dre_v3 import integrity as I
from dre_v3 import interior_analysis as IA
from dre_v3 import leakage_audit as K
from dre_v3 import local_stability as LS
from dre_v3 import models as M
from dre_v3 import path_distribution as PD
from dre_v3 import splits as S
from dre_v3 import state_panel as SP
from dre_v3 import temporal_stability as TS
from dre_v3.dashboard_export import export
from dre_v3.report import write_reports

PANEL_COLS = [
    "trade_id",
    "event_id",
    "nba_game_id",
    "dataset_split",
    "game_date",
    "game_clock",
    "possession_index",
    "possessions_since_entry",
    "market_age_seconds",
    "period",
    "game_seconds_remaining",
    "score_differential_from_A1",
    "is_A1_team_offense",
    "current_price",
    "deterioration_cents",
    "y_settle_yes",
    "y_rec_ge_10_end",
    "y_rec_ge_30_end",
    "y_det_ge_10_end",
    "y_jump_40",
    "y_jump_40_kind",
    "future_min_5",
    "future_max_5",
    "future_min_10",
    "future_max_10",
    "future_min_end",
    "future_max_end",
    "path_bin_5",
    "path_bin_10",
    "path_bin_end",
    "path_valid_5",
    "path_valid_10",
    "path_valid_end",
    "dd_5",
    "dd_10",
    "dd_end",
    "uu_5",
    "uu_10",
    "uu_end",
    "p_terminal",
    "p_terminal_v3",
    "p_rec10_end",
    "p_rec30_end",
    "p_det10_end",
    "p_jump40",
    "p_settle_M3",
    "target_delta_M3_A",
    "h_N1",
    "h_N2",
    "h_N3",
    "h_N4",
    "h_N2_LINEAR",
    "h_E0",
    "h_E1",
    "h_E2",
    "h_E3",
    "plateau_N1",
    "plateau_N2",
    "plateau_N3",
    "plateau_N4",
    "vmax_N1",
    "curve_sample",
]
PANEL_COLS += [f"p_{b}_{hz}" for hz in C.HORIZONS for b in C.PATH_BINS]
PANEL_COLS += [f"p_path_sum_{hz}" for hz in C.HORIZONS]


def _git_commit() -> str | None:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=C.REPO, stderr=subprocess.DEVNULL)
            .decode()
            .strip()
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _halt(stage: str, detail) -> int:
    C.log(f"HALT at {stage}: {detail}")
    C.OUT.mkdir(parents=True, exist_ok=True)
    C.write_json(C.OUT / "20_run_manifest.json", {"status": "HALT", "stage": stage, "detail": detail, "banner": C.BANNER})
    return 2


def _metrics_map(metrics: list, split: str) -> dict:
    out = {}
    for rec in metrics:
        if rec.get("split") == split:
            out[rec["model"]] = rec
    return out


def _hist(df, col: str, split: str) -> list[dict]:
    xs = df.loc[df["dataset_split"] == split, col].dropna()
    out = []
    for hv in C.H_GRID:
        out.append({"h": hv, "n": int((xs - hv).abs().le(1e-9).sum())})
    return out


def _examples(df, n: int = 8) -> list[dict]:
    picks = []
    for split in ("OOS", "VALIDATION", "TRAIN"):
        xs = df[df["dataset_split"] == split]
        lengths = xs.groupby("trade_id").size().sort_values(ascending=False)
        for tid in lengths.index[: 4 if split == "OOS" else 2]:
            g = xs[xs["trade_id"] == tid].sort_values("possessions_since_entry")
            if g.empty:
                continue
            path = []
            for r in g.itertuples():
                path.append(
                    {
                        "poss": None if r.possessions_since_entry != r.possessions_since_entry else int(r.possessions_since_entry),
                        "pidx": None if r.possession_index != r.possession_index else int(r.possession_index),
                        "clock": None if r.game_clock != r.game_clock else str(r.game_clock),
                        "period": None if r.period != r.period else int(r.period),
                        "price": None if r.current_price != r.current_price else float(r.current_price),
                        "secs": None if r.game_seconds_remaining != r.game_seconds_remaining else float(r.game_seconds_remaining),
                        "diff": None if r.score_differential_from_A1 != r.score_differential_from_A1 else float(r.score_differential_from_A1),
                        "p_terminal": None if r.p_terminal != r.p_terminal else float(r.p_terminal),
                        "path_bin_end": None if r.path_bin_end != r.path_bin_end else str(r.path_bin_end),
                        "h_N1": None if r.h_N1 != r.h_N1 else float(r.h_N1),
                        "h_N2": None if r.h_N2 != r.h_N2 else float(r.h_N2),
                        "h_N3": None if r.h_N3 != r.h_N3 else float(r.h_N3),
                        "h_N4": None if r.h_N4 != r.h_N4 else float(r.h_N4),
                        "h_E2": None if r.h_E2 != r.h_E2 else float(r.h_E2),
                        "h_E3": None if r.h_E3 != r.h_E3 else float(r.h_E3),
                    }
                )
            picks.append(
                {
                    "trade_id": str(tid),
                    "event_id": str(g["event_id"].iloc[0]),
                    "nba_game_id": None if g["nba_game_id"].isna().all() else str(g["nba_game_id"].iloc[0]),
                    "split": split,
                    "n": int(len(g)),
                    "path": path,
                    "label": "THEORETICAL RETAINED EXPOSURE — NOT EXECUTED",
                }
            )
            if len(picks) >= n:
                return picks
    return picks


def _project(df, cols):
    keep = [c for c in cols if c in df.columns]
    return df[keep].copy()


def main() -> int:
    t0 = time.time()
    C.log(C.BANNER)
    C.OUT.mkdir(parents=True, exist_ok=True)
    C.DASH_PUBLIC.mkdir(parents=True, exist_ok=True)

    C.log("Gate A — PADE integrity")
    gate_a = I.gate_a_pade()
    C.write_json(C.OUT / "02_pade_integrity.json", gate_a)
    if gate_a["status"] != "PASS":
        return _halt("A", gate_a)

    C.log("Gate B — DRE V2 integrity")
    gate_b = I.gate_b_v2()
    C.write_json(C.OUT / "03_dre_v2_integrity.json", gate_b)
    if gate_b["status"] != "PASS":
        return _halt("B", gate_b)

    C.log("Gate C — frozen FIRST-80")
    gate_c = U.gate_c()
    C.write_json(C.OUT / "01_frozen_universe_validation.json", gate_c)
    if gate_c["status"] != "PASS":
        return _halt("C", gate_c)

    C.log("Build state panel")
    df = SP.build_panel()
    counts = SP.panel_counts(df)
    if counts["rows"] != 139966:
        return _halt("panel_rows", counts)
    leak = K.audit()
    split_audit = S.audit_splits(df)
    C.write_json(C.OUT / "16_leakage_audit.json", leak)
    C.write_json(C.OUT / "17_split_audit.json", split_audit)
    if leak["market_lookahead"]["status"] != "PASS":
        return _halt("market_lookahead", leak)
    if leak["game_lookahead"]["status"] != "PASS":
        return _halt("game_lookahead", leak)
    if leak["label_leakage"]["status"] != "PASS":
        return _halt("label_leakage", leak)
    if split_audit["status"] != "PASS":
        return _halt("split", split_audit)

    C.log("Fit predictive models (TRAIN only)")
    df, fitted, metrics = M.fit_predictive(df)

    # path-sum halt
    for hz in C.HORIZONS:
        s = df[f"p_path_sum_{hz}"]
        finite = s.notna()
        if finite.any() and float((s.loc[finite] - 1.0).abs().max()) > 1e-6:
            return _halt("path_norm", {"horizon": hz, "max_abs": float((s.loc[finite] - 1.0).abs().max())})

    C.log("Select exposure objectives on VALIDATION")
    df, selected = G.select_and_apply(df)
    curves = G.objective_curves(df, selected)

    path_summ = PD.summarize(df)
    if path_summ["status"] != "PASS":
        return _halt("path_distribution", path_summ)

    C.log("Surfaces and stability")
    surfaces = []
    for fam in ("N1", "N2", "N3", "N4", "E2", "E3"):
        surfaces.extend(E.surface_price_clock(df, fam))
    contrast = E.same_price_contrast(df)
    interior = IA.analyze(df)
    local = LS.analyze(df, fitted, selected)
    temporal = TS.analyze(df)
    pred_oos = _metrics_map(metrics, "OOS")
    pred_val = _metrics_map(metrics, "VALIDATION")
    pred_tr = _metrics_map(metrics, "TRAIN")
    questions = D.compare_families(interior, temporal, local, contrast)

    gates = {
        "A": {"status": gate_a["status"]},
        "B": {"status": gate_b["status"]},
        "C": {"status": gate_c["status"]},
        "market": leak["market_lookahead"],
        "game": leak["game_lookahead"],
        "label": leak["label_leakage"],
        "split": split_audit,
        "path_norm": {"status": path_summ["status"], "fails": path_summ.get("fails")},
    }
    verdict = D.overall_verdict(gates, questions, interior)

    oos_results = {
        "interior": {f: interior.get(f, {}).get("OOS") for f in ("N1", "N2", "N3", "N4", "N2_LINEAR", "E2", "E3")},
        "stability": {f: interior.get(f, {}).get("stability") for f in ("N1", "N2", "N3", "N4")},
        "selected": {k: {kk: vv for kk, vv in selected[k].items() if kk != "grid"} for k in ("N1", "N2", "N3", "N4")},
        "questions": questions,
        "headline": verdict["HEADLINE"],
        "label": "THEORETICAL RETAINED EXPOSURE — NOT EXECUTED",
    }

    C.log("Write artifacts")
    C.write_parquet_df(C.OUT / "04_state_panel.parquet", _project(df, PANEL_COLS))
    path_cols = [
        "trade_id",
        "possession_index",
        "dataset_split",
        "current_price",
        "future_min_5",
        "future_max_5",
        "future_min_10",
        "future_max_10",
        "future_min_end",
        "future_max_end",
        "path_bin_5",
        "path_bin_10",
        "path_bin_end",
        "path_valid_5",
        "path_valid_10",
        "path_valid_end",
        "dd_5",
        "dd_10",
        "dd_end",
        "uu_5",
        "uu_10",
        "uu_end",
        "y_rec_ge_30_5",
        "y_rec_ge_30_10",
        "y_rec_ge_30_end",
        "y_jump_40",
        "y_jump_40_kind",
    ]
    C.write_parquet_df(C.OUT / "05_forward_path_labels.parquet", _project(df, path_cols))

    dist_rows = []
    for hz, splits in path_summ["empirical"].items():
        for split, rec in splits.items():
            for b, rate in (rec.get("rates") or {}).items():
                dist_rows.append({"kind": "empirical", "horizon": hz, "split": split, "bin": b, "rate": rate, "n": rec.get("n")})
    C.write_parquet_df(C.OUT / "06_path_distribution_metrics.parquet", pd.DataFrame(dist_rows))
    C.write_json(C.OUT / "06_path_distribution_metrics.json", path_summ)

    met_df = pd.DataFrame(metrics)
    (C.OUT / "07_terminal_models").mkdir(parents=True, exist_ok=True)
    (C.OUT / "08_recovery_models").mkdir(parents=True, exist_ok=True)
    (C.OUT / "09_downside_models").mkdir(parents=True, exist_ok=True)
    (C.OUT / "10_calibration").mkdir(parents=True, exist_ok=True)
    C.write_json(C.OUT / "07_terminal_models" / "metrics.json", [r for r in metrics if r.get("model") == "p_terminal"])
    C.write_json(C.OUT / "08_recovery_models" / "metrics.json", [r for r in metrics if str(r.get("model", "")).startswith("p_rec") or str(r.get("model", "")).startswith("path_")])
    C.write_json(C.OUT / "09_downside_models" / "metrics.json", [r for r in metrics if str(r.get("model", "")).startswith("p_det") or r.get("model") == "p_jump40"])
    C.write_json(
        C.OUT / "10_calibration" / "ece.json",
        [{"model": r.get("model"), "split": r.get("split"), "ece": r.get("ece"), "n": r.get("n")} for r in metrics if "ece" in r],
    )
    C.write_parquet_df(C.OUT / "08_models" / "model_metrics.parquet", met_df)

    exp_cols = [
        "trade_id",
        "possession_index",
        "dataset_split",
        "current_price",
        "p_terminal",
        "h_N1",
        "h_N2",
        "h_N3",
        "h_N4",
        "h_N2_LINEAR",
        "h_E0",
        "h_E1",
        "h_E2",
        "h_E3",
        "plateau_N1",
        "plateau_N2",
        "plateau_N3",
        "plateau_N4",
        "vmax_N1",
        "vmax_N2",
        "vmax_N3",
        "vmax_N4",
        "curve_sample",
    ]
    C.write_parquet_df(C.OUT / "11_exposure_objective_values.parquet", _project(df, exp_cols))
    C.write_parquet_df(C.OUT / "12_exposure_surface.parquet", pd.DataFrame(surfaces))
    C.write_json(C.OUT / "13_interior_solution_analysis.json", interior)
    C.write_json(C.OUT / "14_local_stability_analysis.json", local)
    C.write_json(C.OUT / "15_temporal_stability_analysis.json", temporal)
    C.write_json(C.OUT / "18_objective_family_comparison.json", {"selected": selected, "questions": questions, "interior": interior})
    C.write_json(C.OUT / "19_oos_results.json", oos_results)
    C.write_json(C.OUT / "objective_curves.json", curves)

    hist = {f: {s: _hist(df, f"h_{f}", s) for s in ("TRAIN", "VALIDATION", "OOS")} for f in ("N1", "N2", "N3", "N4", "E2", "E3")}
    examples = _examples(df)

    ctx = {
        "gates": gates,
        "counts": counts,
        "verdict": verdict,
        "questions": questions,
        "interior": interior,
        "selected": selected,
        "pred_oos": pred_oos,
        "pred_val": pred_val,
        "pred_train": pred_tr,
        "local": local,
        "temporal": temporal,
        "path": path_summ,
        "curves": curves,
        "contrast": contrast,
        "surfaces": surfaces,
    }
    write_reports(ctx)

    dash = {
        "program": C.PROGRAM,
        "banner": C.BANNER,
        "created_utc": C.utc_now(),
        "schema_version": C.SCHEMA_VERSION,
        "research_date": C.RESEARCH_DATE,
        "live_execution_changed": C.LIVE_EXECUTION_CHANGED,
        "verdict": verdict,
        "gates": gates,
        "counts": counts,
        "questions": questions,
        "selected": {k: {kk: vv for kk, vv in selected[k].items() if kk != "grid"} for k in ("N1", "N2", "N3", "N4")},
        "selected_grids": {k: selected[k].get("grid") for k in ("N1", "N2", "N3", "N4")},
        "accounting": selected["accounting"],
        "interior": interior,
        "local": local,
        "temporal": temporal,
        "path": path_summ,
        "models": metrics,
        "surfaces": surfaces,
        "contrast": contrast,
        "curves": curves,
        "histograms": hist,
        "oos_results": oos_results,
        "examples": examples,
        "layers": {
            "OBSERVED_DATA": "empirical candle-path bins and settlement labels",
            "MODELED_PROBABILITIES": "TRAIN-fit logistic / multinomial scores",
            "THEORETICAL_EXPOSURE": "grid-argmax h* under nonlinear objectives — not executed",
        },
        "feature_cols": list(C.FEATURE_COLS),
        "h_grid": list(C.H_GRID),
    }
    export(dash)

    untouched_pade = I.assert_untouched(gate_a)
    untouched_v2 = I.assert_untouched(gate_b)
    if not untouched_pade["ok"] or not untouched_v2["ok"]:
        return _halt("frozen_overwrite", {"pade": untouched_pade, "v2": untouched_v2})

    elapsed = time.time() - t0
    manifest = {
        "status": "OK",
        "program": C.PROGRAM,
        "schema_version": C.SCHEMA_VERSION,
        "created_utc": C.utc_now(),
        "elapsed_sec": elapsed,
        "git_commit": _git_commit(),
        "python": sys.version,
        "platform": platform.platform(),
        "live_execution_changed": False,
        "banner": C.BANNER,
        "source_paths": {"pade": str(C.PADE_OUT), "dre_v2": str(C.V2_OUT), "out": str(C.OUT)},
        "row_counts": counts,
        "split_counts": counts["splits"],
        "feature_version": "dre_v3_asof_v1",
        "label_version": "dre_v3_pathbins_v1",
        "gates": {k: v.get("status") for k, v in gates.items()},
        "headline": verdict["HEADLINE"],
        "selected": {k: {kk: vv for kk, vv in selected[k].items() if kk != "grid"} for k in ("N1", "N2", "N3", "N4")},
        "pade_untouched": untouched_pade,
        "dre_v2_untouched": untouched_v2,
        "output_hashes": {
            "04_state_panel.parquet": C.sha256_prefix(C.OUT / "04_state_panel.parquet"),
            "11_exposure_objective_values.parquet": C.sha256_prefix(C.OUT / "11_exposure_objective_values.parquet"),
            "19_oos_results.json": C.sha256_prefix(C.OUT / "19_oos_results.json"),
        },
    }
    C.write_json(C.OUT / "20_run_manifest.json", manifest)
    C.log(f"done in {elapsed:.1f}s headline={verdict['HEADLINE']}")
    print(verdict["HEADLINE"])
    print("LIVE DEPLOYMENT: NOT AUTHORIZED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as e:
        C.log(f"HALT RuntimeError: {e}")
        C.OUT.mkdir(parents=True, exist_ok=True)
        C.write_json(C.OUT / "20_run_manifest.json", {"status": "HALT", "error": str(e), "banner": C.BANNER})
        raise
