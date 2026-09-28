"""Build 78/67 snapshots. Feature distance_from_78 is entry cents minus 78."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from roller.austin.bars_join import first_close_at_or_below, load_paths, parse_entry, split_post
from roller.austin.config import DEFAULT
from roller.austin.errors import AustinError
from roller.austin.features import build_feature_vector
from roller.austin.pbp_join import load_pbp, state_at
from roller.austin.raw_state import PathPoint, RawState
from roller.austin.snapshots import snapshot_id
from roller.austin_first78.config import CFG, ENTRY_CENTS, distance_from_78
from roller.austin_first78.hedge import summarize_hedge, trade_hedge, trigger_resolution_audit
from roller.austin_first78.outcomes import outcome_after_snapshot
from roller.austin_first78.paths import coverage_path, dataset_dir, snapshots_path, trades_path
from roller.austin_first78.trades import load_nba_trades

GAP_SEC = 300


def _iso(stamp: datetime) -> str:
    return stamp.astimezone(timezone.utc).isoformat()


def _classify(post: list, opponent: list, events: list) -> str:
    if not post:
        return "PATH_UNAVAILABLE"
    gap = any((nxt[0] - prev[0]).total_seconds() > GAP_SEC for prev, nxt in zip(post, post[1:]))
    if not opponent or not events or gap:
        return "PATH_PARTIAL"
    return "PATH_COMPLETE"


def _flatten(bundle: dict[str, Any], entry_cents: float | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, cell in (bundle.get("features") or {}).items():
        out[name] = cell.get("value")
        out[f"{name}__status"] = cell.get("status")
    dist = distance_from_78(entry_cents)
    out["distance_from_78"] = dist
    out["distance_from_78__status"] = "VALUE" if dist is not None else "NOT_APPLICABLE"
    out["feature_coverage"] = bundle.get("feature_coverage")
    out["path_mode"] = bundle.get("path_mode")
    return out


def _raw(trade: dict[str, Any], *, kind: str, stamp: datetime, price: int, path: list[PathPoint], pbp_row, entry_ts: datetime) -> RawState:
    home = None if pbp_row is None else pbp_row.get("home_score")
    away = None if pbp_row is None else pbp_row.get("away_score")
    quarter = None if pbp_row is None else pbp_row.get("period")
    sec_left = None if pbp_row is None else pbp_row.get("seconds_remaining")
    wall = 0 if kind == "entry" else max(0, int((stamp - entry_ts).total_seconds()))
    return RawState(
        is_query=False,
        trade_id=str(trade["trade_id"]),
        side=str(trade["entry_side"]),
        entry_price_cents=int(trade["entry_price_cents"]),
        current_price_cents=int(price),
        home_score_entry=trade.get("home_score_entry"),
        away_score_entry=trade.get("away_score_entry"),
        home_score_current=home,
        away_score_current=away,
        entry_quarter=trade.get("quarter"),
        current_quarter=quarter if quarter is not None else trade.get("quarter"),
        entry_seconds_remaining=trade.get("entry_seconds_remaining"),
        current_seconds_remaining=sec_left,
        time_since_entry_sec=wall,
        path_to_t=path,
        snapshot_kind=kind,
        availability_timestamp=_iso(stamp),
        query_mode="POST_80",
        query_source="HISTORICAL_RECONSTRUCT",
        entry_source="NONE",
        ticker=str(trade["ticker"]),
        event_id=str(trade.get("event_id") or ""),
    )


def build_dataset(*, progress=print) -> dict[str, Any]:
    trades, exclusions = load_nba_trades(progress=progress)
    if not trades:
        raise AustinError("DATA_REQUIRED", "no NBA 2Q/3Q 78¢ crosses")
    paths = load_paths(trades)
    game_ids = {gid for gid in paths["internal_game_id"].values() if gid}
    pbp = load_pbp(game_ids) if game_ids else {}
    snap_rows: list[dict[str, Any]] = []
    hedge_rows: list[dict[str, Any]] = []
    path_status = {"PATH_COMPLETE": 0, "PATH_PARTIAL": 0, "PATH_UNAVAILABLE": 0}
    for index, trade in enumerate(trades, start=1):
        if progress and index % 50 == 0:
            progress(f"snapshots {index}/{len(trades)}")
        ticker = trade["ticker"]
        fav = paths["favorite"].get(ticker, [])
        opp_ticker = paths["opponent_ticker"].get(ticker)
        opp = paths["favorite"].get(opp_ticker, []) if opp_ticker else []
        gid = paths["internal_game_id"].get(ticker)
        events = pbp.get(gid, []) if gid else []
        entry_ts = parse_entry(trade)
        post = [] if entry_ts is None else split_post(fav, entry_ts)
        status = _classify(post, opp, events)
        path_status[status] = path_status.get(status, 0) + 1
        if events and entry_ts is not None and trade.get("home_score_entry") is None:
            entry_pbp = state_at(events, entry_ts)
            if entry_pbp is not None:
                trade["home_score_entry"] = entry_pbp.get("home_score")
                trade["away_score_entry"] = entry_pbp.get("away_score")
                trade["entry_seconds_remaining"] = entry_pbp.get("seconds_remaining")
                if entry_pbp.get("period") is not None:
                    trade["quarter"] = entry_pbp.get("period")
        hedge_rows.append(trade_hedge(trade, paths))
        if entry_ts is None:
            continue
        points: list[tuple[str, datetime, int]] = [("entry", entry_ts, int(trade["entry_price_cents"]))]
        stride = max(1, int(CFG.snapshot_stride))
        for i, row in enumerate(post):
            if i % stride == 0:
                points.append(("path", row[0], int(round(row[1]))))
        for trigger, kind in ((69, "hedge_69"), (68, "hedge_68")):
            hit = first_close_at_or_below(post, float(trigger))
            if hit is not None:
                points.append((kind, hit[0], int(round(hit[1]))))
        seen: set[tuple[str, str]] = set()
        for kind, stamp, price in points:
            key = (kind, _iso(stamp))
            if key in seen:
                continue
            seen.add(key)
            path_to_t = [
                PathPoint(
                    t_sec=0,
                    price_cents=int(trade["entry_price_cents"]),
                    home_score=trade.get("home_score_entry"),
                    away_score=trade.get("away_score_entry"),
                )
            ]
            for row in post:
                if row[0] > stamp:
                    break
                pbp_row = state_at(events, row[0])
                path_to_t.append(
                    PathPoint(
                        t_sec=max(0, int((row[0] - entry_ts).total_seconds())),
                        price_cents=int(round(row[1])),
                        home_score=None if pbp_row is None else pbp_row.get("home_score"),
                        away_score=None if pbp_row is None else pbp_row.get("away_score"),
                    )
                )
            pbp_now = state_at(events, stamp)
            raw = _raw(trade, kind=kind, stamp=stamp, price=price, path=path_to_t, pbp_row=pbp_now, entry_ts=entry_ts)
            feats = build_feature_vector(raw)
            if "distance_from_78" in feats["feature_names"]:
                raise AustinError("LEAKAGE", "distance_from_78 must be added by this fit, not the 604 builder")
            outcome = outcome_after_snapshot(trade, snapshot_ts=stamp, favorite_post=post)
            row = {
                "snapshot_id": snapshot_id(trade["trade_id"], _iso(stamp), kind),
                "trade_id": trade["trade_id"],
                "kind": kind,
                "available_at": _iso(stamp),
                "game_date": trade["game_date"],
                "calendar_month": trade["calendar_month"],
                "quarter": trade.get("quarter"),
                "slice": trade["slice"],
                "ticker": ticker,
                "path_status": status,
                "query_mode": "POST_78",
                "entry_source": "DERIVED_FOUR_FIRST78",
                "entry_price_cents": int(trade["entry_price_cents"]),
                "current_price_cents": int(price),
            }
            row.update(_flatten(feats, float(trade["entry_price_cents"])))
            row.update(outcome)
            snap_rows.append(row)
    frame = pd.DataFrame(snap_rows)
    trade_frame = pd.DataFrame(trades)
    dataset_dir().mkdir(parents=True, exist_ok=True)
    trade_frame.to_parquet(trades_path(), index=False)
    frame.to_parquet(snapshots_path(), index=False)
    q2 = int((trade_frame["slice"] == "Q2").sum())
    q3 = int((trade_frame["slice"] == "Q3").sum())
    stopped = int(trade_frame["t67"].sum())
    coverage = {
        "n_trades": int(len(trades)),
        "n_q2": q2,
        "n_q3": q3,
        "n_t67": stopped,
        "n_survive": int(len(trades) - stopped),
        "n_path_complete": path_status["PATH_COMPLETE"],
        "n_path_partial": path_status["PATH_PARTIAL"],
        "n_path_unavailable": path_status["PATH_UNAVAILABLE"],
        "n_knn_observations": int(len(frame)),
        "n_entry_snapshots": int((frame["kind"] == "entry").sum()) if not frame.empty else 0,
        "exclusions": exclusions,
        "population": "NBA_2Q3Q_FIRST78",
        "entry_cents": ENTRY_CENTS,
        "stop_cents": 67,
        "n_is_604": False,
        "hedge_trigger_resolution": trigger_resolution_audit(trades, paths),
        "pbp_status": DEFAULT.pbp_status,
        "l2_status": DEFAULT.l2_status,
        "fill_status": DEFAULT.fill_status,
        "live_feed": DEFAULT.live_feed,
        "data_mode": DEFAULT.data_mode,
        "note": "NBA 2Q/3Q contracts from the derived four with a 78¢ up-cross. N is observed.",
    }
    coverage_path().write_text(json.dumps(coverage, indent=2) + "\n", encoding="utf-8")
    return {
        "trades": trades,
        "snapshots": frame,
        "hedge_summary": summarize_hedge(hedge_rows, resolution=coverage["hedge_trigger_resolution"]),
        "coverage": coverage,
    }
