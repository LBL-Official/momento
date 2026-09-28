#!/usr/bin/env python3
"""MOMENTO DYNAMIC RISK ENGINE V4 — offline research runner.

State-transition distributions. Does not optimize h* or produce orders.
Does not modify PADE V1, DRE V2, DRE V3, FIRST01, Risk, or live execution.

CANDLE PATH ≠ ACTUAL FILL
FORWARD DISTRIBUTION ≠ TRADABLE EDGE
PREDICTIVE STATE ≠ EXECUTION SIGNAL
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

from dre_v4 import config as C
from dre_v4 import discoveries as DIS
from dre_v4 import frozen_universe as U
from dre_v4 import integrity as I
from dre_v4 import labels as L
from dre_v4 import leakage_audit as K
from dre_v4 import matched_price as MP
from dre_v4 import models as M
from dre_v4 import robustness as R
from dre_v4 import splits as S
from dre_v4 import state_panel as SP
from dre_v4 import transitions as T
from dre_v4.dashboard_export import export
from dre_v4.report import write_reports

PANEL_COLS = [
    "trade_id",
    "event_id",
    "nba_game_id",
    "market_ticker",
    "dataset_split",
    "game_date",
    "entry_timestamp",
    "possession_index",
    "possessions_since_entry",
    "period",
    "game_clock",
    "elapsed_game_seconds",
    "game_seconds_remaining",
    "position_age_wall_s",
    "is_A1_team_offense",
    "score_differential_from_A1",
    "current_price",
    "current_yes_bid",
    "current_yes_ask",
    "A1_mid",
    "deterioration_cents",
    "max_dd_since_entry",
    "recovery_from_trough",
    "market_observation_timestamp",
    "market_age_seconds",
    "alignment_confidence",
    "unique_market_obs",
    "stale_market",
    "v_3",
    "a_short",
    "market_volatility",
    "rolling_range_5",
    "est_remaining_r1",
    "regime",
    "y_settle_yes",
    "y_min_le_40_k5",
    "y_jump_40",
    "y_jump_40_kind",
    "p_settle_M3",
    "p_rec10_k5_M3",
    "p_det10_end_M3",
    "clock_horizon_basis",
    "order_10_5",
    "poss_to_det10",
    "poss_to_rec10",
    "wall_to_det10",
    "wall_to_rec10",
    "censored_det10",
    "censored_rec10",
]
for hz in C.POSS_HORIZONS:
    PANEL_COLS += [
        f"path_valid_{hz}",
        f"dd_{hz}",
        f"ue_{hz}",
        f"dP_{hz}",
        f"y_rec5_{hz}",
        f"y_rec10_{hz}",
        f"y_rec20_{hz}",
        f"y_det5_{hz}",
        f"y_det10_{hz}",
        f"y_det20_{hz}",
        f"path_class_{hz}",
    ]
for sec in C.CLOCK_HORIZONS:
    PANEL_COLS += [
        f"path_valid_c{sec}",
        f"dd_c{sec}",
        f"ue_c{sec}",
        f"dP_c{sec}",
        f"y_det10_c{sec}",
        f"y_rec10_c{sec}",
    ]

LABEL_COLS = [
    "trade_id",
    "event_id",
    "possession_index",
    "dataset_split",
    "current_price",
    "order_10_5",
    "poss_to_det10",
    "poss_to_rec10",
    "wall_to_det10",
    "wall_to_rec10",
    "censored_det10",
    "censored_rec10",
    "clock_horizon_basis",
]
for hz in C.POSS_HORIZONS:
    LABEL_COLS += [
        f"path_valid_{hz}",
        f"dd_{hz}",
        f"ue_{hz}",
        f"dP_{hz}",
        f"y_rec5_{hz}",
        f"y_rec10_{hz}",
        f"y_rec20_{hz}",
        f"y_det5_{hz}",
        f"y_det10_{hz}",
        f"y_det20_{hz}",
        f"path_class_{hz}",
    ]
for sec in C.CLOCK_HORIZONS:
    LABEL_COLS += [
        f"path_valid_c{sec}",
        f"dd_c{sec}",
        f"ue_c{sec}",
        f"dP_c{sec}",
        f"y_det10_c{sec}",
        f"y_rec10_c{sec}",
    ]

PATH_COLS = [
    "trade_id",
    "event_id",
    "possession_index",
    "dataset_split",
    "current_price",
    "order_10_5",
]
PATH_COLS += [f"path_class_{hz}" for hz in C.POSS_HORIZONS]
PATH_COLS += [f"path_valid_{hz}" for hz in C.POSS_HORIZONS]


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


def _project(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    keep = [c for c in cols if c in df.columns]
    return df[keep].copy()


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


def _flatten_matched(matched: dict) -> list[dict]:
    rows = []
    for split, rec in (matched.get("by_split") or {}).items():
        for key, bands in rec.items():
            if key.startswith("bin_") and isinstance(bands, dict):
                width = int(key.split("_", 1)[1])
                for lo, band in bands.items():
                    for pair, sl in (band.get("slices") or {}).items():
                        rows.append(
                            {
                                "split": split,
                                "match": f"bin_{width}",
                                "width": width,
                                "price_lo": int(lo),
                                "pair": pair,
                                "n_a": (sl.get("a") or {}).get("n"),
                                "n_b": (sl.get("b") or {}).get("n"),
                                "trades_a": (sl.get("a") or {}).get("trades"),
                                "trades_b": (sl.get("b") or {}).get("trades"),
                                "games_a": (sl.get("a") or {}).get("games"),
                                "games_b": (sl.get("b") or {}).get("games"),
                                "p_settle_a": (sl.get("a") or {}).get("p_settle"),
                                "p_settle_b": (sl.get("b") or {}).get("p_settle"),
                                "p_rec10_a": (sl.get("a") or {}).get("p_rec10"),
                                "p_rec10_b": (sl.get("b") or {}).get("p_rec10"),
                                "p_det10_a": (sl.get("a") or {}).get("p_det10"),
                                "p_det10_b": (sl.get("b") or {}).get("p_det10"),
                                "median_dd_a": ((sl.get("a") or {}).get("dd") or {}).get("median"),
                                "median_dd_b": ((sl.get("b") or {}).get("dd") or {}).get("median"),
                                "wasserstein_dd": (sl.get("delta") or {}).get("wasserstein_dd"),
                                "ks_dd": (sl.get("delta") or {}).get("ks_dd"),
                                "adequate": sl.get("adequate"),
                                "material": sl.get("material"),
                                "excluded_reason": sl.get("excluded_reason"),
                            }
                        )
            elif key == "nn_1c_60":
                sl = (bands or {}).get("early_vs_late") or {}
                rows.append(
                    {
                        "split": split,
                        "match": "nn_1c",
                        "width": None,
                        "price_lo": 60,
                        "pair": "early_vs_late",
                        "n_a": (sl.get("a") or {}).get("n"),
                        "n_b": (sl.get("b") or {}).get("n"),
                        "trades_a": (sl.get("a") or {}).get("trades"),
                        "trades_b": (sl.get("b") or {}).get("trades"),
                        "games_a": (sl.get("a") or {}).get("games"),
                        "games_b": (sl.get("b") or {}).get("games"),
                        "p_settle_a": (sl.get("a") or {}).get("p_settle"),
                        "p_settle_b": (sl.get("b") or {}).get("p_settle"),
                        "p_rec10_a": (sl.get("a") or {}).get("p_rec10"),
                        "p_rec10_b": (sl.get("b") or {}).get("p_rec10"),
                        "p_det10_a": (sl.get("a") or {}).get("p_det10"),
                        "p_det10_b": (sl.get("b") or {}).get("p_det10"),
                        "median_dd_a": ((sl.get("a") or {}).get("dd") or {}).get("median"),
                        "median_dd_b": ((sl.get("b") or {}).get("dd") or {}).get("median"),
                        "wasserstein_dd": (sl.get("delta") or {}).get("wasserstein_dd"),
                        "ks_dd": (sl.get("delta") or {}).get("ks_dd"),
                        "adequate": sl.get("adequate"),
                        "material": sl.get("material"),
                        "excluded_reason": sl.get("excluded_reason"),
                    }
                )
    return rows


def _empirical_baselines(df: pd.DataFrame) -> dict:
    out = {"by_split": {}, "note": "Empirical B0-style distributions by 5¢ price bin. Not a policy."}
    for split in ("TRAIN", "VALIDATION", "OOS"):
        xs = df[df["dataset_split"] == split].copy()
        xs["_bin"] = MP.price_bin(xs["current_price"], 5)
        rec = {}
        for lo in range(40, 85, 5):
            band = xs[(xs["_bin"] >= lo) & (xs["_bin"] < lo + 5)]
            if len(band) < 20:
                continue
            rec[str(lo)] = {
                "n": int(len(band)),
                "trades": int(band["trade_id"].nunique()),
                "games": int(band["event_id"].nunique()),
                "dd_5": MP._q(band["dd_5"].to_numpy(float)),
                "ue_5": MP._q(band["ue_5"].to_numpy(float)),
                "p_settle": MP._rate(band["y_settle_yes"]),
                "p_rec10_5": MP._rate(band["y_rec10_5"]),
                "p_det10_5": MP._rate(band["y_det10_5"]),
                "p_min40_k5": MP._rate(band["y_min_le_40_k5"]),
            }
        out["by_split"][split] = rec
    return out


def _clocks(df: pd.DataFrame) -> dict:
    def _desc(s):
        v = pd.to_numeric(s, errors="coerce").dropna()
        if v.empty:
            return {"n": 0}
        return {
            "n": int(len(v)),
            "mean": float(v.mean()),
            "median": float(v.median()),
            "p10": float(v.quantile(0.10)),
            "p90": float(v.quantile(0.90)),
        }

    return {
        "wall": {
            "field": "market_age_seconds / market_observation_timestamp",
            "age_seconds": _desc(df["market_age_seconds"]),
            "position_age_wall_s": _desc(df["position_age_wall_s"]),
            "stale_share": float((pd.to_numeric(df["market_age_seconds"], errors="coerce") >= 60).mean()),
        },
        "game": {
            "field": "elapsed_game_seconds / game_seconds_remaining / game_clock",
            "elapsed": _desc(df["elapsed_game_seconds"]),
            "remaining": _desc(df["game_seconds_remaining"]),
            "clock_horizon_basis": "elapsed_game_seconds",
            "note": "Remaining clock increases in 58/1221 trades and is not a horizon constructor.",
        },
        "possession": {
            "field": "possession_index / possessions_since_entry",
            "possession_index": _desc(df["possession_index"]),
            "possessions_since_entry": _desc(df["possessions_since_entry"]),
        },
        "not_collapsed": True,
    }


def _path_by_split(df: pd.DataFrame) -> dict:
    out = {}
    for hz in C.POSS_HORIZONS:
        out[hz] = {}
        for split in ("TRAIN", "VALIDATION", "OOS"):
            xs = df[df["dataset_split"] == split]
            vc = xs[f"path_class_{hz}"].value_counts(dropna=False)
            n = int(vc.sum())
            out[hz][split] = {
                "n": n,
                "rates": {c: float(vc.get(c, 0) / n) if n else None for c in C.PATH_CLASSES},
            }
    return out


def _regime_occ(df: pd.DataFrame) -> dict:
    out = {}
    for split in ("TRAIN", "VALIDATION", "OOS"):
        xs = df[df["dataset_split"] == split]
        vc = xs["regime"].value_counts(dropna=False)
        n = int(vc.sum())
        out[split] = {str(k): float(v / n) if n else None for k, v in vc.items()}
        out[split]["_n"] = n
    return out


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
                        "poss": _safe(getattr(r, "possessions_since_entry", None)),
                        "pidx": _safe(getattr(r, "possession_index", None)),
                        "clock": None if getattr(r, "game_clock", None) != getattr(r, "game_clock", None) else str(r.game_clock),
                        "period": _safe(getattr(r, "period", None)),
                        "elapsed": _safe(getattr(r, "elapsed_game_seconds", None)),
                        "gsr": _safe(getattr(r, "game_seconds_remaining", None)),
                        "age": _safe(getattr(r, "market_age_seconds", None)),
                        "price": _safe(getattr(r, "current_price", None)),
                        "bid": _safe(getattr(r, "current_yes_bid", None)),
                        "ask": _safe(getattr(r, "current_yes_ask", None)),
                        "diff": _safe(getattr(r, "score_differential_from_A1", None)),
                        "regime": None if getattr(r, "regime", None) != getattr(r, "regime", None) else str(r.regime),
                        "path_class_5": None
                        if getattr(r, "path_class_5", None) != getattr(r, "path_class_5", None)
                        else str(r.path_class_5),
                        "dd_5": _safe(getattr(r, "dd_5", None)),
                        "ue_5": _safe(getattr(r, "ue_5", None)),
                        "order_10_5": None if getattr(r, "order_10_5", None) != getattr(r, "order_10_5", None) else str(r.order_10_5),
                        "stale": _safe(getattr(r, "stale_market", None)),
                    }
                )
            picks.append(
                {
                    "trade_id": str(tid),
                    "event_id": str(g["event_id"].iloc[0]),
                    "nba_game_id": None if g["nba_game_id"].isna().all() else str(g["nba_game_id"].iloc[0]),
                    "split": split,
                    "n": int(len(g)),
                    "entry_price": _safe(g["current_price"].iloc[0]),
                    "entry_clock": None if pd.isna(g["game_clock"].iloc[0]) else str(g["game_clock"].iloc[0]),
                    "y_settle_yes": _safe(g["y_settle_yes"].iloc[0]),
                    "unresolved": False,
                    "path": path,
                    "label": "OBSERVED CANDLE PATH — NOT FILL HISTORY",
                }
            )
            if len(picks) >= n:
                return picks
    return picks


def _compact_matched(matched: dict) -> dict:
    oos = (matched.get("by_split") or {}).get("OOS") or {}
    robust = {}
    for w in C.ROBUST_BINS:
        sl = (((oos.get(f"bin_{w}") or {}).get("60") or {}).get("slices") or {}).get("early_vs_late")
        if sl:
            robust[str(w)] = sl
    return {
        "primary_spec": matched.get("primary_spec"),
        "primary_oos_early_late_60": matched.get("primary_oos_early_late_60"),
        "oos_60_5_slices": ((oos.get("bin_5") or {}).get("60") or {}).get("slices"),
        "oos_nn_1c_60": oos.get("nn_1c_60"),
        "robust_early_late_60": robust,
        "n_excluded": len(matched.get("excluded") or []),
        "excluded_head": (matched.get("excluded") or [])[:25],
        "label": "RESEARCH DISTRIBUTION — NOT A TRADING INSTRUCTION",
    }


def _surfaces_from_flat(rows: list[dict]) -> list[dict]:
    keep = []
    for r in rows:
        if r.get("split") != "OOS":
            continue
        if r.get("match") != "bin_5":
            continue
        keep.append(r)
    return keep


def main() -> int:
    t0 = time.time()
    C.log(C.BANNER)
    C.OUT.mkdir(parents=True, exist_ok=True)
    C.DASH_PUBLIC.mkdir(parents=True, exist_ok=True)

    C.log("Gate A — Frozen FIRST-80 integrity")
    gate_a = U.gate_a()
    if gate_a["status"] != "PASS":
        return _halt("A", {k: gate_a[k] for k in gate_a if k != "trades"})

    C.log("Gate B — PADE integrity")
    gate_b = I.gate_b_pade()
    if gate_b["status"] != "PASS":
        return _halt("B", gate_b)

    C.log("Gate C — DRE V2 integrity")
    gate_c = I.gate_c_v2()
    if gate_c["status"] != "PASS":
        return _halt("C", gate_c)

    C.log("Gate D — DRE V3 integrity")
    gate_d = I.gate_d_v3()
    if gate_d["status"] != "PASS":
        return _halt("D", gate_d)

    C.log("Build state panel + forward labels")
    df = SP.build_panel()
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

    feature_cols = []
    for cols in C.FAMILIES.values():
        feature_cols.extend(cols)
    feature_cols = list(dict.fromkeys(feature_cols))
    missing_feat = [c for c in feature_cols if c not in df.columns]
    if missing_feat:
        return _halt("missing_features", missing_feat)

    leak = K.audit(feature_cols)
    split_audit = S.audit_splits(df)
    path_norm = L.path_norm_check(df)
    tune = M.no_oos_tuning_audit()

    if leak["market_lookahead"]["status"] != "PASS":
        return _halt("E", leak)
    if leak["game_lookahead"]["status"] != "PASS":
        return _halt("F", leak)
    if leak["label_leakage"]["status"] != "PASS":
        return _halt("G", leak)
    if split_audit["status"] != "PASS":
        return _halt("H", split_audit)
    if path_norm["status"] != "PASS":
        return _halt("I", path_norm)
    if tune["status"] != "PASS" or tune.get("oos_used"):
        return _halt("J", tune)

    C.log("Empirical baselines + nested models (TRAIN fit)")
    baselines = _empirical_baselines(df)
    metrics, _fitted = M.fit_nested(df)
    incremental = M.incremental(metrics)

    C.log("Matched-price state comparison")
    matched = MP.run_matched(df)
    bootstrap = MP.bootstrap_primary(df)
    trans = T.matrices(df)
    seasonal = R.seasonal(df)
    conc = R.concentration(df)
    clocks = _clocks(df)
    path_emp = _path_by_split(df)
    regimes = _regime_occ(df)

    C.log("Classify discoveries")
    disc = DIS.classify(matched, incremental, bootstrap, path_norm)
    robustness = {
        "primary_spec": C.PRIMARY,
        "bin_width": {
            str(w): ((((matched.get("by_split") or {}).get("OOS") or {}).get(f"bin_{w}") or {}).get("60") or {})
            .get("slices", {})
            .get("early_vs_late")
            for w in C.ROBUST_BINS
        },
        "nn_1c": (((matched.get("by_split") or {}).get("OOS") or {}).get("nn_1c_60")),
        "seasonal": seasonal,
        "concentration": conc,
        "bootstrap": bootstrap,
        "bin_agree": disc.get("bin_agree"),
        "persist_direction": disc.get("persist_direction"),
        "concentrated": disc.get("concentrated"),
        "note": "Pre-registered. Not tuned on OOS.",
    }

    gates = {
        "A": {"status": gate_a["status"], "observed": gate_a.get("observed")},
        "B": {"status": gate_b["status"], "hash_mismatch": gate_b.get("hash_mismatch")},
        "C": {"status": gate_c["status"], "hash_mismatch": gate_c.get("hash_mismatch")},
        "D": {"status": gate_d["status"], "hash_mismatch": gate_d.get("hash_mismatch")},
        "E": leak["market_lookahead"],
        "F": leak["game_lookahead"],
        "G": leak["label_leakage"],
        "H": {"status": split_audit["status"], "overlap_games": split_audit.get("overlap_games")},
        "I": {"status": path_norm["status"], "fails": path_norm.get("fails")},
        "J": {"status": tune["status"], "oos_used": tune.get("oos_used")},
    }

    C.log("Write artifacts")
    C.write_json(
        C.OUT / "02_frozen_input_integrity.json",
        {"A": {k: gate_a[k] for k in gate_a if k != "trades"}, "B": gate_b, "C": gate_c, "D": gate_d},
    )
    C.write_parquet_df(C.OUT / "03_state_panel.parquet", _project(df, PANEL_COLS))
    C.write_json(C.OUT / "04_universe_accounting.json", universe)
    C.write_parquet_df(C.OUT / "05_forward_labels.parquet", _project(df, LABEL_COLS))
    C.write_parquet_df(C.OUT / "06_path_classes.parquet", _project(df, PATH_COLS))
    C.write_json(C.OUT / "06_path_classes.json", {"empirical": path_emp, "normalization": path_norm})
    C.write_json(C.OUT / "07_leakage_audit.json", leak)
    C.write_json(C.OUT / "08_split_audit.json", split_audit)
    C.write_json(C.OUT / "09_distribution_baselines.json", baselines)
    C.write_json(C.OUT / "10_nested_model_metrics.json", {"metrics": metrics, "incremental": incremental})
    C.write_parquet_df(C.OUT / "10_nested_model_metrics.parquet", pd.DataFrame(metrics))
    flat = _flatten_matched(matched)
    C.write_json(C.OUT / "11_matched_price_analysis.json", matched)
    if flat:
        C.write_parquet_df(C.OUT / "11_matched_price_analysis.parquet", pd.DataFrame(flat))
    surfaces = _surfaces_from_flat(flat)
    if surfaces:
        C.write_parquet_df(C.OUT / "12_state_distribution_surfaces.parquet", pd.DataFrame(surfaces))
    C.write_json(C.OUT / "12_state_distribution_surfaces.json", {"oos_bin5": surfaces, "regimes": regimes})
    C.write_json(C.OUT / "13_transition_matrices.json", trans)
    C.write_json(C.OUT / "14_robustness_checks.json", robustness)
    C.write_json(C.OUT / "15_discovery_verdict.json", disc)
    C.write_json(C.OUT / "NO_OOS_TUNING_AUDIT.json", tune)
    C.write_json(C.OUT / "clocks.json", clocks)

    examples = _examples(df)
    compact = _compact_matched(matched)

    ctx = {
        "gates": gates,
        "counts": counts,
        "universe": universe,
        "disc": disc,
        "incremental": incremental,
        "matched": compact,
        "robustness": robustness,
        "path_norm": path_norm,
    }
    write_reports(ctx)

    dash = {
        "program": C.PROGRAM,
        "banner": C.BANNER,
        "created_utc": C.utc_now(),
        "schema_version": C.SCHEMA_VERSION,
        "research_date": C.RESEARCH_DATE,
        "live_execution_changed": C.LIVE_EXECUTION_CHANGED,
        "verdict": disc["verdict"],
        "questions": disc["questions"],
        "gates": gates,
        "counts": counts,
        "universe": universe,
        "clocks": clocks,
        "path": {"empirical": path_emp, "status": path_norm["status"], "classes": list(C.PATH_CLASSES)},
        "regimes": regimes,
        "models": metrics,
        "incremental": incremental,
        "baselines": baselines,
        "matched": compact,
        "transitions": trans,
        "robustness": robustness,
        "bootstrap": bootstrap,
        "negative_control": disc.get("negative_control"),
        "primary": disc.get("primary"),
        "examples": examples,
        "feature_families": C.FAMILIES,
        "primary_spec": C.PRIMARY,
        "layers": {
            "OBSERVED_DATA": "as-of PADE clocks, prices, and candle-path labels",
            "MODEL_OUTPUT": "TRAIN-fit nested logits / multinomial path class — evaluation only",
            "THEORETICAL_INFERENCE": "matched-price distributional contrasts — not a policy",
            "UNOBSERVED_EXECUTION": "no fills, maker/IOC executability, or live orders",
        },
        "limitations": [
            "One-minute candles. Repeated candles are observed outcomes, not independent updates.",
            "Same-possession dual 10¢ hit is AMBIGUOUS — no intraminute order is claimed.",
            "Clock horizons use elapsed game seconds because remaining clock is not monotonic.",
            "Rows within a trade are clustered; bootstrap is game-level.",
            "No L2. No fills. Forward distribution ≠ tradable edge.",
        ],
    }
    export(dash)

    untouched = {
        "pade": I.assert_untouched(gate_b),
        "v2": I.assert_untouched(gate_c),
        "v3": I.assert_untouched(gate_d),
    }
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
        "input_paths": {"pade": str(C.PADE_OUT), "dre_v2": str(C.V2_OUT), "dre_v3": str(C.V3_OUT), "out": str(C.OUT)},
        "input_hashes": {
            "pade": {f["name"]: f.get("sha256_16") for f in gate_b.get("files") or []},
            "v2": {f["name"]: f.get("sha256_16") for f in gate_c.get("files") or []},
            "v3": {f["name"]: f.get("sha256_16") for f in gate_d.get("files") or []},
        },
        "row_counts": counts,
        "universe": {k: universe[k] for k in universe if k != "unresolved"},
        "split_counts": counts["splits"],
        "model_configurations": tune,
        "selected_hyperparameters": tune.get("selected"),
        "gates": {k: (v.get("status") if isinstance(v, dict) else v) for k, v in gates.items()},
        "headline": disc["verdict"].get("HEADLINE"),
        "questions": disc["questions"],
        "untouched": untouched,
        "output_hashes": {
            "03_state_panel.parquet": C.sha256_prefix(C.OUT / "03_state_panel.parquet"),
            "15_discovery_verdict.json": C.sha256_prefix(C.OUT / "15_discovery_verdict.json"),
            "01_run_manifest.json": None,
        },
        "warnings": {
            "small_sample_slices": len(matched.get("excluded") or []),
            "unresolved_trades": universe.get("unresolved_n"),
            "clock_horizon_basis": "elapsed_game_seconds",
            "candle_ordering": "AMBIGUOUS is an explicit category",
        },
    }
    C.write_json(C.OUT / "01_run_manifest.json", manifest)
    # refresh hash after write
    manifest["output_hashes"]["01_run_manifest.json"] = C.sha256_prefix(C.OUT / "01_run_manifest.json")
    C.write_json(C.OUT / "01_run_manifest.json", manifest)

    C.log(f"done in {elapsed:.1f}s headline={disc['verdict'].get('HEADLINE')}")
    print(disc["verdict"].get("HEADLINE"))
    print("LIVE DEPLOYMENT: NOT AUTHORIZED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as e:
        C.log(f"HALT RuntimeError: {e}")
        C.OUT.mkdir(parents=True, exist_ok=True)
        C.write_json(C.OUT / "01_run_manifest.json", {"status": "HALT", "error": str(e), "banner": C.BANNER})
        raise
