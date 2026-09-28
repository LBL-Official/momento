#!/usr/bin/env python3
"""One frozen scientific run. Protocol first. No live trading.

Default: full candle pass.
`--from-artifacts`: regenerate reports/classification from saved JSON (no rescan).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import (  # noqa: E402
    BANNER,
    DATA,
    FIGURES,
    PROGRAM,
    REPORTS,
    RESULTS,
    ROOT as EXP_ROOT,
    SCHEMA_VERSION,
    SPECIFICATION_LOCKS,
    WH_OUT,
    log,
    utc_now,
    write_csv,
    write_json,
)
import alpha_persistence as AP  # noqa: E402
import build_first80_dataset as B  # noqa: E402
import figures as FIG  # noqa: E402
import module_a_calibration as MA  # noqa: E402
import module_b_path_survival as MB  # noqa: E402
import module_c_decomposition as MC  # noqa: E402
import module_d_hedge_states as MD  # noqa: E402
import pandas as pd  # noqa: E402
import quotes as Q  # noqa: E402
import report  # noqa: E402
import robustness as RB  # noqa: E402


def _write_manifest(clf: dict, elapsed: float, source: str) -> dict:
    manifest = {
        "status": "OK",
        "program": PROGRAM,
        "schema_version": SCHEMA_VERSION,
        "created_utc": utc_now(),
        "elapsed_sec": elapsed,
        "letter": clf["letter"],
        "source": source,
        "live_execution_changed": False,
        "banner": BANNER,
        "m0_m1_calls": 0,
        "first80_redefined": False,
        "touch40_redefined": False,
    }
    write_json(RESULTS / "run_manifest.json", manifest)
    write_json(WH_OUT / "run_manifest.json", manifest)
    return manifest


def load_artifacts() -> dict:
    cal = json.loads((RESULTS / "terminal_calibration.json").read_text())
    path = json.loads((RESULTS / "path_survival.json").read_text())
    joint = json.loads((RESULTS / "joint_outcome_tree.json").read_text())
    hedge = json.loads((RESULTS / "hedge_state.json").read_text())
    alpha = json.loads((RESULTS / "alpha_persistence.json").read_text())
    rb = json.loads((RESULTS / "robustness_bootstrap.json").read_text())
    ident = {}
    ip = DATA / "identity_gate.json"
    if ip.exists():
        ident = json.loads(ip.read_text())
    return {
        "module_a": {"calibration": cal},
        "module_b": path,
        "module_c": {"trees": joint["trees"], "scenarios": joint["scenarios"]},
        "module_d": hedge,
        "alpha": alpha,
        "robustness": rb,
        "identity": ident,
    }


def refresh_csv_from_artifacts(ctx: dict) -> None:
    """CSV hygiene only. Does not recompute scientific objects."""
    surf_pq = DATA / "threshold_calibration.parquet"
    if surf_pq.exists():
        surf = pd.read_parquet(surf_pq)
        write_csv(RESULTS / "threshold_calibration.csv", MA.flatten_threshold_surface(surf))
    path = ctx["module_b"]
    rows = []
    for name, blk, splits in (
        ("FIRST80", path["FIRST80"]["full"], path["FIRST80"]["splits"]),
        ("FIRST75", path["FIRST75"]["full"], path["FIRST75"]["splits"]),
        ("NON_FIRST80", path["NON_FIRST80"]["full"], path["NON_FIRST80"]["splits"]),
    ):
        rows.append(
            {
                "control": name,
                "split": "FULL",
                "n_total": blk.get("n_total"),
                "n_wins": blk.get("n_wins", blk.get("n")),
                "k_never_t40": blk.get("k"),
                "p_not_t40_given_w": blk.get("estimate"),
                "wilson_lo": (blk.get("wilson") or {}).get("lo"),
                "wilson_hi": (blk.get("wilson") or {}).get("hi"),
            }
        )
        for s, b in splits.items():
            rows.append(
                {
                    "control": name,
                    "split": s,
                    "n_total": b.get("n_total"),
                    "n_wins": b.get("n_wins", b.get("n")),
                    "k_never_t40": b.get("k"),
                    "p_not_t40_given_w": b.get("estimate"),
                    "wilson_lo": (b.get("wilson") or {}).get("lo"),
                    "wilson_hi": (b.get("wilson") or {}).get("hi"),
                }
            )
    write_csv(RESULTS / "path_survival.csv", pd.DataFrame(rows))
    write_csv(RESULTS / "control_comparisons.csv", pd.DataFrame(rows))


def from_artifacts() -> int:
    t0 = time.time()
    log("Regenerating reports from artifacts (no candle rescan)")
    ctx = load_artifacts()
    refresh_csv_from_artifacts(ctx)
    report.write_all(ctx)
    clf = ctx["classification"]
    manifest = _write_manifest(clf, time.time() - t0, "from_artifacts")
    log(f"done letter={clf['letter']} in {manifest['elapsed_sec']:.1f}s")
    print(clf["letter"])
    print("LIVE DEPLOYMENT: NOT AUTHORIZED")
    return 0


def main() -> int:
    t0 = time.time()
    log(BANNER)
    for p in (DATA, RESULTS, FIGURES, REPORTS, WH_OUT):
        p.mkdir(parents=True, exist_ok=True)

    locks = dict(SPECIFICATION_LOCKS)
    locks["written_utc"] = utc_now()
    write_json(EXP_ROOT / "SPECIFICATION_LOCKS.json", locks)
    write_json(RESULTS / "SPECIFICATION_LOCKS.json", locks)

    log("Build frozen FIRST80 dataset (no redefinition)")
    df, meta = B.build()
    log(f"identity {meta['identity']['status']} n={len(df)}")

    log("Load candles (same window/quality as frozen audit)")
    quotes, markets, games, _meta = Q.load_quotes()
    log(f"tickers with quotes {len(quotes)}")

    log("MODULE A")
    a = MA.run(df, quotes, markets, games)
    log("MODULE B")
    b = MB.run(df, quotes, markets, games)
    log("MODULE C")
    c = MC.run(df)
    log("MODULE D")
    d = MD.run(df, quotes, games)
    log("Alpha persistence (TRAIN Fhat only)")
    al = AP.run(df)
    log("Robustness bootstrap")
    rb = RB.run(df)

    ctx = {
        "module_a": a,
        "module_b": b,
        "module_c": c,
        "module_d": d,
        "alpha": al,
        "robustness": rb,
        "identity": meta,
    }
    log("Figures")
    FIG.run(a["calibration"], a["surface"], b, c["trees"]["FULL"], d["by_threshold"], d["events"], c["sensitivity"])
    log("Reports")
    report.write_all(ctx)
    clf = ctx["classification"]
    manifest = _write_manifest(clf, time.time() - t0, "full_run")
    log(f"done letter={clf['letter']} in {manifest['elapsed_sec']:.1f}s")
    print(clf["letter"])
    print("LIVE DEPLOYMENT: NOT AUTHORIZED")
    return 0


if __name__ == "__main__":
    try:
        if "--from-artifacts" in sys.argv:
            raise SystemExit(from_artifacts())
        raise SystemExit(main())
    except RuntimeError as e:
        log(f"HALT {e}")
        write_json(RESULTS / "run_manifest.json", {"status": "HALT", "error": str(e), "banner": BANNER})
        raise
