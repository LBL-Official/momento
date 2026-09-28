#!/usr/bin/env python3
"""V4 report. One verdict. One production line. Negative result allowed."""

from __future__ import annotations

import csv
import json

from common import (
    EXPECTED_FIRST80,
    EXPECTED_GAMES,
    EXPECTED_STOPS,
    EXPECTED_SURVIVORS,
    OUT,
    Q_UNCONDITIONAL,
    SPEC_DIR,
    ev_from_q,
    utc_now,
    write_json,
)


def load(name):
    p = OUT / name
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def pct(x, d=2):
    if x is None:
        return "—"
    return f"{100.0 * x:.{d}f}%"


def num(x, d=4):
    if x is None:
        return "—"
    return f"{x:.{d}f}"


def decide(model, means):
    selected = model.get("selected") or "H0"
    promo = model.get("promoted_path_model")
    oos_sel = model.get("oos_selected") or {}
    oos_h0 = (model.get("oos") or {}).get("H0") or {}
    oos_hs = (model.get("oos") or {}).get("HS") or {}
    fw = (means.get("full_window") or {})
    p_perm = fw.get("permutation_p_train")
    overlap = fw.get("fraction_grid_overlap_95")
    brier_oos = oos_sel.get("brier")
    b0 = oos_h0.get("brier")
    bs = oos_hs.get("brier")
    path_oos_win = (
        promo
        and brier_oos is not None
        and b0 is not None
        and brier_oos <= 0.95 * b0
        and bs is not None
        and brier_oos <= bs - 0.001
    )
    reasons = {
        "selected": selected,
        "promoted_on_val": promo,
        "train_perm_p_full": p_perm,
        "train_mean_overlap": overlap,
        "path_oos_win_vs_h0_and_hs": path_oos_win,
        "val_reject_threshold": model.get("val_chosen_reject_threshold"),
    }
    if path_oos_win and model.get("val_chosen_reject_threshold") is not None:
        return (
            "VERDICT A — ROBUST ARRIVAL-PATH SIGNAL",
            "CANDIDATE FOR INDEPENDENT PRODUCTION VALIDATION",
            reasons,
        )
    if (p_perm is not None and p_perm < 0.05) or promo:
        return (
            "VERDICT B — WEAK / RESEARCH-ONLY PATH DIFFERENCE",
            "NO PRODUCTION CHANGE",
            reasons,
        )
    return (
        "VERDICT C — NO ROBUST ARRIVAL-PATH SIGNAL",
        "NO PRODUCTION CHANGE",
        reasons,
    )


