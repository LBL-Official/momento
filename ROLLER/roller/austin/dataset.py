"""Build the 604-trade Austin dataset and path snapshots."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from roller.austin.bars_join import load_paths, parse_entry, split_post
from roller.austin.clock import parse_utc
from roller.austin.config import DEFAULT
from roller.austin.errors import AustinError
from roller.austin.features import build_feature_vector
from roller.austin.hedge import summarize_hedge, trade_hedge, trigger_resolution_audit
from roller.austin.instances import load_trades
from roller.austin.locks import N_Q2, N_Q3, N_TRADES, S_N
from roller.austin.outcomes import outcome_after_snapshot
from roller.austin.paths import coverage_path, dataset_dir, snapshots_path, trades_path
from roller.austin.pbp_join import load_pbp
from roller.austin.snapshots import snapshots_for_trade

GAP_SEC = 300


def classify_path(
    post: list,
    opponent: list,
    events: list,
) -> str:
    if not post:
        return "PATH_UNAVAILABLE"
    gap = False
    for prev, nxt in zip(post, post[1:]):
        if (nxt[0] - prev[0]).total_seconds() > GAP_SEC:
            gap = True
            break
    if not opponent or not events or gap:
        return "PATH_PARTIAL"
    return "PATH_COMPLETE"


def _flatten_features(bundle: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, cell in (bundle.get("features") or {}).items():
        out[name] = cell.get("value")
        out[f"{name}__status"] = cell.get("status")
    out["feature_coverage"] = bundle.get("feature_coverage")
    out["path_mode"] = bundle.get("path_mode")
    out["missing_features"] = "|".join(bundle.get("missing_features") or [])
    return out


def build_dataset() -> dict[str, Any]:
    trades = load_trades()
    paths = load_paths(trades)
    game_ids = {gid for gid in paths["internal_game_id"].values() if gid}
    pbp = load_pbp(game_ids) if game_ids else {}
    snap_rows: list[dict[str, Any]] = []
    hedge_rows: list[dict[str, Any]] = []
    path_status: dict[str, int] = {"PATH_COMPLETE": 0, "PATH_PARTIAL": 0, "PATH_UNAVAILABLE": 0}
    for trade in trades:
        ticker = trade["ticker"]
        fav = paths["favorite"].get(ticker, [])
        opp_ticker = paths["opponent_ticker"].get(ticker)
        opp = paths["favorite"].get(opp_ticker, []) if opp_ticker else []
        gid = paths["internal_game_id"].get(ticker)
        events = pbp.get(gid, []) if gid else []
        entry = parse_entry(trade)
        post = [] if entry is None else split_post(fav, entry)
        status = classify_path(post, opp, events)
        path_status[status] = path_status.get(status, 0) + 1
        hedge_rows.append(trade_hedge(trade, paths))
        for snap in snapshots_for_trade(trade, favorite_bars=fav, pbp_events=events):
            stamp = parse_utc(snap["available_at"])
            if stamp is None:
                continue
            feats = build_feature_vector(snap["raw"])
            if any(name.startswith("final_") or name == "settlement" for name in feats["feature_names"]):
                raise AustinError("LEAKAGE", "settlement leaked into features")
            outcome = outcome_after_snapshot(
                trade,
                snapshot_ts=stamp,
                favorite_post=post,
                opponent_post=[] if entry is None else split_post(opp, entry),
            )
            raw = snap["raw"]
            row = {
                "snapshot_id": snap["snapshot_id"],
                "trade_id": snap["trade_id"],
                "kind": snap["kind"],
                "available_at": snap["available_at"],
                "game_date": snap["game_date"],
                "calendar_month": snap["calendar_month"],
                "quarter": snap["quarter"],
                "slice": snap["slice"],
                "ticker": snap["ticker"],
                "path_complete": status == "PATH_COMPLETE",
                "path_status": status,
                "is_query": False,
                "query_mode": "POST_80",
                "entry_source": "CHOOSIN_604_CSV",
                "side": raw.side,
                "home_score_entry": raw.home_score_entry,
                "away_score_entry": raw.away_score_entry,
                "home_score_current": raw.home_score_current,
                "away_score_current": raw.away_score_current,
                "entry_quarter": raw.entry_quarter,
                "current_quarter": raw.current_quarter,
                "entry_seconds_remaining": raw.entry_seconds_remaining,
                "current_seconds_remaining": raw.current_seconds_remaining,
                "time_since_entry_sec": raw.time_since_entry_sec,
            }
            row.update(_flatten_features(feats))
            row.update(outcome)
            snap_rows.append(row)
    if len(trades) != N_TRADES:
        raise AustinError("LOCK_MISMATCH", f"built {len(trades)} trades")
    dataset_dir().mkdir(parents=True, exist_ok=True)
    trade_frame = pd.DataFrame(trades)
    snap_frame = pd.DataFrame(snap_rows)
    trade_frame.to_parquet(trades_path(), index=False)
    snap_frame.to_parquet(snapshots_path(), index=False)
    coverage = {
        "n_trades": len(trades),
        "n_q2": int((trade_frame["slice"] == "Q2").sum()),
        "n_q3": int((trade_frame["slice"] == "Q3").sum()),
        "n_survive": int((~trade_frame["t40"]).sum()) if "t40" in trade_frame else S_N,
        "n_path_complete": path_status["PATH_COMPLETE"],
        "n_path_partial": path_status["PATH_PARTIAL"],
        "n_path_unavailable": path_status["PATH_UNAVAILABLE"],
        "n_knn_observations": int(len(snap_frame)),
        "n_entry_snapshots": int((snap_frame["kind"] == "entry").sum()) if not snap_frame.empty else 0,
        "path_complete_definition": "favorite 1m path after entry, opponent joined, PBP present, no gap > 300s",
        "hedge_trigger_resolution": trigger_resolution_audit(trades, paths),
        "locks": {"n": N_TRADES, "q2": N_Q2, "q3": N_Q3, "s": S_N},
        "pbp_status": DEFAULT.pbp_status,
        "l2_status": DEFAULT.l2_status,
        "fill_status": DEFAULT.fill_status,
        "live_feed": DEFAULT.live_feed,
        "data_mode": DEFAULT.data_mode,
    }
    if coverage["n_trades"] != N_TRADES or coverage["n_q2"] != N_Q2 or coverage["n_q3"] != N_Q3:
        raise AustinError("LOCK_MISMATCH", f"coverage {coverage}")
    coverage_path().write_text(json.dumps(coverage, indent=2) + "\n", encoding="utf-8")
    return {
        "trades": trades,
        "snapshots": snap_frame,
        "hedge_rows": hedge_rows,
        "hedge_summary": summarize_hedge(hedge_rows, resolution=trigger_resolution_audit(trades, paths)),
        "coverage": coverage,
    }
