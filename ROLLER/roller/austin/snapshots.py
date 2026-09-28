"""Build entry + path snapshots. FINAL settlement price never enters features."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from roller.austin.bars_join import (
    first_close_at_or_below,
    parse_entry,
    split_post,
)
from roller.austin.config import DEFAULT, AustinConfig
from roller.austin.pbp_join import state_at
from roller.austin.raw_state import PathPoint, RawState


def snapshot_id(trade_id: str, stamp: str, kind: str) -> str:
    raw = f"{trade_id}|{stamp}|{kind}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _iso(stamp: datetime) -> str:
    return stamp.astimezone(timezone.utc).isoformat()


def _score_from_pbp(pbp_row: dict[str, Any] | None, trade: dict[str, Any], *, at_entry: bool) -> tuple[int | None, int | None, int | None, int | None]:
    if pbp_row is not None:
        return (
            pbp_row.get("home_score"),
            pbp_row.get("away_score"),
            pbp_row.get("period"),
            pbp_row.get("seconds_remaining"),
        )
    if at_entry:
        sec = trade.get("entry_seconds_remaining")
        try:
            sec_i = int(sec) if sec is not None else None
        except (TypeError, ValueError):
            sec_i = None
        return (
            trade.get("home_score_entry"),
            trade.get("away_score_entry"),
            trade.get("quarter"),
            sec_i,
        )
    return None, None, None, None


def build_raw_for_snapshot(
    trade: dict[str, Any],
    *,
    kind: str,
    stamp: datetime,
    price_cents: int,
    path_to_t: list[PathPoint],
    pbp_row: dict[str, Any] | None,
    entry_ts: datetime,
) -> RawState:
    home, away, quarter, sec_left = _score_from_pbp(pbp_row, trade, at_entry=kind == "entry")
    wall = max(0, int((stamp - entry_ts).total_seconds()))
    return RawState(
        is_query=False,
        trade_id=str(trade["trade_id"]),
        side=str(trade["entry_side"]),
        entry_price_cents=int(trade["entry_price_cents"]),
        current_price_cents=int(price_cents),
        home_score_entry=trade.get("home_score_entry"),
        away_score_entry=trade.get("away_score_entry"),
        home_score_current=home,
        away_score_current=away,
        entry_quarter=trade.get("quarter"),
        current_quarter=quarter if quarter is not None else trade.get("quarter"),
        entry_seconds_remaining=_as_int(trade.get("entry_seconds_remaining")),
        current_seconds_remaining=sec_left,
        time_since_entry_sec=0 if kind == "entry" else wall,
        lookbacks=[],
        path_to_t=path_to_t,
        snapshot_kind=kind,
        availability_timestamp=_iso(stamp),
        query_mode="POST_80",
        query_source="HISTORICAL_RECONSTRUCT",
        entry_source="CHOOSIN_604_CSV",
        ticker=str(trade.get("ticker") or ""),
        event_id=str(trade.get("event_id") or ""),
        snapshot_id=snapshot_id(str(trade["trade_id"]), _iso(stamp), kind),
    )


def _as_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def snapshots_for_trade(
    trade: dict[str, Any],
    *,
    favorite_bars: list[tuple[datetime, float, float, float]],
    pbp_events: list[dict[str, Any]],
    cfg: AustinConfig = DEFAULT,
) -> list[dict[str, Any]]:
    entry_ts = parse_entry(trade)
    if entry_ts is None:
        return []
    post = split_post(favorite_bars, entry_ts)
    points: list[tuple[str, datetime, int]] = [
        ("entry", entry_ts, int(trade["entry_price_cents"])),
    ]
    stride = max(1, int(cfg.snapshot_stride))
    for i, row in enumerate(post):
        if i % stride != 0:
            continue
        points.append(("path", row[0], int(round(row[1]))))
    for trigger, kind in ((42, "hedge_42"), (41, "hedge_41")):
        hit = first_close_at_or_below(post, float(trigger))
        if hit is not None:
            points.append((kind, hit[0], int(round(hit[1]))))
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for kind, stamp, price in points:
        key = (kind, _iso(stamp))
        if key in seen:
            continue
        seen.add(key)
        path_to_t: list[PathPoint] = [
            PathPoint(t_sec=0, price_cents=int(trade["entry_price_cents"]),
                      home_score=trade.get("home_score_entry"),
                      away_score=trade.get("away_score_entry")),
        ]
        for row in post:
            if row[0] > stamp:
                break
            pbp = state_at(pbp_events, row[0])
            path_to_t.append(
                PathPoint(
                    t_sec=max(0, int((row[0] - entry_ts).total_seconds())),
                    price_cents=int(round(row[1])),
                    home_score=None if pbp is None else pbp.get("home_score"),
                    away_score=None if pbp is None else pbp.get("away_score"),
                )
            )
        raw = build_raw_for_snapshot(
            trade,
            kind=kind,
            stamp=stamp,
            price_cents=price,
            path_to_t=path_to_t,
            pbp_row=state_at(pbp_events, stamp),
            entry_ts=entry_ts,
        )
        out.append(
            {
                "snapshot_id": snapshot_id(str(trade["trade_id"]), _iso(stamp), kind),
                "trade_id": trade["trade_id"],
                "kind": kind,
                "available_at": _iso(stamp),
                "game_date": trade["game_date"],
                "calendar_month": trade["calendar_month"],
                "quarter": trade["quarter"],
                "slice": trade["slice"],
                "ticker": trade["ticker"],
                "raw": raw,
                "path_complete": bool(post),
            }
        )
    return out
