"""One-command synthetic E2E. Writes artifacts/walkforward/summary.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from roller.nba_path_fe.config import DEFAULT, PathFeConfig
from roller.nba_path_fe.episodes import build_episodes
from roller.nba_path_fe.features import build_enter_features
from roller.nba_path_fe.hedge import build_hedge_features
from roller.nba_path_fe.ingest import WAREHOUSE_SOURCE, attach_pbp_state, ingest_warehouse, load_raw
from roller.nba_path_fe.labels import build_labels
from roller.nba_path_fe.leakage import assert_no_post_ts_leakage
from roller.nba_path_fe.paths import (
    artifacts_dir,
    episodes_dir,
    features_dir,
    labels_dir,
    raw_data_dir,
    walkforward_summary_path,
)
from roller.nba_path_fe.registry import load_registry
from roller.nba_path_fe.synthetic import generate_games
from roller.nba_path_fe.tau_policy import raw_warehouse_present
from roller.nba_path_fe.decision_grid import CONCLUSION, run_decision_grid
from roller.nba_path_fe.ingest import WAREHOUSE_SOURCE
from roller.nba_path_fe.walkforward import run_walkforward


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    def conv(o: Any) -> Any:
        if isinstance(o, float) and (o != o):  # NaN
            return None
        if isinstance(o, dict):
            return {str(k): conv(v) for k, v in o.items()}
        if isinstance(o, list):
            return [conv(v) for v in o]
        if hasattr(o, "item"):
            try:
                return o.item()
            except Exception:
                return o
        return o

    path.write_text(json.dumps(conv(obj), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_synthetic_e2e(cfg: PathFeConfig = DEFAULT, *, leakage: bool = True) -> dict[str, Any]:
    load_registry()
    ticks, games = generate_games(cfg)
    episodes = build_episodes(ticks, games, cfg)
    labels = build_labels(episodes, ticks, cfg)
    features, sf_meta = build_enter_features(episodes, ticks, labels, cfg)
    hedge = build_hedge_features(episodes, ticks, labels, cfg)
    leak = assert_no_post_ts_leakage(episodes, ticks, labels, cfg) if leakage else {"ok": None}
    raw_present = raw_warehouse_present(raw_data_dir())
    summary = run_walkforward(features, labels, cfg, raw_present=raw_present)
    summary["warehouse_gate"] = {
        "raw_present": raw_present,
        "ambition_claimable": bool(raw_present and cfg.source_tag != "SYNTHETIC_E2E"),
        "reason": (
            None
            if raw_present and cfg.source_tag != "SYNTHETIC_E2E"
            else "data/raw empty or SYNTHETIC_E2E; ambition metrics not claimable"
        ),
    }
    summary["state_fair"] = sf_meta
    summary["leakage"] = leak
    _attach_run_meta(summary, episodes, labels, games, features, hedge, cfg)
    _persist(episodes, labels, games, features, hedge, sf_meta, summary)
    return summary


def run_warehouse(*, leakage: bool = False, ingest: bool = True) -> dict[str, Any]:
    """Walk-forward on warehouse touch-80s. Not a synthetic re-tune."""
    load_registry()
    raw_present = raw_warehouse_present(raw_data_dir())
    if ingest or not raw_present:
        ingest_warehouse()
    ticks, games = load_raw()
    cfg = PathFeConfig(
        source_tag=WAREHOUSE_SOURCE,
        fill_rate=1.0,
        state_fair_version="v1_logistic_prior_yyyymm",
    )
    episodes = build_episodes(ticks, games, cfg)
    episodes = attach_pbp_state(episodes)
    labels = build_labels(episodes, ticks, cfg)
    features, sf_meta = build_enter_features(episodes, ticks, labels, cfg)
    hedge = build_hedge_features(episodes, ticks, labels, cfg)
    leak = assert_no_post_ts_leakage(episodes, ticks, labels, cfg) if leakage else {"ok": None}
    summary = run_walkforward(features, labels, cfg, raw_present=True)
    summary["warehouse_gate"] = {
        "raw_present": True,
        "ambition_claimable": True,
        "reason": None,
    }
    summary["state_fair"] = sf_meta
    summary["leakage"] = leak
    summary["label_basis"] = "candle_path_proxy"
    summary["candle_path_is_not_a_fill"] = True
    summary["l2"] = "SOURCE_UNAVAILABLE"
    _attach_run_meta(summary, episodes, labels, games, features, hedge, cfg)
    _persist(episodes, labels, games, features, hedge, sf_meta, summary)
    return summary


def _period_list(episodes: pd.DataFrame) -> list[int]:
    vals = pd.to_numeric(episodes["period"], errors="coerce").dropna().astype(int).unique()
    return sorted(int(v) for v in vals)


def _attach_run_meta(summary, episodes, labels, games, features, hedge, cfg) -> None:
    summary["n_episodes"] = int(len(episodes))
    summary["n_filled"] = int((labels["filled"] == 1).sum())
    summary["n_games"] = int(games["game_id"].nunique())
    summary["periods_stored"] = _period_list(episodes)
    summary["q2_policy_filter"] = bool(cfg.q2_policy_filter)
    summary["hedge_rows"] = int(len(hedge))
    summary["enter_skip_has_hedge_columns"] = any(c.startswith("hedge_") for c in features.columns)


def _persist(episodes, labels, games, features, hedge, sf_meta, summary) -> None:
    episodes_dir().mkdir(parents=True, exist_ok=True)
    features_dir().mkdir(parents=True, exist_ok=True)
    labels_dir().mkdir(parents=True, exist_ok=True)
    (artifacts_dir() / "pca").mkdir(parents=True, exist_ok=True)
    (artifacts_dir() / "knn").mkdir(parents=True, exist_ok=True)
    (artifacts_dir() / "clusters").mkdir(parents=True, exist_ok=True)
    episodes.to_parquet(episodes_dir() / "episodes.parquet", index=False)
    features.to_parquet(features_dir() / "enter_skip.parquet", index=False)
    hedge.to_parquet(features_dir() / "hedge_only.parquet", index=False)
    labels.to_parquet(labels_dir() / "labels.parquet", index=False)
    games.to_parquet(episodes_dir() / "games.parquet", index=False)
    _write_json(walkforward_summary_path(), summary)
    _write_json(artifacts_dir() / "pca" / "state_fair_meta.json", sf_meta)


def close_warehouse_decision_grid() -> dict[str, Any]:
    """One τ grid on frozen warehouse features. Then halt."""
    feat = pd.read_parquet(features_dir() / "enter_skip.parquet")
    lab = pd.read_parquet(labels_dir() / "labels.parquet")
    cfg = PathFeConfig(source_tag=WAREHOUSE_SOURCE, fill_rate=1.0, state_fair_version="v1_logistic_prior_yyyymm")
    grid = run_decision_grid(feat, lab, cfg)
    path = walkforward_summary_path()
    summary = json.loads(path.read_text(encoding="utf-8"))
    if grid["any_success"]:
        status = "CANDIDATE_DECISION_V1"
        rec = "Freeze winner τ as candidate_decision_v1. Promotion stays FAILED until fees + sealed holdout."
    else:
        status = "INACTIVE_NO_RESIDUAL_EDGE"
        rec = "Unfiltered touch-80 (desk 78–82 / bail-40 only). Second filter inactive."
    summary["conclusion"] = CONCLUSION
    summary["filter_status"] = status
    summary["recommended_research_policy"] = rec
    summary["decision_grid"] = grid
    summary["promotion"] = "FAILED"
    summary["warehouse_gate"] = {
        "raw_present": True,
        "ambition_claimable": False,
        "reason": f"filter_status={status}; p_K>=0.82 not claimable",
    }
    summary["ambition"] = {
        **summary.get("ambition", {}),
        "p_K": 0.82,
        "hit": False,
        "claimable": False,
        "next_milestone": "p_K > p0 with r in [0.12,0.25]; not p_K>=0.82",
    }
    _write_json(path, summary)
    return summary


def summary_path() -> Path:
    return walkforward_summary_path()
