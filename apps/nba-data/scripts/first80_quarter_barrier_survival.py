#!/usr/bin/env python3
"""NBA FIRST80 quarter barrier survival (research only).

Splits the frozen n=1,230 FIRST80 universe by PBP quarter at entry, then
reports P(expire winner before close-touching 60/50/40) per quarter and the
game-clock remaining distribution at each nested close-path touch.

Does not change live FIRST01 / 80/81/83/89. Candle path, not fills.
Does not invent L2, queue, or future OT.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
GPE_DIR = SCRIPTS / "game_path_engine_v2"
if str(GPE_DIR) not in sys.path:
    sys.path.insert(0, str(GPE_DIR))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import nba_80_40_execution_audit as audit  # noqa: E402
from pbp import (  # noqa: E402
    box_header,
    classify_confidence,
    enrich_actions,
    game_seconds_elapsed,
    game_seconds_remaining,
    load_box,
    load_pbp,
    replay_residuals,
    snap_to_entry,
)

ROOT = audit.ROOT
NORM = audit.NORM
CANDIDATES_PATH = ROOT / "derived" / "nba" / "first80_execution_audit" / "candidates.json"
CANDLES_DIR = NORM / "candles_1m"
CROSSWALK_PATH = NORM / "pbp" / "game_crosswalk.json"
OUT = ROOT / "derived" / "nba" / "first80_quarter_barrier_survival"

EXPECTED_N = 1230
EXPECTED_W = 1019
EXPECTED_T40 = 320
EXPECTED_W_NOT_T40 = 910
EXPECTED_L_NOT_T40 = 0
# Universe-level v2 close-path joints (quality-filtered rescan may differ at 60/50).
EXPECTED_V2_W_NOT_T60 = 759
EXPECTED_V2_W_NOT_T50 = 855

LEVELS = (60, 50, 40)
LEVEL_E4 = {60: 6000, 50: 5000, 40: 4000}
ENTRY_CENTS = 80
SETTLE_YES_CENTS = 100
WIN_PNL_CENTS = SETTLE_YES_CENTS - ENTRY_CENTS  # +20¢
LOSE_HOLD_PNL_CENTS = 0 - ENTRY_CENTS  # −80¢
R_CENTS = audit.R_CENTS  # +1R = +20¢; 40-stop = −2R. Locked audit.
PRIMARY_ALIGN = {"HIGH", "MEDIUM"}
QUARTER_BUCKETS = ("Q1", "Q2", "Q3", "Q4")
PARTITION_BUCKETS = ("Q1", "Q2", "Q3", "Q4", "OT", "UNALIGNED")
REMAINING_HIST_BINS = (
    ("36:01–48:00", 36 * 60 + 1, 48 * 60 + 1),
    ("24:01–36:00", 24 * 60 + 1, 36 * 60 + 1),
    ("12:01–24:00", 12 * 60 + 1, 24 * 60 + 1),
    ("00:00–12:00", 0, 12 * 60 + 1),
)


class IdentityHalt(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_crosswalk() -> dict:
    rows = json.loads(CROSSWALK_PATH.read_text())
    return {r["event_id"]: r for r in rows}


def load_frozen_first80(path: Path | None = None) -> list[dict]:
    src = path or CANDIDATES_PATH
    cands = json.loads(src.read_text())
    return [
        dict(c)
        for c in cands
        if c.get("status") == "FIRST_80" and c.get("expiration_result_yes") is not None
    ]


def identity_of(trades: list[dict]) -> dict:
    n = len(trades)
    w = sum(1 for t in trades if t.get("expiration_result_yes") is True)
    t40 = sum(1 for t in trades if t.get("stop_close_triggered"))
    w_not = sum(
        1
        for t in trades
        if t.get("expiration_result_yes") is True and not t.get("stop_close_triggered")
    )
    l_not = sum(
        1
        for t in trades
        if t.get("expiration_result_yes") is False and not t.get("stop_close_triggered")
    )
    observed = {
        "n": n,
        "W": w,
        "T40": t40,
        "W_and_not_T40": w_not,
        "L_and_not_T40": l_not,
    }
    expected = {
        "n": EXPECTED_N,
        "W": EXPECTED_W,
        "T40": EXPECTED_T40,
        "W_and_not_T40": EXPECTED_W_NOT_T40,
        "L_and_not_T40": EXPECTED_L_NOT_T40,
    }
    return {
        "ok": observed == expected,
        "observed": observed,
        "expected": expected,
        "label": "CANDLE PATH — NOT ACTUAL FILL",
    }


def halt_unless_identity(trades: list[dict]) -> dict:
    gate = identity_of(trades)
    if not gate["ok"]:
        raise IdentityHalt(f"HALT frozen identity {gate}")
    return gate


def scan_window_end(rec: dict) -> int | None:
    gd = audit.parse_game_date(rec.get("game_date"))
    gw_end = int((gd + timedelta(hours=52)).timestamp()) if gd else None
    close_ts = rec.get("close_ts")
    close_i = int(close_ts) if close_ts is not None else None
    if close_i is None:
        return gw_end
    if gw_end is None:
        return close_i
    return min(close_i, gw_end)


def first_close_touches(
    quotes: list[dict],
    t0: int,
    scan_end: int | None = None,
) -> dict[int, int | None]:
    """First later tradable yes_bid_close ≤ L. Nested: 40 ⊂ 50 ⊂ 60."""
    found: dict[int, int | None] = {60: None, 50: None, 40: None}
    had_q = True
    for q in quotes:
        ts = int(q["ts"])
        if ts <= t0:
            continue
        if scan_end is not None and ts > scan_end:
            continue
        if not audit.quality(q.get("bid_c"), q.get("ask_c"), q.get("vol"), had_q):
            continue
        had_q = True
        c = q["bid_c"]
        if c is None:
            continue
        for cents, e4 in LEVEL_E4.items():
            if found[cents] is None and c <= e4:
                found[cents] = ts
        if all(v is not None for v in found.values()):
            break
    return found


def entry_bucket(confidence: str | None, phase: str | None, period: int | None) -> str:
    """Q1–Q4 / OT for HIGH+MEDIUM in-game snaps. Pre-tip and unusable → UNALIGNED."""
    if confidence not in PRIMARY_ALIGN:
        return "UNALIGNED"
    if phase in (None, "GAME_NOT_STARTED", "UNALIGNED"):
        return "UNALIGNED"
    if period is None:
        return "UNALIGNED"
    p = int(period)
    if p >= 5:
        return "OT"
    if 1 <= p <= 4:
        return f"Q{p}"
    return "UNALIGNED"


def format_clock(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    s = int(round(float(seconds)))
    if s < 0:
        s = 0
    return f"{s // 60:02d}:{s % 60:02d}"


def percentile(xs: list[float], p: float) -> float | None:
    ys = sorted(xs)
    if not ys:
        return None
    if len(ys) == 1:
        return float(ys[0])
    k = (len(ys) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(ys[int(k)])
    return float(ys[f] * (c - k) + ys[c] * (k - f))


def clock_stats(values: list[float]) -> dict:
    xs = [float(v) for v in values if v is not None]
    n = len(xs)
    if n == 0:
        return {
            "n": 0,
            "mean_s": None,
            "median_s": None,
            "sd_s": None,
            "p25_s": None,
            "p75_s": None,
            "iqr_s": None,
            "min_s": None,
            "max_s": None,
            "mean_clock": None,
            "median_clock": None,
            "sd_clock": None,
            "p25_clock": None,
            "p75_clock": None,
            "iqr_clock": None,
            "min_clock": None,
            "max_clock": None,
        }
    mean = statistics.mean(xs)
    median = statistics.median(xs)
    sd = statistics.stdev(xs) if n >= 2 else 0.0
    p25 = percentile(xs, 25)
    p75 = percentile(xs, 75)
    iqr = None if p25 is None or p75 is None else p75 - p25
    return {
        "n": n,
        "mean_s": round(mean, 3),
        "median_s": round(float(median), 3),
        "sd_s": round(sd, 3),
        "p25_s": None if p25 is None else round(p25, 3),
        "p75_s": None if p75 is None else round(p75, 3),
        "iqr_s": None if iqr is None else round(iqr, 3),
        "min_s": round(min(xs), 3),
        "max_s": round(max(xs), 3),
        "mean_clock": format_clock(mean),
        "median_clock": format_clock(median),
        "sd_clock": format_clock(sd),
        "p25_clock": format_clock(p25),
        "p75_clock": format_clock(p75),
        "iqr_clock": format_clock(iqr),
        "min_clock": format_clock(min(xs)),
        "max_clock": format_clock(max(xs)),
    }


def remaining_hist_bin(period: int | None, remaining_s: float | None) -> str | None:
    if remaining_s is None:
        return None
    if period is not None and int(period) >= 5:
        return "OT"
    for label, lo, hi in REMAINING_HIST_BINS:
        if lo <= remaining_s < hi:
            return label
    if remaining_s >= 48 * 60 + 1:
        return ">48:00"
    return "00:00–12:00"


def nested_ok(touches: dict[int, int | None]) -> bool:
    """T40 ⊆ T50 ⊆ T60 on timestamps: a later/deeper touch implies earlier levels."""
    t60, t50, t40 = touches.get(60), touches.get(50), touches.get(40)
    if t40 is not None and (t50 is None or t60 is None):
        return False
    if t50 is not None and t60 is None:
        return False
    if t60 is not None and t50 is not None and t50 < t60:
        return False
    if t50 is not None and t40 is not None and t40 < t50:
        return False
    return True


def regulation_remaining_formula_ok(period: int | None, period_remaining: float | None, game_remaining: float | None) -> bool:
    """Unused regulation only. Future OT is not added."""
    if period is None or period_remaining is None or game_remaining is None:
        return True
    expected = game_seconds_remaining(period, period_remaining)
    if expected is None:
        return True
    return abs(float(game_remaining) - float(expected)) < 1e-6


def snap_clock(actions: list[dict], ts: int) -> dict:
    snap = snap_to_entry(actions, int(ts))
    idx = snap.get("snap_idx")
    row = actions[idx] if idx is not None and 0 <= idx < len(actions) else None
    period = None if row is None else row.get("period")
    period_remaining = None if row is None else row.get("remaining_s")
    return {
        "phase": snap.get("game_phase"),
        "snap_idx": idx,
        "period": period,
        "period_remaining_s": period_remaining,
        "elapsed_s": None if row is None else row.get("elapsed_s"),
        "game_seconds_remaining": game_seconds_remaining(period, period_remaining),
        "game_seconds_elapsed": game_seconds_elapsed(period, period_remaining),
        "snap_modeled_wall_ts": snap.get("snap_modeled_wall_ts"),
    }


def align_entry(rec: dict, xwalk: dict, pbp_cache: dict) -> dict:
    event_id = rec.get("event_id")
    cw = xwalk.get(event_id) or {}
    nba_id = cw.get("nba_game_id")
    match_status = cw.get("match_status")
    entry_ts = int(rec["first_80_timestamp"])
    out = {
        "nba_game_id": nba_id,
        "crosswalk_status": match_status,
        "alignment_model": "PERIOD_BOUNDED_LINEAR_GAME_CLOCK",
        "alignment_confidence": "UNUSABLE",
        "alignment_reason": None,
        "entry_phase": "UNALIGNED",
        "entry_period": None,
        "entry_period_remaining_s": None,
        "entry_game_seconds_remaining": None,
        "entry_quarter_bucket": "UNALIGNED",
    }
    if match_status != "MATCHED" or not nba_id:
        out["alignment_reason"] = "UNMATCHED_CROSSWALK"
        return out
    packed = _pbp_pack(nba_id, pbp_cache)
    if packed is None:
        out["alignment_reason"] = "NO_PBP"
        return out
    actions, header = packed
    snap = snap_to_entry(actions, entry_ts)
    residuals = replay_residuals(actions)
    conf, reason = classify_confidence(actions, snap, entry_ts, header, residuals)
    clock = snap_clock(actions, entry_ts)
    out.update(
        {
            "alignment_confidence": conf,
            "alignment_reason": reason,
            "entry_phase": clock["phase"],
            "entry_period": clock["period"],
            "entry_period_remaining_s": clock["period_remaining_s"],
            "entry_game_seconds_remaining": clock["game_seconds_remaining"],
            "entry_quarter_bucket": entry_bucket(conf, clock["phase"], clock["period"]),
        }
    )
    return out


def _pbp_pack(nba_id: str, cache: dict) -> tuple[list[dict], dict] | None:
    if nba_id in cache:
        return cache[nba_id]
    pbp = load_pbp(nba_id)
    if not pbp:
        cache[nba_id] = None
        return None
    box = load_box(nba_id)
    header = box_header(box)
    actions = enrich_actions(pbp.get("game", {}).get("actions") or [], header)
    cache[nba_id] = (actions, header)
    return cache[nba_id]


def _pq():
    import pyarrow.parquet as pq  # local: warehouse already depends on pyarrow

    return pq


def load_ticker_quotes(path: Path) -> list[dict]:
    pq = _pq()
    cols = [
        "end_period_ts",
        "yes_bid_close_e4",
        "yes_ask_close_e4",
        "volume_hundredths",
        "is_valid",
    ]
    table = pq.read_table(path, columns=cols)
    get = {c: table.column(c) for c in cols}
    rows = []
    for i in range(table.num_rows):
        if not get["is_valid"][i].as_py():
            continue
        rows.append(
            {
                "ts": int(get["end_period_ts"][i].as_py()),
                "bid_c": audit._opt_int(get["yes_bid_close_e4"][i].as_py()),
                "ask_c": audit._opt_int(get["yes_ask_close_e4"][i].as_py()),
                "vol": audit._opt_int(get["volume_hundredths"][i].as_py()),
            }
        )
    rows.sort(key=lambda r: r["ts"])
    return rows


def candle_files_for(tickers: set[str]) -> list[Path]:
    return [p for p in CANDLES_DIR.rglob("*.parquet") if p.stem in tickers]


def rate(k: int, n: int) -> float | None:
    if n <= 0:
        return None
    return round(100.0 * k / n, 2)


def stop_pnl_cents(level: int) -> int:
    """Gross candle P&L if the 80¢ entry exits at close-touch L. Not a fill."""
    return int(level) - ENTRY_CENTS


def ev_stop_gross(n: int, n_survive_win: int, n_touch: int, level: int) -> dict:
    """Gross EV of buy@80 / stop-at-L / hold-to-100 if never touched.

    Fees unresolved. Fill at L is not proven. Survivors in this universe
    are all winners (every loser close-touches 40, hence 50 and 60).
    EV % of a $1 contract = cents per contract.
    """
    stop_pnl = stop_pnl_cents(level)
    if n <= 0:
        return {
            "n": 0,
            "n_survive_win": n_survive_win,
            "n_touch": n_touch,
            "level": level,
            "win_pnl_cents": WIN_PNL_CENTS,
            "stop_pnl_cents": stop_pnl,
            "sum_pnl_cents": 0,
            "ev_cents_per_contract": None,
            "ev_pct_of_1_dollar": None,
            "ev_pct_of_80_debit": None,
            "ev_R": None,
            "label": "GROSS CANDLE PATH — NOT A FILL — ZERO FEE",
        }
    total = n_survive_win * WIN_PNL_CENTS + n_touch * stop_pnl
    ev = total / n
    return {
        "n": n,
        "n_survive_win": n_survive_win,
        "n_touch": n_touch,
        "level": level,
        "win_pnl_cents": WIN_PNL_CENTS,
        "stop_pnl_cents": stop_pnl,
        "sum_pnl_cents": total,
        "ev_cents_per_contract": round(ev, 4),
        "ev_pct_of_1_dollar": round(ev, 4),
        "ev_pct_of_80_debit": round(ev / ENTRY_CENTS * 100.0, 4),
        "ev_R": round(ev / R_CENTS, 4),
        "label": "GROSS CANDLE PATH — NOT A FILL — ZERO FEE",
    }


def ev_hold_gross(n: int, n_win: int) -> dict:
    """Gross EV of buy@80 and hold to Kalshi settlement. No stop."""
    n_lose = n - n_win
    if n <= 0:
        return {
            "n": 0,
            "n_win": n_win,
            "n_lose": n_lose,
            "win_pnl_cents": WIN_PNL_CENTS,
            "lose_pnl_cents": LOSE_HOLD_PNL_CENTS,
            "sum_pnl_cents": 0,
            "ev_cents_per_contract": None,
            "ev_pct_of_1_dollar": None,
            "ev_pct_of_80_debit": None,
            "ev_R": None,
            "label": "GROSS CANDLE PATH — NOT A FILL — ZERO FEE",
        }
    total = n_win * WIN_PNL_CENTS + n_lose * LOSE_HOLD_PNL_CENTS
    ev = total / n
    return {
        "n": n,
        "n_win": n_win,
        "n_lose": n_lose,
        "win_pnl_cents": WIN_PNL_CENTS,
        "lose_pnl_cents": LOSE_HOLD_PNL_CENTS,
        "sum_pnl_cents": total,
        "ev_cents_per_contract": round(ev, 4),
        "ev_pct_of_1_dollar": round(ev, 4),
        "ev_pct_of_80_debit": round(ev / ENTRY_CENTS * 100.0, 4),
        "ev_R": round(ev / R_CENTS, 4),
        "label": "GROSS CANDLE PATH — NOT A FILL — ZERO FEE",
    }


def ev_touch_hold_gross(n_touch: int, n_win_and_touch: int) -> dict:
    """Hold-to-expiration EV on the close-touch subset only."""
    return ev_hold_gross(n_touch, n_win_and_touch)


def bucket_summary(rows: list[dict], bucket: str) -> dict:
    sub = [r for r in rows if r["entry_quarter_bucket"] == bucket]
    n = len(sub)
    w = sum(1 for r in sub if r["W"])
    levels = {}
    for lv in LEVELS:
        t_key = f"T{lv}"
        n_touch = sum(1 for r in sub if r[t_key])
        n_w_not = sum(1 for r in sub if r["W"] and not r[t_key])
        clocks = [
            r[f"t{lv}_remaining_s"]
            for r in sub
            if r[t_key] and r.get(f"t{lv}_remaining_s") is not None
        ]
        hist: dict[str, int] = defaultdict(int)
        for r in sub:
            if not r[t_key]:
                continue
            b = remaining_hist_bin(r.get(f"t{lv}_period"), r.get(f"t{lv}_remaining_s"))
            if b:
                hist[b] += 1
        n_w_and_t = sum(1 for r in sub if r["W"] and r[t_key])
        levels[str(lv)] = {
            "n_touch": n_touch,
            "n_no_touch": n - n_touch,
            "n_winner_before_touch": n_w_not,
            "n_win_and_touch": n_w_and_t,
            "pct_winner_before_touch": rate(n_w_not, n),
            "pct_touch": rate(n_touch, n),
            "pct_win_given_touch": rate(n_w_and_t, n_touch),
            "ev_stop": ev_stop_gross(n, n_w_not, n_touch, lv),
            "ev_touch_hold": ev_touch_hold_gross(n_touch, n_w_and_t),
            "clock": clock_stats(clocks),
            "remaining_hist": dict(hist),
        }
    nested = all(
        levels["40"]["n_touch"] <= levels["50"]["n_touch"] <= levels["60"]["n_touch"]
        for _ in (0,)
    )
    return {
        "bucket": bucket,
        "n": n,
        "n_winners": w,
        "pct_win": rate(w, n),
        "ev_hold": ev_hold_gross(n, w),
        "levels": levels,
        "nested_touch_ok": nested,
    }


def universe_joints(rows: list[dict]) -> dict:
    n = len(rows)
    out = {"n": n}
    for lv in LEVELS:
        t_key = f"T{lv}"
        n_touch = sum(1 for r in rows if r[t_key])
        n_w_not = sum(1 for r in rows if r["W"] and not r[t_key])
        out[f"T{lv}"] = n_touch
        out[f"W_and_not_T{lv}"] = n_w_not
        out[f"pct_W_and_not_T{lv}"] = rate(n_w_not, n)
    return out


def analyze(trades: list[dict] | None = None) -> dict:
    trades = trades if trades is not None else load_frozen_first80()
    identity = halt_unless_identity(trades)
    xwalk = load_crosswalk()
    pbp_cache: dict = {}
    needed = {t["ticker"] for t in trades if t.get("ticker")}
    files = candle_files_for(needed)
    quotes_by_ticker: dict[str, list] = {}
    print(f"candle files {len(files)} / needed {len(needed)}", flush=True)
    for i, path in enumerate(files, 1):
        if i == 1 or i == len(files) or i % 400 == 0:
            print(f"  scan {i}/{len(files)}", flush=True)
        quotes_by_ticker[path.stem] = load_ticker_quotes(path)

    t40_mismatch = []
    missing_candles = []
    rows = []
    for rec in trades:
        ticker = rec["ticker"]
        t0 = int(rec["first_80_timestamp"])
        align = align_entry(rec, xwalk, pbp_cache)
        quotes = quotes_by_ticker.get(ticker)
        if quotes is None:
            missing_candles.append(ticker)
            touches = {60: None, 50: None, 40: None}
        else:
            touches = first_close_touches(quotes, t0, scan_window_end(rec))
        frozen_t40 = bool(rec.get("stop_close_triggered"))
        rescanned_t40 = touches[40] is not None
        if frozen_t40 != rescanned_t40:
            t40_mismatch.append(ticker)
        packed = None
        nba_id = align.get("nba_game_id")
        if nba_id:
            packed = _pbp_pack(nba_id, pbp_cache)
        actions = packed[0] if packed else []
        touch_clocks = {}
        for lv in LEVELS:
            ts = touches[lv]
            if ts is None or not actions:
                touch_clocks[lv] = {
                    "ts": ts,
                    "period": None,
                    "period_remaining_s": None,
                    "game_seconds_remaining": None,
                }
                continue
            ck = snap_clock(actions, ts)
            touch_clocks[lv] = {
                "ts": ts,
                "period": ck["period"],
                "period_remaining_s": ck["period_remaining_s"],
                "game_seconds_remaining": ck["game_seconds_remaining"],
            }
        won = bool(rec["expiration_result_yes"])
        row = {
            "event_id": rec.get("event_id"),
            "ticker": ticker,
            "game_date": rec.get("game_date"),
            "team": rec.get("team"),
            "first_80_timestamp": t0,
            "W": won,
            "entry_quarter_bucket": align["entry_quarter_bucket"],
            "alignment_confidence": align["alignment_confidence"],
            "alignment_reason": align["alignment_reason"],
            "entry_phase": align["entry_phase"],
            "entry_period": align["entry_period"],
            "entry_game_seconds_remaining": align["entry_game_seconds_remaining"],
            "nba_game_id": align.get("nba_game_id"),
        }
        for lv in LEVELS:
            ck = touch_clocks[lv]
            row[f"T{lv}"] = ck["ts"] is not None
            row[f"t{lv}_ts"] = ck["ts"]
            row[f"t{lv}_period"] = ck["period"]
            row[f"t{lv}_period_remaining_s"] = ck["period_remaining_s"]
            row[f"t{lv}_remaining_s"] = ck["game_seconds_remaining"]
            row[f"t{lv}_remaining_clock"] = format_clock(ck["game_seconds_remaining"])
        rows.append(row)

    if missing_candles:
        raise IdentityHalt(f"HALT missing candles n={len(missing_candles)} sample={missing_candles[:5]}")
    if t40_mismatch:
        raise IdentityHalt(
            f"HALT T40 rescan mismatch n={len(t40_mismatch)} sample={t40_mismatch[:5]}"
        )

    partition = dict(Counter(r["entry_quarter_bucket"] for r in rows))
    for b in PARTITION_BUCKETS:
        partition.setdefault(b, 0)
    if sum(partition[b] for b in PARTITION_BUCKETS) != EXPECTED_N:
        raise IdentityHalt(f"HALT quarter partition {partition}")

    joints = universe_joints(rows)
    if joints["T40"] != EXPECTED_T40 or joints["W_and_not_T40"] != EXPECTED_W_NOT_T40:
        raise IdentityHalt(f"HALT universe T40 joints {joints}")

    by_bucket = {b: bucket_summary(rows, b) for b in PARTITION_BUCKETS}
    alignment_counts = dict(Counter(r["alignment_confidence"] for r in rows))

    summary = {
        "written_utc": utc_now(),
        "research_only": True,
        "candle_path_not_fill": True,
        "touch_definition": "first later tradable yes_bid_close <= L (close-path, not wick)",
        "quarter_definition": "PBP period of last action with modeled wall <= first_80_timestamp",
        "alignment_model": "PERIOD_BOUNDED_LINEAR_GAME_CLOCK",
        "identity": identity,
        "universe_joints": joints,
        "v2_universe_reference": {
            "W_and_not_T60": EXPECTED_V2_W_NOT_T60,
            "W_and_not_T50": EXPECTED_V2_W_NOT_T50,
            "W_and_not_T40": EXPECTED_W_NOT_T40,
            "t60_match": joints["W_and_not_T60"] == EXPECTED_V2_W_NOT_T60,
            "t50_match": joints["W_and_not_T50"] == EXPECTED_V2_W_NOT_T50,
        },
        "partition": partition,
        "alignment_counts": alignment_counts,
        "by_bucket": by_bucket,
        "quarter_tables": {b: by_bucket[b] for b in QUARTER_BUCKETS},
        "residual": {b: by_bucket[b] for b in ("OT", "UNALIGNED")},
    }
    return {"summary": summary, "rows": rows}


def attach_ev_from_counts(level_block: dict, n: int, n_winners: int, level: int) -> None:
    """Fill EV fields on an existing summary level block from stored counts."""
    n_touch = int(level_block["n_touch"])
    n_w_not = int(level_block["n_winner_before_touch"])
    n_w_and_t = int(level_block.get("n_win_and_touch") or max(0, n_winners - n_w_not))
    level_block["n_win_and_touch"] = n_w_and_t
    level_block["pct_win_given_touch"] = rate(n_w_and_t, n_touch)
    level_block["ev_stop"] = ev_stop_gross(n, n_w_not, n_touch, level)
    level_block["ev_touch_hold"] = ev_touch_hold_gross(n_touch, n_w_and_t)


def enrich_summary_ev(summary: dict) -> dict:
    """Recompute EV onto a written summary without rescanning candles/PBP."""
    for key in ("by_bucket", "quarter_tables", "residual"):
        block = summary.get(key) or {}
        for _name, rec in block.items():
            n = int(rec["n"])
            w = int(rec["n_winners"])
            rec["ev_hold"] = ev_hold_gross(n, w)
            for lv in LEVELS:
                lv_s = str(lv)
                if lv_s in rec.get("levels", {}):
                    attach_ev_from_counts(rec["levels"][lv_s], n, w, lv)
    return summary


def write_outputs(result: dict) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    OUT.mkdir(parents=True, exist_ok=True)
    summary = result["summary"]
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    rows = result["rows"]
    pq.write_table(pa.Table.from_pylist(rows), OUT / "trades.parquet")
    print("wrote", OUT / "summary.json")
    print("partition", summary["partition"])
    print("universe", summary["universe_joints"])
    for b in QUARTER_BUCKETS:
        q = summary["quarter_tables"][b]
        print(
            b,
            "n",
            q["n"],
            "W¬T60",
            q["levels"]["60"]["pct_winner_before_touch"],
            "W¬T50",
            q["levels"]["50"]["pct_winner_before_touch"],
            "W¬T40",
            q["levels"]["40"]["pct_winner_before_touch"],
        )


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--ev-only":
        path = OUT / "summary.json"
        summary = json.loads(path.read_text())
        enrich_summary_ev(summary)
        path.write_text(json.dumps(summary, indent=2) + "\n")
        print("enriched EV", path)
        for b, lv in (("Q2", "60"), ("Q2", "50"), ("Q2", "40"), ("Q3", "60")):
            rec = summary["by_bucket"][b]
            ev = rec["levels"][lv]["ev_stop"]
            hold = rec["ev_hold"]
            print(
                b,
                lv,
                "stop",
                ev["ev_pct_of_1_dollar"],
                "%/$1",
                "hold",
                hold["ev_pct_of_1_dollar"],
            )
        return 0
    result = analyze()
    write_outputs(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
