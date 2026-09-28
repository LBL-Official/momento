#!/usr/bin/env python3
"""MOMENTO DYNAMIC RISK ENGINE V2 — offline research runner.

Does not modify PADE V1, FIRST01, Risk, or live execution.
CANDLE PATH ≠ ACTUAL FILL
THEORETICAL TARGET DELTA ≠ EXECUTED DELTA
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))

from dre_v2 import config as C
from dre_v2 import diagnostics as D
from dre_v2 import exposure_surface as E
from dre_v2 import feature_builder as F
from dre_v2 import frozen_universe as U
from dre_v2 import labels as L
from dre_v2 import leakage_audit as K
from dre_v2 import models as M
from dre_v2 import pade_loader as P
from dre_v2 import regimes as R
from dre_v2 import splits as S
from dre_v2 import state_panel as SP
from dre_v2 import target_delta as T
from dre_v2.dashboard_export import export_dashboard
from dre_v2.report import write_reports

STATE_COLS = [
    "trade_id",
    "event_id",
    "nba_game_id",
    "dataset_split",
    "game_date",
    "entry_timestamp",
    "real_time_timestamp",
    "game_clock",
    "possession_index",
    "possessions_since_entry",
    "market_age_seconds",
    "alignment_confidence",
    "period",
    "period_type",
    "elapsed_game_seconds",
    "game_seconds_remaining",
    "score_differential_from_A1",
    "is_A1_team_offense",
    "current_price",
    "current_price_e4",
    "current_price_cents",
    "entry_price_e4",
    "deterioration_cents",
    "deterioration_e4",
    "spread_e4",
    "unique_market_observations_since_entry",
    "market_price_change_1_observation",
    "market_price_change_1_valid",
    "recovery_from_max_drawdown",
    "distance_from_entry",
    "distance_from_prior_peak",
    "velocity_1_possession",
    "velocity_1_possession_valid",
    "v_3",
    "v_5",
    "a_short",
    "estimated_remaining_possessions",
    "remaining_possessions_confidence",
    "y_settle_yes",
    "y_rec_ge_10_k5",
    "y_rec_ge_10_end",
    "y_det_ge_10_k5",
    "y_det_ge_10_end",
    "y_min_le_50_k5",
    "y_jump_40",
    "y_min_le_40_k5",
]

PRED_COLS = STATE_COLS + [
    "p_settle_B0",
    "p_settle_M3",
    "p_settle_M5",
    "p_rec10_k5_B0",
    "p_rec10_k5_M3",
    "p_det10_end_B0",
    "p_det10_end_M3",
    "terminal_probability_edge_B0",
    "terminal_probability_edge_M3",
    "ev_hold_mtm_cents_B0",
    "ev_hold_mtm_cents_M3",
    "ev_hold_from_entry_cents_M3",
    "target_delta_B0_A",
    "target_delta_M3_A",
    "target_delta_M3_B",
    "target_delta_M3_C",
    "target_delta_M3_D",
    "regime_price",
    "regime_period",
    "regime_score",
    "regime_cluster",
]


def _project(rows, cols):
    return [{k: r.get(k) for k in cols} for r in rows]


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
    C.write_json(C.OUT / "run_manifest.json", {"status": "HALT", "stage": stage, "detail": detail})
    return 2


def scientific_verdict(ctx: dict) -> dict:
    gates = ctx["gates"]
    hard = ["A", "B", "C", "D", "E"]
    if any(gates[g]["status"] != "PASS" for g in hard):
        arch = "FAIL"
    else:
        inc = ctx["incremental_oos"]
        settle_d = inc.get("M3_y_settle_yes_d_auc")
        rec_d = inc.get("M5_y_rec_ge_10_k5_d_auc")
        asym = ctx["asymmetry"]["asymmetry_exists_oos"]
        if settle_d is not None and settle_d >= 0.008 and asym:
            arch = "PARTIAL"
        elif (settle_d is not None and settle_d >= 0.005) or asym:
            arch = "PARTIAL"
        else:
            arch = "INCONCLUSIVE"

    sat = ctx["control_oos"]
    price_only = "PASS" if (sat.get("B0_auc") or 0) >= 0.97 else "PARTIAL"

    return {
        "FROZEN_UNIVERSE": gates["A"]["status"],
        "PADE_INPUT_INTEGRITY": gates["B"]["status"],
        "MARKET_LOOKAHEAD": gates["C"]["status"],
        "GAME_LOOKAHEAD": gates["D"]["status"],
        "SPLIT_ISOLATION": gates["E"]["status"],
        "UNRESOLVED_PRESERVATION": gates["F"]["status"],
        "MODEL_BASELINE": gates["G"]["status"],
        "OOS_DISCIPLINE": gates["H"]["status"],
        "EXECUTION_CLAIMS": gates["I"]["status"],
        "SATURATED_40_IN_5_CONTROL": price_only,
        "INCREMENTAL_STATE_VALUE": arch,
        "EXPOSURE_ASYMMETRY": "PASS" if ctx["asymmetry"]["asymmetry_exists_oos"] else "INCONCLUSIVE",
        "TARGET_DELTA_STABILITY": ctx["delta_stability_grade"],
        "REMAINING_POSSESSIONS": ctx["rem_ablation"]["settlement_oos_verdict"],
        "EXECUTION_EVIDENCE": "UNOBSERVED",
        "LIVE_DEPLOYMENT": "NOT AUTHORIZED",
        "ARCHITECTURE": arch,
    }


def main() -> int:
    t0 = time.time()
    C.OUT.mkdir(parents=True, exist_ok=True)
    for name in (
        "01_input_manifest",
        "02_frozen_universe",
        "03_state_panel",
        "04_feature_dictionary",
        "05_leakage_audit",
        "06_forward_labels",
        "07_model_datasets",
        "08_models",
        "09_predictions",
        "10_distribution_surfaces",
        "11_exposure_surfaces",
        "12_regime_analysis",
        "13_oos_results",
        "14_diagnostics",
        "15_reports",
        "16_dashboard",
    ):
        (C.OUT / name).mkdir(parents=True, exist_ok=True)

    C.log(f"{C.PROGRAM} start schema={C.SCHEMA_VERSION}")
    C.log(C.BANNER)

    # STAGE 1 — inspection
    C.log("STAGE 1 repository / input inspection")
    integrity = P.pade_integrity()
    C.write_json(C.OUT / "01_input_manifest" / "pade_integrity.json", {k: v for k, v in integrity.items() if k != "files"} | {"files": integrity["files"]})
    if integrity["status"] != "PASS":
        return _halt("STAGE1_PADE_INTEGRITY", integrity)

    # STAGE 2 — frozen universe
    C.log("STAGE 2 frozen universe")
    gate_a = U.gate_a()
    trades = gate_a.pop("trades")
    C.write_json(
        C.OUT / "02_frozen_universe" / "gate_a.json",
        {k: v for k, v in gate_a.items() if k != "reproduce"} | {"reproduce": gate_a.get("reproduce")},
    )
    if not gate_a["ok"]:
        return _halt("STAGE2_FROZEN_UNIVERSE", gate_a)
    C.log(f"GATE A PASS n={gate_a['observed'].get('n')} surv={gate_a['observed'].get('survivors')} stops={gate_a['observed'].get('stops')}")

    # STAGE 3 — load PADE
    C.log("STAGE 3 load PADE panel")
    pade_panel = P.load_panel()
    if not pade_panel:
        return _halt("STAGE3_EMPTY_PANEL", "PADE panel empty")
    C.log(f"PADE panel rows={len(pade_panel)}")

    # STAGE 4 — state panel
    C.log("STAGE 4 construct DRE state panel")
    panel = SP.build_state_panel(pade_panel)
    counts = SP.panel_counts(panel)
    C.write_parquet(C.OUT / "03_state_panel" / "dre_state_panel.parquet", _project(panel, STATE_COLS))
    C.write_json(C.OUT / "03_state_panel" / "counts.json", counts)
    C.log(f"state panel rows={counts['panel_rows']} trades={counts['panel_trades']}")

    # STAGE 5 — leakage
    C.log("STAGE 5 leakage audit")
    leak = K.audit(panel)
    C.write_json(
        C.OUT / "05_leakage_audit" / "LEAKAGE_AUDIT.json",
        {k: v for k, v in leak.items() if k != "rows"} | {"rows": leak["rows"]},
    )
    if leak["gate_c"] != "PASS" or leak["gate_d"] != "PASS":
        return _halt("STAGE5_LEAKAGE", {"C": leak["gate_c"], "D": leak["gate_d"], "illegal": leak["illegal_features"]})

    feat_dict = F.feature_dictionary()
    C.write_json(C.OUT / "04_feature_dictionary" / "feature_dictionary.json", feat_dict)
    C.write_json(C.OUT / "06_forward_labels" / "label_catalog.json", L.catalog())
    spot = L.spotcheck(panel)
    C.write_json(C.OUT / "14_diagnostics" / "label_spotcheck.json", spot)

    # STAGE 6 implied by spotcheck
    C.log("STAGE 6 label spotcheck")
    if any(s.get("spotcheck_min5_consistent") is False for s in spot):
        C.log("WARNING label spotcheck mismatch (PADE labels retained; see diagnostics)")

    split_rows, split_sum = S.split_manifest(panel)
    C.write_json(C.OUT / "02_frozen_universe" / "split_manifest.json", split_rows)
    C.write_json(C.OUT / "02_frozen_universe" / "split_isolation.json", split_sum)
    if split_sum["status"] != "PASS":
        return _halt("STAGE_SPLIT_ISOLATION", split_sum)

    unresolved = D.unresolved_report(trades, panel)
    C.write_json(C.OUT / "14_diagnostics" / "unresolved.json", unresolved)

    usable = [
        r
        for r in panel
        if r.get("alignment_usable") and r.get("current_price") is not None
    ]
    C.write_json(
        C.OUT / "07_model_datasets" / "dataset_counts.json",
        {
            "panel": counts,
            "usable_high_medium": len(usable),
            "usable_by_split": {
                s: len([r for r in usable if r["dataset_split"] == s]) for s in ("TRAIN", "VALIDATION", "OOS")
            },
            "alignment_mix": D.alignment_mix(panel),
            "note": "Models use HIGH+MEDIUM alignment only. LOW/UNRESOLVED rows are retained on the panel.",
        },
    )

    # STAGE 7/8 — models
    C.log("STAGE 7–8 nested models B0–M5 + remaining-possessions ablation")
    model_rows, fitted, excl = M.run_nested(usable)
    if excl.get("status") != "PASS":
        return _halt("STAGE_MODELS", excl)
    C.write_parquet(C.OUT / "08_models" / "model_metrics.parquet", model_rows)
    C.write_json(
        C.OUT / "08_models" / "hyperparameters.json",
        {
            "estimator": "LogisticRegression",
            "C": C.LOGIT_C,
            "max_iter": C.LOGIT_MAX_ITER,
            "class_weight": "balanced",
            "solver": "lbfgs",
            "scaler": "StandardScaler",
            "random_seed": C.RANDOM_SEED,
            "tuned_on_oos": False,
            "families": {k: {"features": v, "layer": F.FAMILY_LAYER[k]} for k, v in F.FAMILIES.items()},
            "targets": [{"name": a, "label": b} for a, b in F.ALL_TARGETS],
        },
    )
    C.write_json(C.OUT / "07_model_datasets" / "complete_case_exclusions.json", excl["rows"])
    incremental = M.incremental(model_rows)
    C.write_json(C.OUT / "08_models" / "incremental_vs_B0.json", incremental)

    # STAGE 9 — probabilities, exposure, target delta
    C.log("STAGE 9 exposure surfaces and theoretical target delta")
    E.attach_probabilities(usable, fitted)
    selected = E.select_hyperparams(usable, "M3")
    E.apply_target_delta(usable, selected, "M3")
    E.apply_target_delta(usable, selected, "B0")
    R.assign_buckets(usable)
    clusters = R.fit_clusters(usable, k=5)
    surfaces = E.exposure_aggregates(usable, "M3")
    surfaces_b0 = E.exposure_aggregates(usable, "B0")
    oos_policy = E.oos_policy_score(usable, selected, "M3")
    stability = T.stability(usable, "M3")
    rem_ablation = D.remaining_ablation(model_rows)
    asym = D.asymmetry(usable)
    regimes = R.regime_table(usable)

    C.write_json(C.OUT / "11_exposure_surfaces" / "hyperparameters_selected.json", selected)
    C.write_json(C.OUT / "11_exposure_surfaces" / "exposure_grid_M3.json", surfaces)
    C.write_json(C.OUT / "11_exposure_surfaces" / "exposure_grid_B0.json", surfaces_b0)
    C.write_json(C.OUT / "11_exposure_surfaces" / "oos_policy_score.json", oos_policy)
    C.write_json(C.OUT / "11_exposure_surfaces" / "target_delta_stability.json", stability)
    C.write_json(C.OUT / "10_distribution_surfaces" / "empirical_and_model_surfaces.json", surfaces)
    C.write_json(C.OUT / "12_regime_analysis" / "interpretable_regimes.json", regimes)
    C.write_json(C.OUT / "12_regime_analysis" / "clusters.json", clusters)
    C.write_json(C.OUT / "13_oos_results" / "incremental_vs_B0.json", [x for x in incremental if x["split"] == "OOS"])
    C.write_json(C.OUT / "13_oos_results" / "remaining_possessions_ablation.json", rem_ablation)
    C.write_json(C.OUT / "13_oos_results" / "asymmetry.json", {k: v for k, v in asym.items() if k != "contrasts"})
    C.write_json(C.OUT / "12_regime_analysis" / "EXPOSURE_ASYMMETRY.json", asym)

    C.write_parquet(C.OUT / "09_predictions" / "state_predictions.parquet", _project(usable, PRED_COLS))

    def d_auc(fam, target):
        row = next((x for x in incremental if x["family"] == fam and x["target"] == target and x["split"] == "OOS"), None)
        return None if row is None else row.get("d_auc")

    incremental_oos = {
        "M3_y_settle_yes_d_auc": d_auc("M3", "y_settle_yes"),
        "M5_y_settle_yes_d_auc": d_auc("M5", "y_settle_yes"),
        "M3_y_rec_ge_10_k5_d_auc": d_auc("M3", "y_rec_ge_10_k5"),
        "M5_y_rec_ge_10_k5_d_auc": d_auc("M5", "y_rec_ge_10_k5"),
        "M3_y_det_ge_10_end_d_auc": d_auc("M3", "y_det_ge_10_end"),
        "B2_y_rec_ge_10_k5_d_auc": d_auc("B2", "y_rec_ge_10_k5"),
        "M3_NO_REM_y_settle_yes_d_auc": d_auc("M3_NO_REM", "y_settle_yes"),
    }
    control_oos = {
        "B0_auc": M.pick(model_rows, "B0", "y_min_le_40_k5", "OOS", "auc"),
        "M3_auc": M.pick(model_rows, "M3", "y_min_le_40_k5", "OOS", "auc"),
        "B0_brier": M.pick(model_rows, "B0", "y_min_le_40_k5", "OOS", "brier"),
    }

    # Target-delta stability grade: OOS mean_h vs VAL mean_h for family A
    sta = stability.get("A") or {}
    oos_h = (sta.get("OOS") or {}).get("mean_h")
    val_h = (sta.get("VALIDATION") or {}).get("mean_h")
    if oos_h is None or val_h is None:
        delta_grade = "INCONCLUSIVE"
    elif abs(oos_h - val_h) <= 0.08:
        delta_grade = "PARTIAL"
    else:
        delta_grade = "WARNING"

    pade_after = P.assert_pade_untouched(integrity)
    if not pade_after["ok"]:
        return _halt("PADE_MUTATION", pade_after)

    gates = {
        "A": {"status": "PASS", "detail": gate_a["observed"]},
        "B": {"status": "PASS", "detail": {"row_counts": integrity["row_counts"], "pade_untouched": True}},
        "C": {"status": leak["gate_c"], "detail": {"market_lookahead": leak["market_lookahead_count"]}},
        "D": {"status": leak["gate_d"], "detail": {"game_lookahead": leak["game_lookahead_count"]}},
        "E": {"status": split_sum["status"], "detail": {k: split_sum[k] for k in ("train_games", "validation_games", "oos_games")}},
        "F": {"status": unresolved["status"], "detail": {"universe": unresolved["universe"], "panel": unresolved["panel_eligible_trades"], "unresolved": unresolved["unresolved_n"]}},
        "G": {"status": "PASS", "detail": "every advanced family compared to B0"},
        "H": {"status": "PASS", "detail": "lambdas selected on VALIDATION only; logit C frozen a priori"},
        "I": {"status": "PASS", "detail": C.BANNER},
    }

    ctx = {
        "gates": gates,
        "incremental_oos": incremental_oos,
        "control_oos": control_oos,
        "asymmetry": asym,
        "rem_ablation": rem_ablation,
        "delta_stability_grade": delta_grade,
    }
    verdict = scientific_verdict(ctx)

    # Empirical distribution surfaces (not models)
    emp_surfaces = []
    for split in ("TRAIN", "VALIDATION", "OOS"):
        xs = [r for r in usable if r["dataset_split"] == split]
        for lo in range(5, 85, 5):
            b = [r for r in xs if r.get("current_price") is not None and lo <= r["current_price"] < lo + 5]
            if not b:
                continue
            emp_surfaces.append(
                {
                    "split": split,
                    "price_lo": lo,
                    "price_hi": lo + 5,
                    "n": len(b),
                    "p_settle": D._mean(b, "y_settle_yes"),
                    "p_rec10_k5": D._mean(b, "y_rec_ge_10_k5"),
                    "p_det10_end": D._mean(b, "y_det_ge_10_end"),
                    "p_min50_k5": D._mean(b, "y_min_le_50_k5"),
                    "p_jump40": D._mean(b, "y_jump_40"),
                    "p_min40_k5": D._mean(b, "y_min_le_40_k5"),
                }
            )
    C.write_json(C.OUT / "10_distribution_surfaces" / "empirical_by_price.json", emp_surfaces)

    examples = _examples(usable)
    dash = export_dashboard(
        {
            "program": C.PROGRAM,
            "banner": C.BANNER,
            "created_utc": C.utc_now(),
            "schema_version": C.SCHEMA_VERSION,
            "verdict": verdict,
            "gates": gates,
            "counts": {
                **counts,
                "universe": len(trades),
                "unresolved": unresolved["unresolved_n"],
                "usable": len(usable),
            },
            "models": model_rows,
            "incremental_oos": incremental_oos,
            "surfaces": surfaces,
            "emp_surfaces": emp_surfaces,
            "asymmetry": asym,
            "regimes": regimes[:80],
            "clusters": clusters,
            "selected": selected,
            "oos_policy": oos_policy,
            "stability": stability,
            "rem_ablation": rem_ablation,
            "unresolved": unresolved,
            "examples": examples,
            "leakage": leak["rows"],
            "corner_note": T.corner_note(),
            "spotcheck": spot,
        }
    )

    write_reports(
        {
            "verdict": verdict,
            "gates": gates,
            "counts": counts,
            "universe": len(trades),
            "unresolved": unresolved,
            "model_rows": model_rows,
            "incremental": incremental,
            "incremental_oos": incremental_oos,
            "control_oos": control_oos,
            "surfaces": surfaces,
            "asymmetry": asym,
            "regimes": regimes,
            "clusters": clusters,
            "selected": selected,
            "oos_policy": oos_policy,
            "stability": stability,
            "rem_ablation": rem_ablation,
            "spotcheck": spot,
            "leak": leak,
            "split_sum": split_sum,
            "integrity": integrity,
            "elapsed_s": time.time() - t0,
            "git": _git_commit(),
        }
    )

    env = {
        "timestamp": C.utc_now(),
        "git_commit": _git_commit(),
        "python": sys.version,
        "platform": platform.platform(),
        "sklearn": M.HAS_SKLEARN,
        "random_seed": C.RANDOM_SEED,
        "input_paths": {"pade": str(C.PADE_OUT)},
        "pade_hashes": {f["name"]: f.get("sha256_16") for f in integrity["files"]},
        "row_counts": counts,
        "universe": gate_a["observed"],
        "split": split_sum,
        "feature_families": {k: v for k, v in F.FAMILIES.items()},
        "model_hyperparameters": {"C": C.LOGIT_C, "seed": C.RANDOM_SEED, "tuned_on_oos": False},
        "objective_hyperparameters": selected,
        "output_path": str(C.OUT),
        "elapsed_s": time.time() - t0,
        "verdict": verdict,
        "gates": {k: v["status"] for k, v in gates.items()},
        "banner": C.BANNER,
        "pade_untouched": pade_after,
    }
    C.write_json(C.OUT / "run_manifest.json", env)
    C.write_json(C.OUT / "summary.json", {"verdict": verdict, "gates": {k: v["status"] for k, v in gates.items()}, "counts": counts, "banner": C.BANNER})
    C.write_json(C.OUT / "16_dashboard" / "dashboard.json", dash)

    C.log(f"done in {time.time() - t0:.1f}s architecture={verdict['ARCHITECTURE']}")
    C.log("LIVE DEPLOYMENT: NOT AUTHORIZED")
    return 0


def _examples(usable: list[dict], n: int = 10) -> list[dict]:
    by = {}
    for r in usable:
        by.setdefault(r["trade_id"], []).append(r)
    picks = []
    for split in ("TRAIN", "VALIDATION", "OOS"):
        tids = [t for t, rs in by.items() if rs[0].get("dataset_split") == split]
        tids.sort()
        if not tids:
            continue
        step = max(1, len(tids) // 4)
        picks.extend(tids[::step][:4])
    out = []
    for tid in picks[:n]:
        rs = sorted(by[tid], key=lambda x: x.get("possessions_since_entry") or 0)
        path = []
        for r in rs[:: max(1, len(rs) // 80)][:80]:
            path.append(
                {
                    "poss": r.get("possessions_since_entry"),
                    "pidx": r.get("possession_index"),
                    "real": r.get("real_time_timestamp"),
                    "clock": r.get("game_clock"),
                    "period": r.get("period"),
                    "price": r.get("current_price"),
                    "age": r.get("market_age_seconds"),
                    "conf": r.get("alignment_confidence"),
                    "det": r.get("deterioration_absolute"),
                    "dd": r.get("max_deterioration_since_entry"),
                    "rec": r.get("recovery_from_max_drawdown"),
                    "diff": r.get("score_differential_from_A1"),
                    "off": r.get("is_A1_team_offense"),
                    "p_yes": r.get("p_settle_M3"),
                    "p_rec": r.get("p_rec10_k5_M3"),
                    "p_down": r.get("p_det10_end_M3"),
                    "hA": r.get("target_delta_M3_A"),
                    "hD": r.get("target_delta_M3_D"),
                    "edge": r.get("terminal_probability_edge_M3"),
                    "uniq": r.get("unique_market_observations_since_entry"),
                }
            )
        out.append(
            {
                "trade_id": tid,
                "event_id": rs[0].get("event_id"),
                "nba_game_id": rs[0].get("nba_game_id"),
                "split": rs[0].get("dataset_split"),
                "n": len(rs),
                "path": path,
            }
        )
    return out


if __name__ == "__main__":
    raise SystemExit(main())
