#!/usr/bin/env python3
"""MOMENTO DYNAMIC RISK ENGINE V5 — offline research runner.

Specification freeze → protocol write → integrity gates → TRAIN surfaces →
TRAIN-frozen lookup → VAL → OOS → verdict.

Does not modify PADE V1, DRE V2–V4, FIRST01, Risk, or live execution.

CANDLE PATH ≠ ACTUAL FILL
FORWARD DISTRIBUTION ≠ TRADABLE EDGE
CONDITIONAL ALPHA ≠ EXECUTABLE ACTION
LIVE DEPLOYMENT: NOT AUTHORIZED
"""

from __future__ import annotations

import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))

from dre_v5 import config as C
from dre_v5 import frozen_universe as U
from dre_v5 import greeks as G
from dre_v5 import integrity as I
from dre_v5 import leakage_audit as K
from dre_v5 import splits as S
from dre_v5 import state_panel as SP
from dre_v5 import surfaces as SF
from dre_v5.candle_ledger import build_candle_ledger
from dre_v5.dashboard_export import export
from dre_v5.possession_remaining import build_priors
from dre_v5.report import write_reports
from dre_v5.trade_ledger import build_trade_ledger


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
    C.write_json(C.OUT / "13_run_manifest.json", {"status": "HALT", "stage": stage, "detail": detail, "banner": C.BANNER})
    return 2


def _safe(v):
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, (np.floating, float)):
        x = float(v)
        if np.isnan(x) or np.isinf(x):
            return None
        return x
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    return v


def _path_norm(rows: list[dict]) -> dict:
    fails = []
    n = 0
    for r in rows:
        if r.get("level") in ("L1_META",):
            continue
        if r.get("n_rows") is None:
            continue
        n += 1
        if r.get("adequate") and (
            r.get("n_unique_trades") is None or r.get("n_unique_games") is None or r.get("weighting") != C.SURFACE_WEIGHTING_PRIMARY
        ):
            fails.append(r.get("level"))
    return {
        "gate": "G",
        "status": "PASS" if not fails else "FAIL",
        "n_cells": n,
        "fails": fails[:20],
        "rule": "Adequate cells report n_rows, n_unique_trades, n_unique_games, TRADE_BALANCED.",
    }


def _gate_i(rows: list[dict]) -> dict:
    unlabeled = [
        r
        for r in rows
        if r.get("payoff") == C.PRIMARY_PAYOFF
        and r.get("level") in ("L1", "L2", "L3")
        and r.get("weighting") != C.SURFACE_WEIGHTING_PRIMARY
    ]
    return {
        "gate": "I",
        "status": "PASS" if not unlabeled else "FAIL",
        "n_unlabeled": len(unlabeled),
        "primary": C.SURFACE_WEIGHTING_PRIMARY,
        "secondary": C.SURFACE_WEIGHTING_SECONDARY,
    }


def _examples(df: pd.DataFrame, n: int = 8) -> list[dict]:
    picks = []
    for split in ("OOS", "VALIDATION", "TRAIN"):
        xs = df[df["dataset_split"] == split]
        lengths = xs.groupby("trade_id").size().sort_values(ascending=False)
        take = 4 if split == "OOS" else 2
        for tid in lengths.index[:take]:
            g = xs[xs["trade_id"] == tid].sort_values("possession_index")
            if g.empty:
                continue
            path = []
            for r in g.itertuples():
                path.append(
                    {
                        "pidx": _safe(getattr(r, "possession_index", None)),
                        "clock": None if getattr(r, "game_clock", None) != getattr(r, "game_clock", None) else str(r.game_clock),
                        "elapsed": _safe(getattr(r, "elapsed_game_seconds", None)),
                        "price_cents": _safe(getattr(r, "current_price_cents", None)),
                        "a2_cents": _safe(getattr(r, "A2_yes_bid_cents", None)),
                        "diff": _safe(getattr(r, "score_differential_from_A1", None)),
                        "n_hat": _safe(getattr(r, "n_hat_remaining_prior", None)),
                        "v_mtm": _safe(getattr(r, "V_mtm_cents", None)),
                        "clock_l2": None if getattr(r, "clock_bin_l2", None) != getattr(r, "clock_bin_l2", None) else str(r.clock_bin_l2),
                    }
                )
            picks.append(
                {
                    "trade_id": str(tid),
                    "event_id": str(g["event_id"].iloc[0]),
                    "split": split,
                    "n": int(len(g)),
                    "y_settle_yes": _safe(g["y_settle_yes"].iloc[0]),
                    "pi_terminal": _safe(g["pi_terminal"].iloc[0]),
                    "path": path,
                    "label": "OBSERVED CANDLE PATH — NOT FILL HISTORY",
                }
            )
            if len(picks) >= n:
                return picks
    return picks