def main() -> int:
    uni = load("trade_universe_summary.json")
    curves = load("curve_build_summary.json")
    means = load("mean_curves.json")
    model = load("model_results.json")
    leak = load("leakage_audit.json")
    fit = load("model_fit.json")
    verdict, production, reasons = decide(model, means)
    fw = means.get("full_window") or {}
    f50 = means.get("from50") or {}
    sc = means.get("score") or {}
    val = model.get("validation") or {}
    oos = model.get("oos") or {}

    lines = []
    a = lines.append
    a("# Complete Path Engine V4 — report")
    a("")
    a("Research only. Frozen 80/40 labels. The object is the **complete arrival path**")
    a("to first-80, not Z at 80 and not post-80 hazard.")
    a("")
    a(f"**{verdict}**")
    a("")
    a(f"Production line: **{production}**")
    a("")
    a("The report does not claim production ready. A negative result is accepted.")
    a("")
    a("## Frozen baseline")
    a("")
    a(f"- Games: {uni.get('games')} (expected {EXPECTED_GAMES})")
    a(f"- First-80: {uni.get('first80')} (expected {EXPECTED_FIRST80})")
    a(f"- Close-path 40: {uni.get('Y_40_CLOSE')} (expected {EXPECTED_STOPS})")
    a(f"- Survivors: {uni.get('survivors')} (expected {EXPECTED_SURVIVORS})")
    a(f"- Reproduction: {'PASS' if uni.get('baseline_ok') else 'FAIL'}")
    a(f"- q = {pct(Q_UNCONDITIONAL)} ; EV = {num(ev_from_q(Q_UNCONDITIONAL), 3)} R")
    a("")
    a("## Arrival paths")
    a("")
    a(f"- FULL_WINDOW ok: {curves.get('full_window_ok')}")
    a(f"- FROM_50 ok: {curves.get('from50_ok')}")
    a(f"- Game-aligned available: {curves.get('game_available')}")
    a(f"- Grid: {curves.get('grid_n')} time-normalized points")
    a("")
    a("## 1. Do mean failure and survivor curves differ?")
    a("")
    a("| Path | TRAIN ISD | TRAIN permutation p | grid pts with non-overlap 95% CI | VAL ISD | OOS ISD |")
    a("| --- | ---: | ---: | ---: | ---: | ---: |")
    for name, blk in (("FULL_WINDOW", fw), ("FROM_50", f50), ("score_diff", sc)):
        a(
            f"| {name} | {num(blk.get('isd_train'), 4)} | {num(blk.get('permutation_p_train'), 3)} | "
            f"{blk.get('n_grid_nonoverlap_95')} | {num(blk.get('val_isd_heldout_means'), 4)} | "
            f"{num(blk.get('oos_isd_heldout_means'), 4)} |"
        )
    a("")
    a(f"FULL_WINDOW max |μ_fail − μ_surv| on TRAIN: {num(fw.get('max_abs_mean_gap_train'), 3)} cents.")
    a(f"Fraction of grid with overlapping 95% mean CIs: {pct(fw.get('fraction_grid_overlap_95'))}.")
    a("")
    a("## 2. Path models vs state-at-80 vs unconditional")
    a("")
    a("| Model | VAL Brier | VAL AUC | OOS Brier | OOS AUC |")
    a("| --- | ---: | ---: | ---: | ---: |")
    for k in ("H0", "HS", "H2_l2_mean", "H3_dtw", "H4_functionals", "H5_pca"):
        v = val.get(k) or {}
        o = oos.get(k) or {}
        a(f"| {k} | {num(v.get('brier'), 5)} | {num(v.get('auc'), 3)} | {num(o.get('brier'), 5)} | {num(o.get('auc'), 3)} |")
    a("")
    a(f"- VAL selected: `{model.get('selected')}`")
    a(f"- Path model passing all VAL gates: `{model.get('promoted_path_model')}`")
    a("A path claim requires beating **both** H0 and HS (endpoint/local state).")
    a("")
    a("## 3. Economic reject rule")
    a("")
    a(f"- VAL hold EV: {num(model.get('val_hold_ev'), 3)}")
    a(f"- Frozen reject threshold: {model.get('val_chosen_reject_threshold')}")
    a(f"- OOS hold EV: {num(model.get('oos_hold_ev'), 3)}")
    a("Thresholds {0.30, 0.333, 0.40} searched on VAL only.")
    a("")
    a("## Leakage")
    a("")
    a(f"- Rows with source after first-80: {leak.get('n_rows_source_after_entry')}")
    a("- SAME_BAR_1M_LIMITATION on the last candle.")
    a("")
    a("## Decision")
    a("")
    a(f"- Reasons: `{json.dumps(reasons)}`")
    a("- V1/V2/V3 are not modified. This is not an entry filter unless verdict A.")
    a("")
    a("## Production")
    a("")
    a(f"- Status: **{production}**")
    a("- Live execution changed: **false**")
    a("")
    a(f"Generated {utc_now()}")
    a("")
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n")

    # ledger statuses
    ledger = SPEC_DIR / "HYPOTHESIS_LEDGER.csv"
    if ledger.exists():
        rows = list(csv.DictReader(ledger.open()))
        status = {
            "H0": "BENCHMARK",
            "HS": "FIT",
            "H1": "PERM_SIG" if (fw.get("permutation_p_train") or 1) < 0.05 else "NO_LOCATION_SHIFT",
            "H2": "VAL_PROMOTED" if model.get("promoted_path_model") == "H2_l2_mean" else "FIT",
            "H3": "VAL_PROMOTED" if model.get("promoted_path_model") == "H3_dtw" else "FIT",
            "H4": "VAL_PROMOTED" if model.get("promoted_path_model") == "H4_functionals" else "FIT",
            "H5": "VAL_PROMOTED" if model.get("promoted_path_model") == "H5_pca" else "FIT",
            "H6": "PERM_SIG" if (sc.get("permutation_p_train") or 1) < 0.05 else "NO_LOCATION_SHIFT",
            "H7": "PERM_SIG" if (f50.get("permutation_p_train") or 1) < 0.05 else "NO_LOCATION_SHIFT",
        }
        for r in rows:
            hid = r.get("hypothesis_id")
            if hid in status:
                r["status"] = status[hid]
        if rows:
            with ledger.open("w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)

    write_json(
        OUT / "summary.json",
        {
            "engine": "NBA_COMPLETE_PATH_ENGINE_V4",
            "written_utc": utc_now(),
            "research_only": True,
            "live_execution_changed": False,
            "frozen_baseline": {
                "games": uni.get("games"),
                "first80": uni.get("first80"),
                "close40": uni.get("Y_40_CLOSE"),
                "survivors": uni.get("survivors"),
                "reproduction": "PASS" if uni.get("baseline_ok") else "FAIL",
                "q": Q_UNCONDITIONAL,
            },
            "n_full_window": curves.get("full_window_ok"),
            "n_from50": curves.get("from50_ok"),
            "n_game": curves.get("game_available"),
            "mean_curves_full": {
                "isd_train": fw.get("isd_train"),
                "permutation_p": fw.get("permutation_p_train"),
                "n_nonoverlap": fw.get("n_grid_nonoverlap_95"),
                "overlap_frac": fw.get("fraction_grid_overlap_95"),
                "max_gap_cents": fw.get("max_abs_mean_gap_train"),
            },
            "selected": model.get("selected"),
            "promoted_path_model": model.get("promoted_path_model"),
            "validation": val,
            "oos_selected": model.get("oos_selected"),
            "verdict": verdict,
            "production_line": production,
            "reasons": reasons,
            "leakage_fail": leak.get("n_rows_source_after_entry"),
        },
    )
    print(verdict)
    print(production)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
