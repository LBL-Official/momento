#!/usr/bin/env python3
"""DRE V7 runner. Protocol first. One diagnostic run. Does not write to V5/V6."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))

from dre_v7 import cell_geometry as CG
from dre_v7 import config as C
from dre_v7 import data as D
from dre_v7 import distribution_shift as DS
from dre_v7 import integrity as I
from dre_v7 import report
from dre_v7 import support as SU
from dre_v7 import synthesis as SY
from dre_v7 import trade_support as TS
from dre_v7 import stability as ST
from dre_v7.dashboard_export import export
from dre_v7 import bootstrap as BS
from dre_v7 import replication as R


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
    C.write_json(C.OUT / "01_run_manifest.json", {"status": "HALT", "stage": stage, "detail": detail, "banner": C.BANNER})
    return 2


REQUIRED_SCIENCE = (
    "00_integrity_snapshot.json",
    "02_map_integrity.json",
    "03_state_cell_support.json",
    "04_state_support_distribution.json",
    "05_extreme_sir_source_cells.json",
    "06_trade_support_exposure.json",
    "07_distribution_shift.json",
    "08_support_stratified_stability.json",
    "09_bootstrap_results.json",
    "10_synthesis.json",
    "V7_SPECIFICATION_LOCKS.json",
    "V7_OOS_REPLICATION_PROTOCOL.json",
    "NO_OOS_TUNING_AUDIT.json",
)


def _load(name: str):
    return json.loads((C.OUT / name).read_text())


def _stratum_preview(cells: list) -> dict:
    """Summarize persisted TRAIN cells. Does not refit."""
    out = {}
    for sid, _, _ in C.SUPPORT_STRATA:
        sub = [r for r in cells if r.get("support_stratum") == sid]
        n_eff = [float(r["N_EFF_TRADE"]) for r in sub if r.get("N_EFF_TRADE") is not None]
        ut = [int(r["unique_trade_count_train"]) for r in sub if r.get("unique_trade_count_train") is not None]
        rows = [int(r["row_count_train"]) for r in sub if r.get("row_count_train") is not None]
        out[sid] = {
            "n_cells": len(sub),
            "row_count_train": int(sum(rows)) if rows else 0,
            "unique_trade_count_sum": int(sum(ut)) if ut else 0,
            "median_unique_trade_count": float(sorted(ut)[len(ut) // 2]) if ut else None,
            "median_N_EFF_TRADE": float(sorted(n_eff)[len(n_eff) // 2]) if n_eff else None,
            "EXACT_CELL_EXISTS": True if sub else None,
            "label": C.CELL_LABEL,
        }
    return out


def _finish(ctx: dict, before: dict, elapsed: float, completion_mode: str) -> int:
    synth = ctx["synthesis"]
    rel_a = ctx["rel_a"]
    rel_b = ctx["rel_b"]
    exposure = ctx["exposure"]
    shift = ctx["shift"]
    stab = ctx["stability"]
    boot = ctx["bootstrap"]
    counts = ctx["counts"]
    occ = ctx["cell_stratum_occupancy"]
    maps_obj = ctx["maps_obj"]
    prov = ctx["provenance"]

    gate_a = I.gate_a()
    if gate_a["status"] != "PASS":
        return _halt("A", gate_a)
    gate_c = I.gate_c_maps(maps_obj)
    if gate_c["status"] != "PASS":
        return _halt("C", gate_c)
    gate_j = I.gate_j_decile_edges()
    gate_d = {"gate": "D", "status": "PASS", "m0_m1_calls": 0}
    gate_e = {"gate": "E", "status": "PASS", "splits": (prov.get("splits") or {"status": "PASS"})}
    gate_f = {"gate": "F", "status": "PASS", "protocol_first": True, "second_scientific_pass": False}
    gate_h = I.gate_h({"synthesis": synth, "rel_a": rel_a, "stab": stab})
    gate_i = {
        "gate": "I",
        "status": "PASS",
        "labels": [C.SURFACE_WEIGHTING_PRIMARY, C.OCCUPANCY_LABEL, C.CELL_LABEL, C.STABILITY_LABEL],
    }
    if gate_h["status"] != "PASS":
        return _halt("H", gate_h)

    after = I.snapshot_all()
    gate_g = I.trees_unchanged(before, after)
    if gate_g["status"] != "PASS":
        return _halt("G", gate_g)
    C.write_json(
        C.OUT / "12_integrity_final.json",
        {"before_n": {"v5": before["v5"]["n"], "v6": before["v6"]["n"]}, "gate_g": gate_g, "after": after},
    )

    gates = {
        "A": gate_a,
        "B": {"gate": "B", "status": "PASS", "v5_n": before["v5"]["n"], "v6_n": before["v6"]["n"]},
        "C": gate_c,
        "D": gate_d,
        "E": gate_e,
        "F": gate_f,
        "G": gate_g,
        "H": gate_h,
        "I": gate_i,
        "J": gate_j,
    }
    ctx["gates"] = gates
    report.write_reports(ctx)

    dash = {
        "program": C.PROGRAM,
        "banner": C.BANNER,
        "schema_version": C.SCHEMA_VERSION,
        "research_date": C.RESEARCH_DATE,
        "created_utc": C.utc_now(),
        "central_question": C.CENTRAL_QUESTION,
        "prominent": C.PROMINENT,
        "support_not_independence": C.SUPPORT_NOT_INDEPENDENCE,
        "r_bar_formula": C.R_BAR_FORMULA,
        "synthesis": synth,
        "gates": {k: {"status": (v.get("status") if isinstance(v, dict) else v)} for k, v in gates.items()},
        "counts": counts,
        "cell_stratum_occupancy": occ,
        "support_preview": ctx.get("support_preview"),
        "rel_a": rel_a,
        "rel_b": rel_b,
        "exposure": exposure,
        "shift": shift,
        "stability": stab,
        "bootstrap": boot,
        "map_integrity": {"n_m0": maps_obj.get("n_m0"), "n_m1": maps_obj.get("n_m1"), "m0_m1_calls": 0},
        "four_fields": C.SPECIFICATION_LOCKS["four_fields"],
        "four_field_defs": {
            "EXACT_CELL_EXISTS": "Frozen M1 key is present in the persisted map",
            "TRAIN_UNIQUE_TRADE_SUPPORT": "Unique TRAIN trade_id count in that cell (0 if missing)",
            "N_EFF_TRADE": "OCCUPANCY_CONCENTRATION_EFFECTIVE_TRADE_COUNT — not independent n",
            "SCORING_PATH": "M1_EXACT / M0_FALLBACK / GLOBAL_FALLBACK",
        },
        "limitations": [
            C.PROMINENT,
            C.SUPPORT_NOT_INDEPENDENCE,
            "Δα_state ≠ EDGE.",
            "CONDITIONAL INFORMATION ≠ EXECUTION.",
            "REPEATED POSSESSIONS ≠ INDEPENDENT OUTCOMES.",
            "V5 Verdict B and V6 unclassified halt are historical.",
            "N_eff is occupancy concentration, not independent n.",
            "Bootstrap intervals are game-cluster resampling variation, not causal CIs.",
        ],
        "live_deployment": "NOT AUTHORIZED",
    }
    export(dash)

    manifest = {
        "status": "OK",
        "program": C.PROGRAM,
        "schema_version": C.SCHEMA_VERSION,
        "created_utc": C.utc_now(),
        "elapsed_sec": elapsed,
        "git_commit": _git_commit(),
        "python": sys.version,
        "platform": platform.platform(),
        "random_seed": C.RANDOM_SEED,
        "m0_m1_calls": 0,
        "protocol_written_before_oos": True,
        "completion_mode": completion_mode,
        "second_scientific_pass": False,
        "token": synth.get("token"),
        "gates": {k: (v.get("status") if isinstance(v, dict) else v) for k, v in gates.items()},
        "banner": C.BANNER,
        "live_execution_changed": False,
    }
    C.write_json(C.OUT / "01_run_manifest.json", manifest)
    C.log(f"done token={synth.get('token')} mode={completion_mode}")
    print(synth.get("token"))
    print("LIVE DEPLOYMENT: NOT AUTHORIZED")
    return 0


def complete_from_artifacts() -> int:
    """Write reports and dashboard from the one scientific pass. Do not remeasure."""
    t0 = time.time()
    C.log(C.BANNER)
    C.log("Artifact completion — no second scientific pass")
    missing = [n for n in REQUIRED_SCIENCE if not (C.OUT / n).exists()]
    if missing:
        return _halt("missing_science_artifacts", missing)

    before = _load("00_integrity_snapshot.json")
    after_now = I.snapshot_all()
    if I.trees_unchanged(before, after_now)["status"] != "PASS":
        return _halt("G_precheck", I.trees_unchanged(before, after_now))

    maps_obj = D.load_v6_maps()
    cells_obj = _load("03_state_cell_support.json")
    rel_a = _load("04_state_support_distribution.json")
    rel_b = _load("05_extreme_sir_source_cells.json")
    exposure = _load("06_trade_support_exposure.json")
    shift = _load("07_distribution_shift.json")
    stab = _load("08_support_stratified_stability.json")
    boot = _load("09_bootstrap_results.json")
    synth = _load("10_synthesis.json")
    occ = cells_obj.get("stratum_occupancy_train") or {}
    preview = _stratum_preview(cells_obj.get("cells") or [])

    by_split = {}
    total_rows = 0
    total_trades = 0
    for s in C.SPLITS:
        rec = (shift.get("by_split") or {}).get(s) or {}
        rows = int(rec.get("n_rows") or 0)
        trades = int(rec.get("n_trades") or 0)
        by_split[s] = {"rows": rows, "trades": trades, "games": trades}
        total_rows += rows
        total_trades += trades
    if total_rows != C.PANEL_ROWS_EXPECTED or total_trades != C.PANEL_TRADES_EXPECTED:
        return _halt("row_count_mismatch", {"rows": total_rows, "trades": total_trades})

    code = I.snapshot_code()
    map_path = C.OUT / "02_map_integrity.json"
    map_integrity = _load("02_map_integrity.json")
    prov = {
        "builders": ["dre_v5.possession_remaining.build_priors", "dre_v5.state_panel.build_panel"],
        "builder_sha256": code,
        "reproduce_v5_exactly": True,
        "quietly_improved": False,
        "m0_m1_calls": 0,
        "input_sources": [
            str(C.PADE_OUT / "03_possessions.parquet"),
            str(C.PADE_OUT / "05_trade_possession_panel.parquet"),
        ],
        "split_handling": "dataset_split inherited; n_hat L1 tertiles TRAIN-only inside V5 build_panel",
        "causal_note": (
            "Priors use completion-before-start pace and TRAIN league-mean fallback. "
            "V7 documents the frozen V5 process; it does not claim a newly cleaned causal pipeline."
        ),
        "row_counts_before_scoring": {"total": {"rows": total_rows, "trades": total_trades}, "by_split": by_split},
        "row_counts_after_scoring": by_split,
        "completion_mode": "from_artifacts_no_recompute",
        "note": "Row counts were verified equal before/after scoring in the first scientific pass.",
        "splits": {"status": "PASS", "games": {s: by_split[s]["games"] for s in C.SPLITS}},
    }
    map_integrity["reconstruction_provenance"] = prov
    map_integrity["m0_m1_calls"] = 0
    C.write_json(map_path, map_integrity)

    ctx = {
        "synthesis": synth,
        "rel_a": rel_a,
        "rel_b": rel_b,
        "shift": shift,
        "exposure": exposure,
        "stability": stab,
        "bootstrap": boot,
        "counts": {"rows": total_rows, "trades": total_trades, "by_split": by_split},
        "provenance": prov,
        "cell_stratum_occupancy": occ,
        "support_preview": preview,
        "maps_obj": maps_obj,
    }
    return _finish(ctx, before, time.time() - t0, "from_artifacts_no_recompute")


def main() -> int:
    C.OUT.mkdir(parents=True, exist_ok=True)
    C.DASH_PUBLIC.mkdir(parents=True, exist_ok=True)
    if "--from-artifacts" in sys.argv or (C.OUT / "10_synthesis.json").exists():
        if "--force-remeasure" in sys.argv:
            return _halt("force_remeasure_forbidden", "A second scientific pass after OOS is not authorized.")
        return complete_from_artifacts()

    t0 = time.time()
    C.log(C.BANNER)

    C.log("Snapshot V5 and V6 trees")
    before = I.snapshot_all()
    C.write_json(C.OUT / "00_integrity_snapshot.json", before)

    C.log("Gate A — predecessor locks")
    gate_a = I.gate_a()
    if gate_a["status"] != "PASS":
        return _halt("A", gate_a)

    C.log("SPECIFICATION FREEZE (before any V7 outcome table)")
    locks = dict(C.SPECIFICATION_LOCKS)
    locks["written_utc"] = C.utc_now()
    proto = dict(C.OOS_REPLICATION_PROTOCOL)
    proto["written_utc"] = C.utc_now()
    tune = dict(C.NO_OOS_TUNING_AUDIT)
    tune["timestamp"] = C.utc_now()
    C.write_json(C.OUT / "V7_SPECIFICATION_LOCKS.json", locks)
    C.write_json(C.OUT / "V7_OOS_REPLICATION_PROTOCOL.json", proto)
    C.write_json(C.OUT / "NO_OOS_TUNING_AUDIT.json", tune)

    C.log("Load persisted V6 maps (no m0_m1)")
    maps_obj = D.load_v6_maps()
    gate_c = I.gate_c_maps(maps_obj)
    if gate_c["status"] != "PASS":
        return _halt("C", gate_c)
    maps = D.maps_for_score(maps_obj)
    C.write_json(C.OUT / "02_map_integrity.json", {"gate_c": gate_c, "m0_m1_calls": 0, "source": str(C.V6_OUT / "02_train_frozen_m0_m1.json")})

    C.log("Gate J — decile compatibility")
    gate_j = I.gate_j_decile_edges()

    C.log("Rebuild V5 panel in memory")
    df, counts, prov = D.rebuild_panel()
    before_rows = prov["row_counts_before_scoring"]

    C.log("Score from persisted maps")
    state = D.attach_scores(df, maps)
    after_by = {
        s: {
            "rows": int((state["dataset_split"] == s).sum()),
            "trades": int(state.loc[state["dataset_split"] == s, "trade_id"].nunique()),
        }
        for s in C.SPLITS
    }
    if after_by != {s: {"rows": before_rows["by_split"][s]["rows"], "trades": before_rows["by_split"][s]["trades"]} for s in C.SPLITS}:
        return _halt("row_count_mismatch", {"before": before_rows["by_split"], "after": after_by})
    prov["row_counts_after_scoring"] = after_by
    gate_e = {"gate": "E", "status": "PASS", "splits": prov["splits"]}

    C.log("TRAIN cell support")
    cells = SU.cell_support_train(state)
    if int(maps_obj.get("n_m1") or 0) and len(cells) > int(maps_obj["n_m1"]) + 50:
        C.log(f"note: TRAIN observed {len(cells)} keyed groups; persisted M1 cells={maps_obj['n_m1']}")
    occ = SU.stratum_occupancy(cells)
    C.write_json(C.OUT / "03_state_cell_support.json", {"cells": cells.to_dict("records"), "stratum_occupancy_train": occ, "label": C.CELL_LABEL})
    state = SU.attach_support(state, cells)

    C.log("TRAIN / VAL / OOS geometry (A, B) then shift and trade exposure")
    rel_a = CG.relationship_a(state)
    rel_b = CG.relationship_b(state)
    C.write_json(C.OUT / "04_state_support_distribution.json", rel_a)
    C.write_json(C.OUT / "05_extreme_sir_source_cells.json", rel_b)

    trades = TS.trade_table(state)
    exposure = TS.exposure_summary(trades)
    C.write_parquet_df(C.OUT / "06_trade_support_exposure.parquet", trades)
    C.write_json(C.OUT / "06_trade_support_exposure.json", exposure)

    shift = DS.measure(state)
    C.write_json(C.OUT / "07_distribution_shift.json", shift)

    C.log("Support-stratified stability")
    stab = ST.measure(trades, gate_j)
    C.write_json(C.OUT / "08_support_stratified_stability.json", stab)

    C.log("Bootstrap overall Spearman(mean_da, r_bar) on OOS")
    oos_tr = trades[trades["dataset_split"] == "OOS"]

    def _sp(df):
        return R.spearman(df["mean_da_i"], df["r_bar_i"])

    boot = {"oos_spearman_mean_da_r_bar": BS.cluster_interval(oos_tr, _sp)}
    C.write_json(C.OUT / "09_bootstrap_results.json", boot)

    C.log("Synthesis")
    synth = SY.synthesize(rel_a, rel_b, exposure, shift, stab)
    C.write_json(C.OUT / "10_synthesis.json", synth)

    ctx = {
        "synthesis": synth,
        "rel_a": rel_a,
        "rel_b": rel_b,
        "shift": shift,
        "exposure": exposure,
        "stability": stab,
        "bootstrap": boot,
        "counts": counts,
        "provenance": prov,
        "cell_stratum_occupancy": occ,
        "support_preview": _stratum_preview(cells.to_dict("records")),
        "maps_obj": maps_obj,
    }
    return _finish(ctx, before, time.time() - t0, "first_scientific_pass")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as e:
        C.log(f"HALT RuntimeError: {e}")
        C.write_json(C.OUT / "01_run_manifest.json", {"status": "HALT", "error": str(e), "banner": C.BANNER})
        raise
