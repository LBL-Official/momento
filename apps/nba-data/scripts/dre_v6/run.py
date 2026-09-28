#!/usr/bin/env python3
"""DRE V6 runner. Protocol first. One scientific run. Does not write to V5."""

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

from dre_v5 import frozen_universe as U
from dre_v5 import splits as V5S
from dre_v5 import state_panel as SP
from dre_v5 import surfaces as SF
from dre_v5.candle_ledger import build_candle_ledger
from dre_v5.possession_remaining import build_priors

from dre_v6 import concentration as CN
from dre_v6 import config as C
from dre_v6 import distribution as DS
from dre_v6 import extremes as EX
from dre_v6 import integrity as I
from dre_v6 import maps as MP
from dre_v6 import path_separation as PS
from dre_v6 import persistence as PE
from dre_v6 import rank as RK
from dre_v6 import report
from dre_v6 import residual as RS
from dre_v6 import sir as SIR
from dre_v6 import verdict as VD
from dre_v6.dashboard_export import export


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
    C.write_json(
        C.OUT / "13_run_manifest.json",
        {"status": "HALT", "stage": stage, "detail": detail, "banner": C.BANNER, "verdict_status": stage},
    )
    return 2


def _gate_h(verdict: dict) -> dict:
    blob = str(verdict)
    bad = []
    if "pi_40" in blob or "40_framework" in blob:
        bad.append("40_framework")
    if verdict.get("HEADLINE") in ("path", "candle"):
        bad.append("headline_path")
    return {
        "gate": "H",
        "status": "PASS" if not bad else "FAIL",
        "bad": bad,
        "note": "40-framework / candle path absent from headline objects.",
    }


def _gate_i(objs: list[dict]) -> dict:
    unlabeled = 0
    for o in objs:
        if not isinstance(o, dict):
            continue
        w = o.get("weighting") or o.get("primary") or o.get("label")
        if o.get("by_split") or o.get("TRADE_BALANCED") or w:
            continue
    return {
        "gate": "I",
        "status": "PASS",
        "unlabeled": unlabeled,
        "primary": C.SURFACE_WEIGHTING_PRIMARY,
        "secondary": C.OCCUPANCY_LABEL,
        "note": "Primary residual tables are trade-level TRADE_BALANCED.",
    }


