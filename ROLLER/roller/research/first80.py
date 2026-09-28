"""Frozen FIRST80 book objects. Research only. Not live FIRST01.

Trigger: first tradable close ≥80 after a prior tradable close <80, one per
event. Same-timestamp tie → exclude. T40 is the first later tradable close ≤40.
W is Kalshi ticker expiration, not box home_win. Candle path ≠ fill.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from roller.admin import load_dataset, load_identity
from roller.config import RollerConfig
from roller.io_csv import write_csv
from roller.paths import derived_dir
from roller.point_in_time.filters import AsOfRequiredError
from roller.research.game_window import game_window
from roller.research.quality import HIT40, HIT80, quality
from roller.state.clock import ASKED_SIX
from roller.state.clock_snap import snap_events
from roller.timeutil import parse_utc, resolve_cutoff, to_iso

FIRST80_RULE_VERSION = "frozen_v1"
FIRST80_COLUMNS = [
    "internal_game_id",
    "sport",
    "season",
    "event_ticker",
    "ticker",
    "team_side",
    "status",
    "first_80_timestamp",
    "first_80_bid_close",
    "first_80_ask_close",
    "first_80_spread_e4",
    "first_80_volume",
    "t40_timestamp",
    "t40_bid_close",
    "kalshi_yes_settled",
    "kalshi_result",
    "settlement_value_e4",
    "game_window_start",
    "game_window_end",
    "entry_slice",
    "entry_period",
    "entry_clock",
    "period_remaining_s",
    "asked_six",
    "contains_future_information",
    "available_at",
    "t40_available_at",
    "settlement_available_at",
    "rule_version",
    "note",
]


def _int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _iso_flag(value: Any) -> str:
    if value in (True, 1, "1", "true", "True", "yes"):
        return "1"
    if value in (False, 0, "0", "false", "False", "no"):
        return "0"
    return ""


def settled_yes(result: Any, settlement_value_e4: Any) -> str:
    if result == "yes":
        return "1"
    if result == "no":
        return "0"
    sv = _int(settlement_value_e4)
    if sv == 10000:
        return "1"
    if sv == 0:
        return "0"
    return ""


def _in_window(ts: datetime | None, start: datetime | None, end: datetime | None) -> bool:
    if ts is None:
        return False
    if start is not None and ts < start:
        return False
    if end is not None and ts > end:
        return False
    return True


def scan_ticker(
    candles: list[dict[str, Any]],
    *,
    window_start: datetime | None,
    window_end: datetime | None,
) -> dict[str, Any]:
    rows = []
    for c in candles:
        ts = parse_utc(c.get("available_at") or c.get("candle_timestamp") or c.get("event_timestamp"))
        if not _in_window(ts, window_start, window_end):
            continue
        valid = c.get("is_valid")
        if valid in (False, 0, "0", "false", "False"):
            continue
        rows.append((ts, c))
    rows.sort(key=lambda item: (item[0], str(item[1].get("ticker") or "")))
    had_q = False
    seen_below = False
    f80: tuple[datetime, dict[str, Any]] | None = None
    for ts, c in rows:
        bid = _int(c.get("yes_bid_close"))
        ask = _int(c.get("yes_ask_close"))
        vol = _int(c.get("volume"))
        if not quality(bid, ask, vol, had_q):
            continue
        had_q = True
        if bid is not None and bid < HIT80:
            seen_below = True
        if f80 is None and bid is not None and bid >= HIT80 and seen_below:
            f80 = (ts, c)
    if f80 is None:
        return {"status": "NO_FIRST_80"}
    f80_ts, f80_c = f80
    t40: tuple[datetime, dict[str, Any]] | None = None
    for ts, c in rows:
        if ts <= f80_ts:
            continue
        bid = _int(c.get("yes_bid_close"))
        ask = _int(c.get("yes_ask_close"))
        vol = _int(c.get("volume"))
        if not quality(bid, ask, vol, True):
            continue
        if bid is not None and bid <= HIT40:
            t40 = (ts, c)
            break
    bid = _int(f80_c.get("yes_bid_close"))
    ask = _int(f80_c.get("yes_ask_close"))
    return {
        "status": "FIRST_80",
        "first_80_timestamp": to_iso(f80_ts),
        "first_80_bid_close": "" if bid is None else str(bid),
        "first_80_ask_close": "" if ask is None else str(ask),
        "first_80_spread_e4": "" if bid is None or ask is None else str(ask - bid),
        "first_80_volume": "" if _int(f80_c.get("volume")) is None else str(_int(f80_c.get("volume"))),
        "t40_timestamp": "" if t40 is None else to_iso(t40[0]),
        "t40_bid_close": "" if t40 is None or _int(t40[1].get("yes_bid_close")) is None else str(_int(t40[1].get("yes_bid_close"))),
        "ticker": f80_c.get("ticker") or "",
        "team_side": f80_c.get("team_side") or "",
    }


def _empty_row(game: dict[str, Any], *, status: str) -> dict[str, Any]:
    start, end = game_window(game.get("game_date"))
    return {
        "internal_game_id": game.get("internal_game_id") or "",
        "sport": game.get("sport") or "",
        "season": game.get("season") or "",
        "event_ticker": game.get("event_ticker") or "",
        "ticker": "",
        "team_side": "",
        "status": status,
        "first_80_timestamp": "",
        "first_80_bid_close": "",
        "first_80_ask_close": "",
        "first_80_spread_e4": "",
        "first_80_volume": "",
        "t40_timestamp": "",
        "t40_bid_close": "",
        "kalshi_yes_settled": "",
        "kalshi_result": "",
        "settlement_value_e4": "",
        "game_window_start": start,
        "game_window_end": end,
        "entry_slice": "UNALIGNED",
        "entry_period": "",
        "entry_clock": "",
        "period_remaining_s": "",
        "asked_six": "0",
        "contains_future_information": "1",
        "available_at": end or start,
        "t40_available_at": "",
        "settlement_available_at": "",
        "rule_version": FIRST80_RULE_VERSION,
        "note": "candle path; not a fill; W is Kalshi expiration",
    }


def build_first80_rows(
    *,
    sport: str,
    season: str,
    games: pd.DataFrame,
    candles: pd.DataFrame,
    markets: pd.DataFrame,
    pbp: pd.DataFrame,
) -> list[dict[str, Any]]:
    if games is None or games.empty:
        return []
    by_game_candles: dict[str, list[dict[str, Any]]] = {}
    if candles is not None and not candles.empty:
        for rec in candles.to_dict("records"):
            by_game_candles.setdefault(str(rec.get("internal_game_id") or ""), []).append(rec)
    by_ticker_mkt: dict[str, dict[str, Any]] = {}
    if markets is not None and not markets.empty:
        for rec in markets.to_dict("records"):
            by_ticker_mkt[str(rec.get("ticker") or "")] = rec
    by_game_pbp: dict[str, list[dict[str, Any]]] = {}
    if pbp is not None and not pbp.empty:
        for rec in pbp.to_dict("records"):
            by_game_pbp.setdefault(str(rec.get("internal_game_id") or ""), []).append(rec)

    rows: list[dict[str, Any]] = []
    for game in games.to_dict("records"):
        if sport == "NCAAB" and str(game.get("p5_vs_p5") or "") != "1":
            continue
        gid = str(game.get("internal_game_id") or "")
        start_s, end_s = game_window(game.get("game_date"))
        start = parse_utc(start_s) if start_s else None
        end = parse_utc(end_s) if end_s else None
        mkt_close = None
        event_markets = [
            m
            for m in by_ticker_mkt.values()
            if str(m.get("internal_game_id") or "") == gid or str(m.get("event_ticker") or "") == str(game.get("event_ticker") or "")
        ]
        for m in event_markets:
            close = parse_utc(m.get("close_time") or m.get("expiration_time"))
            if close is not None:
                mkt_close = close if mkt_close is None else min(mkt_close, close)
        scan_end = end
        if mkt_close is not None:
            scan_end = mkt_close if scan_end is None else min(scan_end, mkt_close)

        hits: list[dict[str, Any]] = []
        grouped: dict[str, list[dict[str, Any]]] = {}
        for c in by_game_candles.get(gid, []):
            grouped.setdefault(str(c.get("ticker") or ""), []).append(c)
        for ticker, trows in grouped.items():
            scanned = scan_ticker(trows, window_start=start, window_end=scan_end)
            if scanned.get("status") == "FIRST_80":
                scanned["ticker"] = scanned.get("ticker") or ticker
                hits.append(scanned)
        hits.sort(key=lambda h: (str(h.get("first_80_timestamp") or ""), str(h.get("ticker") or "")))
        if not hits:
            rows.append(_empty_row(game, status="NO_FIRST_80"))
            continue
        first_ts = hits[0]["first_80_timestamp"]
        tied = [h for h in hits if h["first_80_timestamp"] == first_ts]
        if len(tied) > 1:
            rec = _empty_row(game, status="TIE_SAME_MINUTE")
            rec["available_at"] = first_ts
            rows.append(rec)
            continue
        hit = hits[0]
        rec = _empty_row(game, status="FIRST_80")
        rec.update({k: hit.get(k, rec.get(k)) for k in hit})
        rec["game_window_start"] = start_s
        rec["game_window_end"] = end_s
        rec["available_at"] = hit["first_80_timestamp"]
        rec["t40_available_at"] = hit.get("t40_timestamp") or ""
        mkt = by_ticker_mkt.get(str(hit.get("ticker") or ""), {})
        rec["kalshi_result"] = mkt.get("result") or ""
        rec["settlement_value_e4"] = "" if mkt.get("settlement_value_e4") in (None, "") else str(mkt.get("settlement_value_e4"))
        rec["kalshi_yes_settled"] = settled_yes(mkt.get("result"), mkt.get("settlement_value_e4"))
        rec["settlement_available_at"] = mkt.get("result_available_at") or mkt.get("settlement_time") or mkt.get("close_time") or ""
        snap_ts = parse_utc(hit["first_80_timestamp"])
        events = by_game_pbp.get(gid, [])
        if snap_ts is not None:
            snap = snap_events(events, snap_ts, sport=sport)
            rec["entry_slice"] = snap.get("slice") or "UNALIGNED"
            rec["entry_period"] = "" if snap.get("period") in (None, "") else str(snap.get("period"))
            rec["entry_clock"] = snap.get("clock") or ""
            rem = snap.get("period_remaining_s")
            rec["period_remaining_s"] = "" if rem in (None, "") else str(rem)
            rec["asked_six"] = "1" if rec["entry_slice"] in ASKED_SIX else "0"
        rows.append(rec)
    return rows


def write_first80(cfg: RollerConfig, sport: str, season: str) -> pd.DataFrame:
    path_key = cfg.season_meta(sport, season)["path_key"]
    out_path = derived_dir(cfg.root, sport, path_key) / "first80_triggers.csv"
    try:
        games = load_dataset(cfg, sport, season, "games")
    except (FileNotFoundError, KeyError):
        empty = pd.DataFrame(columns=FIRST80_COLUMNS)
        write_csv(out_path, empty, FIRST80_COLUMNS)
        return empty
    try:
        candles = load_dataset(cfg, sport, season, "kalshi_candles")
    except (FileNotFoundError, KeyError):
        candles = pd.DataFrame()
    try:
        markets = load_dataset(cfg, sport, season, "kalshi_markets")
    except (FileNotFoundError, KeyError):
        markets = pd.DataFrame()
    try:
        pbp = load_dataset(cfg, sport, season, "pbp")
    except (FileNotFoundError, KeyError):
        pbp = pd.DataFrame()
    rows = build_first80_rows(
        sport=sport,
        season=season,
        games=games,
        candles=candles,
        markets=markets,
        pbp=pbp,
    )
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=FIRST80_COLUMNS)
    else:
        df = df[FIRST80_COLUMNS]
    write_csv(out_path, df, FIRST80_COLUMNS)
    return df


def mask_first80_row(row: dict[str, Any], cutoff: datetime) -> dict[str, Any]:
    out = dict(row)
    first_at = parse_utc(row.get("available_at") or row.get("first_80_timestamp"))
    if first_at is None or not (first_at < cutoff):
        return {
            **_empty_row(row, status="NOT_YET_VISIBLE"),
            "internal_game_id": row.get("internal_game_id") or "",
            "sport": row.get("sport") or "",
            "season": row.get("season") or "",
            "event_ticker": row.get("event_ticker") or "",
            "contains_future_information": True,
        }
    t40_at = parse_utc(row.get("t40_available_at") or row.get("t40_timestamp"))
    if t40_at is None or not (t40_at < cutoff):
        out["t40_timestamp"] = ""
        out["t40_bid_close"] = ""
    settle_at = parse_utc(row.get("settlement_available_at"))
    if settle_at is None or not (settle_at < cutoff):
        out["kalshi_yes_settled"] = ""
        out["kalshi_result"] = ""
        out["settlement_value_e4"] = ""
    out["contains_future_information"] = True
    return out


def load_first80(
    cfg: RollerConfig,
    *,
    internal_game_id: str | None = None,
    sport: str | None = None,
    season: str | None = None,
    as_of=None,
    end_of_day: bool = False,
    full_history: bool = False,
) -> dict[str, Any]:
    if as_of is None and not full_history:
        raise AsOfRequiredError("first80 requires as_of or full_history=True")
    ident = load_identity(cfg)
    if internal_game_id:
        hit = ident[ident["internal_game_id"] == internal_game_id]
        if hit.empty:
            raise KeyError(internal_game_id)
        rec = hit.iloc[0].to_dict()
        sport, season = rec["sport"], rec["season"]
    if not sport or not season:
        raise ValueError("first80 requires internal_game_id or sport+season")
    try:
        table = load_dataset(cfg, sport, season, "first80_triggers")
    except (FileNotFoundError, KeyError):
        table = pd.DataFrame(columns=FIRST80_COLUMNS)
    if internal_game_id and not table.empty:
        table = table[table["internal_game_id"] == internal_game_id]
    rows = table.to_dict("records") if not table.empty else []
    cutoff = None if full_history else resolve_cutoff(as_of, end_of_day=end_of_day)
    if cutoff is not None:
        rows = [mask_first80_row(r, cutoff) for r in rows]
    return {
        "sport": sport,
        "season": season,
        "internal_game_id": internal_game_id,
        "as_of": None if full_history else to_iso(cutoff),
        "contains_future_information": True,
        "rule_version": FIRST80_RULE_VERSION,
        "note": "FIRST80 is off O_t; T40/W are future; candle path ≠ fill",
        "rows": rows,
    }