def _m01_public(m01: dict) -> dict:
    out = dict(m01)
    out.pop("lookup", None)
    return out


def _surface_view(rows: list[dict], levels=("L2", "L3")) -> list[dict]:
    keep = []
    for r in rows:
        if r.get("level") not in levels:
            continue
        if r.get("payoff") not in (C.PRIMARY_PAYOFF, "pi_mtm", "h_at_risk_40"):
            continue
        if r.get("level") == "L3" and not r.get("adequate"):
            continue
        keep.append(r)
    return keep


def main() -> int:
    t0 = time.time()
    C.log(C.BANNER)
    C.OUT.mkdir(parents=True, exist_ok=True)
    C.DASH_PUBLIC.mkdir(parents=True, exist_ok=True)

    C.log("Gate A — Frozen FIRST-80")
    gate_a = U.gate_a()
    if gate_a["status"] != "PASS":
        return _halt("A", {k: gate_a[k] for k in gate_a if k != "trades"})

    C.log("Gate B — PADE integrity")
    gate_b = I.gate_b_pade()
    if gate_b["status"] != "PASS":
        return _halt("B", gate_b)

    C.log("Gate C — DRE V4 integrity")
    gate_c = I.gate_c_v4()
    if gate_c["status"] != "PASS":
        return _halt("C", gate_c)

    C.log("SPECIFICATION FREEZE + OOS protocol (before any OOS table)")
    spec_locks = {
        "program": C.PROGRAM,
        "schema_version": C.SCHEMA_VERSION,
        "frozen": True,
        "units": C.UNITS,
        "primary_payoff": C.PRIMARY_PAYOFF,
        "V_mtm_cents": "100 * P_A1_cents",
        "delta_inv": C.DELTA_INV,
        "surface_weighting": {"PRIMARY": C.SURFACE_WEIGHTING_PRIMARY, "SECONDARY": C.SURFACE_WEIGHTING_SECONDARY},
        "clock_l2": C.OOS_REPLICATION_PROTOCOL["clock_l2"],
        "magnitude_band": list(C.MAGNITUDE_BAND),
        "mae_material_cents": C.MAE_MATERIAL_CENTS,
        "pace": {
            "rx_identity": C.PACE_RX_IDENTITY,
            "chronology": C.PACE_CHRONOLOGY,
            "k": C.PACE_K,
            "min_games": C.PACE_MIN_GAMES,
            "possession_row_is_offensive": C.POSSESSION_ROW_IS_OFFENSIVE,
        },
        "lambda": C.OOS_REPLICATION_PROTOCOL["lambda"],
        "diagnostic_40": C.OOS_REPLICATION_PROTOCOL["diagnostic_40_framework"],
        "written_utc": C.utc_now(),
        "note": "Frozen before TRAIN/VAL/OOS computation. Do not edit after this write.",
    }
    C.write_json(C.OUT / "SPECIFICATION_LOCKS.json", spec_locks)
    C.write_json(C.OUT / "OOS_REPLICATION_PROTOCOL.json", C.OOS_REPLICATION_PROTOCOL)
    tune = SF.no_oos_tuning_audit()
    C.write_json(C.OUT / "NO_OOS_TUNING_AUDIT.json", tune)

    C.log("Load possessions + prior pace")
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
    C.write_parquet_df(C.OUT / "03_possession_remaining_priors.parquet", priors)

    C.log("State panel")
    df = SP.build_panel(priors)
    counts = SP.panel_counts(df)
    universe = SP.universe_accounting(df, gate_a)
    if counts["rows"] != C.PANEL_ROWS_EXPECTED:
        return _halt("panel_rows", counts)
    if counts["trades"] != C.PANEL_TRADES_EXPECTED:
        return _halt("panel_trades", counts)
    if universe["universe"] != C.UNIVERSE_N:
        return _halt("universe", universe)
    if universe["unresolved_n"] != C.UNRESOLVED_EXPECTED:
        return _halt("unresolved", universe)

    leak = K.audit(list(C.FEATURE_COLS), pace_audit)
    split_audit = S.audit_splits(df)
    if leak["market_lookahead"]["status"] != "PASS" or leak["game_lookahead"]["status"] != "PASS" or leak["label_leakage"]["status"] != "PASS":
        return _halt("D", leak)
    if split_audit["status"] != "PASS":
        return _halt("E", split_audit)
    if leak["prior_pace"]["status"] != "PASS":
        return _halt("F", leak)
    if tune["status"] != "PASS" or tune.get("oos_used"):
        return _halt("H", tune)

    C.log("Trade ledger")
    trades = gate_a["trades"]
    ledger = build_trade_ledger(trades, df)
    C.write_parquet_df(C.OUT / "01_trade_ledger.parquet", ledger)
    C.write_json(
        C.OUT / "01_trade_ledger.json",
        {
            "n": int(len(ledger)),
            "unresolved": int(ledger["unresolved"].sum()),
            "disclaimer": "OBSERVED CANDLE PATH — NOT FILL HISTORY",
            "cards": ledger.to_dict("records"),
        },
    )

    C.log("Candle ledger (in-game post-entry, anti-lookahead PBP)")
    candles = build_candle_ledger(trades, poss, priors)
    C.write_parquet_df(C.OUT / "02_candle_ledger.parquet", candles)
    C.write_parquet_df(C.OUT / "04_possession_remaining_attached.parquet", df[["trade_id", "event_id", "nba_game_id", "possession_index", "n_hat_remaining_prior", "r_x_prior", "actual_remaining_possessions", "dataset_split"]])

    C.log("TRAIN surfaces (primary π_terminal, secondary π_mtm)")
    train_alpha = SF.build_surfaces(df, "pi_terminal", C.PRIMARY_PAYOFF, splits=("TRAIN",))
    train_mtm = SF.build_surfaces(df, "pi_mtm", "pi_mtm", splits=("TRAIN",))
    train_h = SF.build_hazard(df, splits=("TRAIN",))
    train_maps = SF.train_lookup_maps(train_alpha)
    C.log(f"TRAIN-frozen lookup L2={len(train_maps['l2'])} L3price={len(train_maps['l3_price'])}")

    C.log("VAL surfaces")
    val_alpha = SF.build_surfaces(df, "pi_terminal", C.PRIMARY_PAYOFF, splits=("VALIDATION",))
    val_mtm = SF.build_surfaces(df, "pi_mtm", "pi_mtm", splits=("VALIDATION",))
    val_h = SF.build_hazard(df, splits=("VALIDATION",))

    C.log("OOS surfaces + contrasts")
    oos_alpha = SF.build_surfaces(df, "pi_terminal", C.PRIMARY_PAYOFF, splits=("OOS",))
    oos_mtm = SF.build_surfaces(df, "pi_mtm", "pi_mtm", splits=("OOS",))
    oos_h = SF.build_hazard(df, splits=("OOS",))
    surfaces = train_alpha + val_alpha + oos_alpha + train_mtm + val_mtm + oos_mtm
    hazard = train_h + val_h + oos_h

    contrasts = SF.run_primary_contrasts(df)
    replication = SF.classify_replication(contrasts)
    m01 = SF.m0_m1(df)
    pathn = _path_norm(surfaces + hazard)
    gate_i = _gate_i(surfaces)
    if pathn["status"] != "PASS":
        return _halt("G", pathn)
    if gate_i["status"] != "PASS":
        return _halt("I", gate_i)

    C.log("Greeks + Lambda (scientific OOS uses TRAIN-frozen α)")
    grads = G.empirical_gradients(surfaces, "TRAIN") + G.empirical_gradients(surfaces, "OOS")
    gamma = {"TRAIN": G.empirical_gamma(surfaces, "TRAIN"), "OOS": G.empirical_gamma(surfaces, "OOS")}
    lambdas = G.path_lambdas(df, surfaces)
    vol = G.volatility_summary(df)
    haz_acc = SF.hazard_accounting(df)
    verdict = SF.classify_verdict(replication, m01, surfaces)

    C.log("Write artifacts")
    panel_cols = [c for c in [
        "trade_id", "event_id", "nba_game_id", "dataset_split", "game_date",
        "possession_index", "possessions_since_entry", "n_hat_remaining_prior", "r_x_prior",
        "is_A1_team_offense", "score_differential_from_A1", "d_sd_1", "d_sd_3", "d_sd_5",
        "elapsed_game_seconds", "game_seconds_remaining", "clock_cluster_30s",
        "clock_bin_l1", "clock_bin_l2", "score_bin_l1", "score_bin_l2",
        "n_hat_bin_l1", "n_hat_bin_l2", "price_bin_5", "price_bin_10",
        "A1_yes_bid_cents", "A2_yes_bid_cents", "current_price_cents", "entry_price_cents",
        "rel_a1_a2_cents", "complement_residual_cents", "V_mtm_cents", "delta_inv", "sigma_P",
        "y_settle_yes", "pi_terminal", "pi_mtm", "pi_40_framework", "pi_40_framework_label",
        "actual_remaining_possessions", "already_in_branch_40", "at_risk_40", "y_future_hit_40",
        "alignment_confidence",
    ] if c in df.columns]
    C.write_parquet_df(C.OUT / "05_state_panel.parquet", df[panel_cols])
    C.write_parquet_df(
        C.OUT / "06_labels.parquet",
        df[[c for c in ["trade_id", "possession_index", "dataset_split", "y_settle_yes", "pi_terminal", "pi_mtm", "pi_40_framework", "actual_remaining_possessions", "at_risk_40", "already_in_branch_40", "y_future_hit_40"] if c in df.columns]],
    )
    C.write_json(C.OUT / "07_leakage.json", leak)
    C.write_json(C.OUT / "08_splits.json", split_audit)
    if surfaces:
        C.write_parquet_df(C.OUT / "09_alpha_surface.parquet", pd.DataFrame(surfaces))
    C.write_json(C.OUT / "09_alpha_surface.json", {"rows": surfaces, "primary": C.PRIMARY_PAYOFF, "weighting": C.SURFACE_WEIGHTING_PRIMARY})
    if hazard:
        C.write_parquet_df(C.OUT / "10_hazard_surface.parquet", pd.DataFrame(hazard))
    C.write_json(C.OUT / "10_hazard_surface.json", {"rows": hazard, "accounting": haz_acc})
    C.write_json(
        C.OUT / "11_empirical_greeks.json",
        {
            "gradients": grads,
            "gamma": gamma,
            "lambda": lambdas,
            "volatility": vol,
            "scientific_oos_lambda_note": "TRAIN-frozen alpha on OOS paths",
            "descriptive_oos_lambda_note": "NEVER verdict input",
        },
    )
    C.write_json(C.OUT / "12_universe_accounting.json", universe)
    C.write_json(C.OUT / "pace_audit.json", pace_audit)
    C.write_json(C.OUT / "15_discovery_verdict.json", {"verdict": verdict, "replication": replication, "m01": _m01_public(m01), "contrasts": contrasts})

    gates = {
        "A": {"status": gate_a["status"], "observed": gate_a.get("observed")},
        "B": {"status": gate_b["status"], "hash_mismatch": gate_b.get("hash_mismatch")},
        "C": {"status": gate_c["status"], "hash_mismatch": gate_c.get("hash_mismatch")},
        "D": {
            "status": "PASS",
            "market": leak["market_lookahead"],
            "game": leak["game_lookahead"],
            "label": leak["label_leakage"],
        },
        "E": {"status": split_audit["status"], "overlap_games": split_audit.get("overlap_games")},
        "F": leak["prior_pace"],
        "G": pathn,
        "H": {"status": tune["status"], "oos_used": tune.get("oos_used"), "protocol_first": True},
        "I": gate_i,
    }

    ctx = {
        "verdict": verdict,
        "gates": gates,
        "universe": universe,
        "counts": counts,
        "m01": _m01_public(m01),
        "pace_audit": pace_audit,
        "lambda": lambdas,
        "replication": replication,
    }
    write_reports(ctx)

    examples = _examples(df)
    dash = {
        "program": C.PROGRAM,
        "banner": C.BANNER,
        "created_utc": C.utc_now(),
        "schema_version": C.SCHEMA_VERSION,
        "research_date": C.RESEARCH_DATE,
        "live_execution_changed": False,
        "central_question": "Does observable state reproducibly segment the frozen FIRST-80 terminal payoff distribution in unseen games?",
        "verdict": verdict,
        "gates": gates,
        "counts": counts,
        "universe": universe,
        "pace": pace_audit,
        "n_hat_tertiles_train": df.attrs.get("n_hat_tertiles_train"),
        "clock_l2": C.OOS_REPLICATION_PROTOCOL["clock_l2"],
        "surfaces": _surface_view(surfaces),
        "hazard": [r for r in hazard if r.get("adequate")],
        "hazard_accounting": haz_acc,
        "contrasts": contrasts,
        "replication": replication,
        "m01": _m01_public(m01),
        "gradients": grads,
        "gamma": gamma,
        "lambda": lambdas,
        "volatility": vol,
        "ledger": {
            "n": int(len(ledger)),
            "unresolved": int(ledger["unresolved"].sum()),
            "V_mtm_entry_cents": C.V_MTM_ENTRY_CENTS,
            "cards": ledger.to_dict("records"),
        },
        "candle_ledger_rows": int(len(candles)),
        "examples": examples,
        "layers": {
            "OBSERVED": "as-of PADE clocks, prices, possessions, Q=100 inventory",
            "CONDITIONAL_EXPECTED_PAYOFF": "trade-balanced α_frozen = E[100Y-80 | X]",
            "EMPIRICAL_SENSITIVITY": "finite-difference ∇α, Γ_emp, Λ_path",
            "UNOBSERVED_EXECUTION": "no fills, no stops, no live orders",
        },
        "limitations": [
            "Candle path ≠ proven fill.",
            "Π_terminal ∈ {+20, −80}; quantiles are empirical and often −80 / +20.",
            "P_A1, P_A2, rel, CR are related market coordinates, not four discoveries.",
            "Scientific OOS Lambda uses TRAIN-frozen α. Descriptive OOS Lambda is not a verdict input.",
            "40¢ framework is CANDLE_PATH_PROXY diagnostic only.",
            "Q=100 is research inventory, not the $50 production size.",
        ],
        "identity": "alpha_frozen = 100 * p_settle_yes - 80",
    }
    export(dash)

    untouched = {"pade": I.assert_untouched(gate_b), "v4": I.assert_untouched(gate_c)}
    if not all(v["ok"] for v in untouched.values()):
        return _halt("frozen_overwrite", untouched)

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
        "row_counts": counts,
        "universe": {k: universe[k] for k in universe if k != "unresolved"},
        "gates": {k: (v.get("status") if isinstance(v, dict) else v) for k, v in gates.items()},
        "headline": verdict.get("HEADLINE"),
        "untouched": untouched,
        "candle_rows": int(len(candles)),
        "protocol_written_before_oos": True,
        "warnings": {
            "unresolved_trades": universe.get("unresolved_n"),
            "ot_clock_separate": True,
            "candle_path": "NOT FILL HISTORY",
        },
    }
    C.write_json(C.OUT / "13_run_manifest.json", manifest)
    C.log(f"done in {elapsed:.1f}s headline={verdict.get('HEADLINE')}")
    print(verdict.get("HEADLINE"))
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