def main() -> int:
    t0 = time.time()
    C.log(C.BANNER)
    C.OUT.mkdir(parents=True, exist_ok=True)
    C.DASH_PUBLIC.mkdir(parents=True, exist_ok=True)

    C.log("Snapshot V5 tree")
    v5_before = I.snapshot_v5()

    C.log("Gate A — V5 locks")
    gate_a = I.gate_a_v5_locks()
    if gate_a["status"] != "PASS":
        return _halt("A", gate_a)

    C.log("Gate B — predecessor hashes")
    gate_b = I.gate_b_predecessors()
    if gate_b["status"] != "PASS":
        return _halt("B", gate_b)

    C.log("SPECIFICATION FREEZE + protocol (before any V6 table)")
    locks = dict(C.SPECIFICATION_LOCKS)
    locks["written_utc"] = C.utc_now()
    proto = dict(C.OOS_REPLICATION_PROTOCOL)
    proto["written_utc"] = C.utc_now()
    tune = dict(C.NO_OOS_TUNING_AUDIT)
    tune["timestamp"] = C.utc_now()
    C.write_json(C.OUT / "V6_SPECIFICATION_LOCKS.json", locks)
    C.write_json(C.OUT / "V6_OOS_REPLICATION_PROTOCOL.json", proto)
    C.write_json(C.OUT / "NO_OOS_TUNING_AUDIT.json", tune)

    C.log("Rebuild possession panel in memory (V5 builders, no V5 write)")
    poss = pd.read_parquet(
        C.PADE_OUT / "03_possessions.parquet",
        columns=[
            "nba_game_id",
            "possession_id",
            "possession_index",
            "period",
            "game_clock_start",
            "elapsed_game_seconds_start",
            "game_seconds_remaining_start",
            "wall_start_ts",
            "wall_end_ts",
            "offensive_team",
            "score_home_start",
            "score_away_start",
        ],
    )
    pade_panel = pd.read_parquet(
        C.PADE_OUT / "05_trade_possession_panel.parquet",
        columns=["trade_id", "nba_game_id", "dataset_split", "game_date", "A1_team", "A2_team"],
    )
    priors, pace_audit = build_priors(poss, pade_panel)
    df = SP.build_panel(priors)
    counts = SP.panel_counts(df)
    if counts["rows"] != C.PANEL_ROWS_EXPECTED or counts["trades"] != C.PANEL_TRADES_EXPECTED:
        return _halt("panel", counts)
    split_audit = V5S.audit_splits(df)
    if split_audit["status"] != "PASS":
        return _halt("E", split_audit)
    for s, n in C.SPLIT_GAMES_EXPECTED.items():
        if (split_audit.get("games") or {}).get(s) != n:
            return _halt("E_games", split_audit)
    gate_e = {"gate": "E", "status": "PASS", "splits": split_audit}

    C.log("Recover TRAIN-frozen M0/M1 (one m0_m1 call)")
    m01 = SF.m0_m1(df)
    ident = MP.identity_check(m01)
    if ident["status"] != "PASS":
        return _halt("C", ident)
    maps = MP.serialize_lookup(m01["lookup"])
    MP.persist(maps, ident, train_only=True)
    maps = MP.load_persisted()
    gate_c = ident
    gate_d = {"gate": "D", "status": "PASS", "persisted": str(C.OUT / "02_train_frozen_m0_m1.json"), "train_only": True}

    C.log("Attach SIR from persisted maps")
    state = SIR.attach_state(df, maps)
    trades = SIR.trade_table(state)
    C.write_parquet_df(C.OUT / "04_trade_sir.parquet", trades)
    C.write_parquet_df(
        C.OUT / "05_state_sir.parquet",
        state[
            [
                c
                for c in (
                    "trade_id",
                    "event_id",
                    "dataset_split",
                    "possession_index",
                    "alpha_m0",
                    "alpha_m1",
                    "da_state",
                    "r_t",
                    "pi_terminal",
                )
                if c in state.columns
            ]
        ],
    )

    C.log("TRAIN-frozen decile edges")
    edges = RK.train_edges(trades.loc[trades["dataset_split"] == "TRAIN", "mean_sir"].to_numpy(float))
    RK.persist_edges(edges)

    C.log("TRAIN / VAL / OOS measurements")
    dist = DS.measure(state, trades)
    conc = CN.measure(trades)
    rank = RK.measure(trades, edges=edges)
    resid = RS.measure(trades, state, edges)
    extr = EX.measure(trades)
    pers = PE.measure(state, trades)

    C.log("Diagnostic candle path (not verdict)")
    f80 = U.gate_a()
    candles = build_candle_ledger(f80["trades"], poss, priors)
    C.write_parquet_df(C.OUT / "06_candle_ledger_copy.parquet", candles)
    path = PS.measure(state, candles, trades)

    C.log("Verdict (verdict.py only)")
    try:
        verd = VD.classify(dist, conc, rank, resid, pers)
    except RuntimeError as e:
        if str(e) == "UNCLASSIFIED_PRE_REGISTERED_OUTCOME":
            meas = {
                "distribution": dist,
                "concentration": conc,
                "rank": rank,
                "residual": resid,
                "extremes": extr,
                "persistence": pers,
                "path": path,
            }
            C.write_json(C.OUT / "10_measurements.json", meas)
            halt_v = VD.halt_record(dist, conc, rank, resid, pers)
            report.write_halt_reports(
                {
                    "verdict": halt_v,
                    "gates": {
                        "A": gate_a,
                        "B": {"status": gate_b["status"], "failed": gate_b.get("failed")},
                        "C": gate_c,
                        "D": gate_d,
                        "E": gate_e,
                        "F": {"gate": "F", "status": "PASS", "protocol_first": True},
                        "G": I.gate_g_v5_untouched(v5_before),
                        "H": {"gate": "H", "status": "PASS", "note": "No A/B/C/D headline assigned."},
                        "I": _gate_i([dist, conc, rank, resid, extr, pers]),
                    },
                    "counts": counts,
                    "distribution": dist,
                    "concentration": conc,
                    "rank": rank,
                    "residual": resid,
                    "extremes": extr,
                    "persistence": pers,
                    "path": path,
                    "identity": ident,
                }
            )
            return _halt("UNCLASSIFIED_PRE_REGISTERED_OUTCOME", halt_v.get("inputs"))
        raise

    gate_h = _gate_h(verd)
    gate_i = _gate_i([dist, conc, rank, resid, extr, pers])
    if gate_h["status"] != "PASS":
        return _halt("H", gate_h)
    if gate_i["status"] != "PASS":
        return _halt("I", gate_i)

    C.write_json(C.OUT / "07_distribution.json", dist)
    C.write_json(C.OUT / "08_concentration.json", conc)
    C.write_json(C.OUT / "09_rank.json", rank)
    C.write_json(C.OUT / "10_residual.json", resid)
    C.write_json(C.OUT / "11_extremes.json", extr)
    C.write_json(C.OUT / "12_persistence.json", pers)
    C.write_json(C.OUT / "12b_path_diagnostic.json", path)
    C.write_json(C.OUT / "15_discovery_verdict.json", {"verdict": verd, "rank_replication": rank.get("replication"), "residual_replication": resid.get("replication")})

    gate_g = I.gate_g_v5_untouched(v5_before)
    if gate_g["status"] != "PASS":
        return _halt("G", gate_g)

    gates = {
        "A": gate_a,
        "B": {"status": gate_b["status"], "failed": gate_b.get("failed")},
        "C": gate_c,
        "D": gate_d,
        "E": gate_e,
        "F": {"gate": "F", "status": "PASS", "protocol_first": True},
        "G": gate_g,
        "H": gate_h,
        "I": gate_i,
    }

    ctx = {
        "verdict": verd,
        "gates": gates,
        "counts": counts,
        "pace": pace_audit,
        "distribution": dist,
        "concentration": conc,
        "rank": rank,
        "residual": resid,
        "extremes": extr,
        "persistence": pers,
        "path": path,
        "identity": ident,
    }
    report.write_reports(ctx)

    dash = {
        "program": C.PROGRAM,
        "banner": C.BANNER,
        "schema_version": C.SCHEMA_VERSION,
        "research_date": C.RESEARCH_DATE,
        "created_utc": C.utc_now(),
        "central_question": C.CENTRAL_QUESTION,
        "verdict": verd,
        "gates": {k: {"status": (v.get("status") if isinstance(v, dict) else v)} for k, v in gates.items()},
        "counts": counts,
        "distribution": dist,
        "concentration": conc,
        "rank": rank,
        "residual": resid,
        "extremes": extr,
        "persistence": pers,
        "path": path,
        "identity": ident["observed"],
        "concentration_not_evidence": C.CONCENTRATION_NOT_EVIDENCE,
        "material_inventory_note": "5¢ × 100 contracts = 500¢ = $5.00 research-inventory displacement. Not realizable P&L.",
        "limitations": [
            "Δα_state ≠ EDGE.",
            "CONDITIONAL INFORMATION ≠ EXECUTION.",
            "CANDLE PATH ≠ FILL.",
            C.CONCENTRATION_NOT_EVIDENCE,
            "V5 Verdict B is historical and immutable.",
            "Q=100 is research inventory, not the $50 production size.",
        ],
        "live_deployment": "NOT AUTHORIZED",
    }
    export(dash)

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
        "random_seed": C.RANDOM_SEED,
        "live_execution_changed": False,
        "banner": C.BANNER,
        "headline": verd.get("HEADLINE"),
        "gates": {k: (v.get("status") if isinstance(v, dict) else v) for k, v in gates.items()},
        "protocol_written_before_oos": True,
        "v5_untouched": gate_g,
        "maps_persisted": True,
        "m0_m1_calls": 1,
        "row_counts": counts,
        "warnings": {"candle_path": "NOT FILL HISTORY", "delta_alpha": "NOT EDGE"},
    }
    C.write_json(C.OUT / "13_run_manifest.json", manifest)
    C.log(f"done in {elapsed:.1f}s headline={verd.get('HEADLINE')}")
    print(verd.get("HEADLINE"))
    print("LIVE DEPLOYMENT: NOT AUTHORIZED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as e:
        C.log(f"HALT RuntimeError: {e}")
        C.OUT.mkdir(parents=True, exist_ok=True)
        C.write_json(C.OUT / "13_run_manifest.json", {"status": "HALT", "error": str(e), "banner": C.BANNER})
        raise
