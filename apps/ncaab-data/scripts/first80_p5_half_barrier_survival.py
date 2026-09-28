#!/usr/bin/env python3
"""NCAAB Power-5 FIRST80 half-bin barrier survival (research only).

Splits the frozen P5 vs P5 FIRST80 universe (n=721) by ESPN PBP half and
10-minute remaining at entry, then reports P(expire winner before
close-touching 60/50/40) and gross EV of buy@80 / stop-at-L.

Does not change live FIRST01 / 80/81/83/89. Candle path, not fills.
Does not invent L2, queue, or future OT.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
NBA_SCRIPTS = Path("/Users/user/Desktop/Momento/apps/nba-data/scripts")
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(NBA_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(NBA_SCRIPTS))

import nba_80_40_execution_audit as audit  # noqa: E402
import ncaab_pbp_align as P  # noqa: E402
import ncaab_pbp_espn_ingest as ingest  # noqa: E402

ROOT = Path(
    "/Users/user/Desktop/Momento/Backtesting Suite/Data/NCAAB/2025-2026/warehouse"
)
NORM = ROOT / "normalized" / "ncaab"
CANDIDATES_PATH = ROOT / "derived" / "ncaab" / "first80_execution_audit" / "candidates.json"
GAMES_PATH = NORM / "games" / "ncaab_games.parquet"
CANDLES_DIR = NORM / "candles_1m"
OUT = ROOT / "derived" / "ncaab" / "first80_p5_half_barrier_survival"

P5_CODES = ingest.P5_CODES

EXPECTED_N = 721
EXPECTED_W = 601
EXPECTED_T40 = 188
EXPECTED_W_NOT_T40 = 533
EXPECTED_L_NOT_T40 = 0

LEVELS = (60, 50, 40)
LEVEL_E4 = {60: 6000, 50: 5000, 40: 4000}
ENTRY_CENTS = 80
SETTLE_YES_CENTS = 100
WIN_PNL_CENTS = SETTLE_YES_CENTS - ENTRY_CENTS
LOSE_HOLD_PNL_CENTS = 0 - ENTRY_CENTS
R_CENTS = audit.R_CENTS
PRIMARY_ALIGN = P.PRIMARY_ALIGN
HALF_BUCKETS = ("H1_1", "H1_2", "H2_1", "H2_2")
PARTITION_BUCKETS = ("H1_1", "H1_2", "H2_1", "H2_2", "OT", "UNALIGNED")
BUCKET_LABELS = {
    "H1_1": "1H first 10",
    "H1_2": "1H second 10",
    "H2_1": "2H first 10",
    "H2_2": "2H second 10",
    "OT": "OT",
    "UNALIGNED": "UNALIGNED",
}
REMAINING_HIST_BINS = (
    ("30:01–40:00", 30 * 60 + 1, 40 * 60 + 1),
    ("20:01–30:00", 20 * 60 + 1, 30 * 60 + 1),
    ("10:01–20:00", 10 * 60 + 1, 20 * 60 + 1),
    ("00:00–10:00", 0, 10 * 60 + 1),
)


class IdentityHalt(RuntimeError):
    pass


def utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def load_games_by_event() -> dict[str, dict]:
    import pyarrow.parquet as pq

    t = pq.read_table(
        GAMES_PATH,
        columns=["event_id", "home_team_code", "away_team_code", "home_team", "away_team", "game_date"],
    )
    out = {}
    for i in range(t.num_rows):
        out[t.column("event_id")[i].as_py()] = {
            "home_team_code": t.column("home_team_code")[i].as_py(),
            "away_team_code": t.column("away_team_code")[i].as_py(),
            "home_team": t.column("home_team")[i].as_py(),
            "away_team": t.column("away_team")[i].as_py(),
            "game_date": t.column("game_date")[i].as_py(),
        }
    return out


def load_frozen_p5_first80(path: Path | None = None) -> list[dict]:
    src = path or CANDIDATES_PATH
    cands = json.loads(src.read_text())
    games = load_games_by_event()
    out = []
    for c in cands:
        if c.get("status") != "FIRST_80" or c.get("expiration_result_yes") is None:
            continue
        g = games.get(c["event_id"])
        if g is None:
            continue
        if g["home_team_code"] in P5_CODES and g["away_team_code"] in P5_CODES:
            rec = dict(c)
            rec["_home_team_code"] = g["home_team_code"]
            rec["_away_team_code"] = g["away_team_code"]
            out.append(rec)
    return out


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
        "label": "CANDLE PATH — NOT ACTUAL FILL — P5 vs P5",
    }


def halt_unless_identity(trades: list[dict]) -> dict:
    gate = identity_of(trades)
    if not gate["ok"]:
        raise IdentityHalt(f"HALT frozen P5 identity {gate}")
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
    if period is not None and int(period) >= 3:
        return "OT"
    for label, lo, hi in REMAINING_HIST_BINS:
        if lo <= remaining_s < hi:
            return label
    if remaining_s >= 40 * 60 + 1:
        return ">40:00"
    return "00:00–10:00"


def nested_ok(touches: dict[int, int | None]) -> bool:
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


def regulation_remaining_formula_ok(
    period: int | None, period_remaining: float | None, game_remaining: float | None
) -> bool:
    if period is None or period_remaining is None or game_remaining is None:
        return True
    expected = P.game_seconds_remaining(period, period_remaining)
    if expected is None:
        return True
    return abs(float(game_remaining) - float(expected)) < 1e-6


def _pbp_pack(espn_id: str, cache: dict) -> list[dict] | None:
    if espn_id in cache:
        return cache[espn_id]
    raw = P.load_plays(espn_id)
    if not raw:
        cache[espn_id] = None
        return None
    actions = P.enrich_actions(raw.get("plays") or [])
    cache[espn_id] = actions
    return actions


def align_entry(rec: dict, xwalk: dict, pbp_cache: dict) -> dict:
    event_id = rec.get("event_id")
    cw = xwalk.get(event_id) or {}
    espn_id = cw.get("espn_game_id")
    match_status = cw.get("match_status")
    entry_ts = int(rec["first_80_timestamp"])
    out = {
        "espn_game_id": espn_id,
        "crosswalk_status": match_status,
        "alignment_model": P.ALIGNMENT_MODEL,
        "alignment_confidence": "UNUSABLE",
        "alignment_reason": None,
        "entry_phase": "UNALIGNED",
        "entry_period": None,
        "entry_period_remaining_s": None,
        "entry_game_seconds_remaining": None,
        "entry_half_bucket": "UNALIGNED",
    }
    if match_status != "MATCHED" or not espn_id:
        out["alignment_reason"] = "UNMATCHED_CROSSWALK"
        return out
    actions = _pbp_pack(espn_id, pbp_cache)
    if not actions:
        out["alignment_reason"] = "NO_PBP"
        return out
    snap = P.snap_to_entry(actions, entry_ts)
    conf, reason = P.classify_confidence(actions, snap, entry_ts)
    clock = P.snap_clock(actions, entry_ts)
    out.update(
        {
            "alignment_confidence": conf,
            "alignment_reason": reason,
            "entry_phase": clock["phase"],
            "entry_period": clock["period"],
            "entry_period_remaining_s": clock["period_remaining_s"],
            "entry_game_seconds_remaining": clock["game_seconds_remaining"],
            "entry_half_bucket": P.entry_bucket(
                conf, clock["phase"], clock["period"], clock["period_remaining_s"]
            ),
        }
    )
    return out


def _pq():
    import pyarrow.parquet as pq

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
    return int(level) - ENTRY_CENTS


def ev_stop_gross(n: int, n_survive_win: int, n_touch: int, level: int) -> dict:
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
    return ev_hold_gross(n_touch, n_win_and_touch)


def bucket_summary(rows: list[dict], bucket: str) -> dict:
    sub = [r for r in rows if r["entry_half_bucket"] == bucket]
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
        ev_stop = ev_stop_gross(n, n_w_not, n_touch, lv)
        ev_hold = ev_hold_gross(n, w)
        vs_hold = None
        if ev_stop["ev_cents_per_contract"] is not None and ev_hold["ev_cents_per_contract"] is not None:
            vs_hold = round(ev_stop["ev_cents_per_contract"] - ev_hold["ev_cents_per_contract"], 4)
        levels[str(lv)] = {
            "n_touch": n_touch,
            "n_no_touch": n - n_touch,
            "n_winner_before_touch": n_w_not,
            "n_win_and_touch": n_w_and_t,
            "pct_winner_before_touch": rate(n_w_not, n),
            "pct_touch": rate(n_touch, n),
            "pct_win_given_touch": rate(n_w_and_t, n_touch),
            "ev_stop": ev_stop,
            "ev_touch_hold": ev_touch_hold_gross(n_touch, n_w_and_t),
            "vs_hold_cents": vs_hold,
            "clock": clock_stats(clocks),
            "remaining_hist": dict(hist),
        }
    nested = levels["40"]["n_touch"] <= levels["50"]["n_touch"] <= levels["60"]["n_touch"]
    return {
        "bucket": bucket,
        "label": BUCKET_LABELS[bucket],
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
    trades = trades if trades is not None else load_frozen_p5_first80()
    identity = halt_unless_identity(trades)
    xwalk = P.load_crosswalk()
    pbp_cache: dict = {}
    needed = {t["ticker"] for t in trades if t.get("ticker")}
    files = candle_files_for(needed)
    quotes_by_ticker: dict[str, list] = {}
    print(f"candle files {len(files)} / needed {len(needed)}", flush=True)
    for i, path in enumerate(files, 1):
        if i == 1 or i == len(files) or i % 200 == 0:
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
        espn_id = align.get("espn_game_id")
        actions = _pbp_pack(espn_id, pbp_cache) if espn_id else None
        actions = actions or []
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
            ck = P.snap_clock(actions, ts)
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
            "entry_half_bucket": align["entry_half_bucket"],
            "alignment_confidence": align["alignment_confidence"],
            "alignment_reason": align["alignment_reason"],
            "entry_phase": align["entry_phase"],
            "entry_period": align["entry_period"],
            "entry_period_remaining_s": align["entry_period_remaining_s"],
            "entry_game_seconds_remaining": align["entry_game_seconds_remaining"],
            "espn_game_id": align.get("espn_game_id"),
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
        raise IdentityHalt(f"HALT T40 rescan mismatch n={len(t40_mismatch)} sample={t40_mismatch[:5]}")

    partition = dict(Counter(r["entry_half_bucket"] for r in rows))
    for b in PARTITION_BUCKETS:
        partition.setdefault(b, 0)
    if sum(partition[b] for b in PARTITION_BUCKETS) != EXPECTED_N:
        raise IdentityHalt(f"HALT half partition {partition}")

    joints = universe_joints(rows)
    if joints["T40"] != EXPECTED_T40 or joints["W_and_not_T40"] != EXPECTED_W_NOT_T40:
        raise IdentityHalt(f"HALT universe T40 joints {joints}")

    by_bucket = {b: bucket_summary(rows, b) for b in PARTITION_BUCKETS}
    alignment_counts = dict(Counter(r["alignment_confidence"] for r in rows))
    ev_cells = []
    for b in HALF_BUCKETS:
        rec = by_bucket[b]
        hold = rec["ev_hold"]
        for lv in LEVELS:
            lv_s = str(lv)
            block = rec["levels"][lv_s]
            ev = block["ev_stop"]
            ev_cells.append(
                {
                    "cell": f"{BUCKET_LABELS[b]} {lv}",
                    "bucket": b,
                    "level": lv,
                    "n": rec["n"],
                    "n_survive_win": block["n_winner_before_touch"],
                    "n_touch": block["n_touch"],
                    "pct_win_given_touch": block["pct_win_given_touch"],
                    "n_win_and_touch": block["n_win_and_touch"],
                    "stop_pnl_cents": ev["stop_pnl_cents"],
                    "ev_pct_of_1_dollar": ev["ev_pct_of_1_dollar"],
                    "ev_pct_of_80_debit": ev["ev_pct_of_80_debit"],
                    "hold_ev_pct_of_1_dollar": hold["ev_pct_of_1_dollar"],
                    "vs_hold_cents": block["vs_hold_cents"],
                    "touch_hold_ev_cents": block["ev_touch_hold"]["ev_cents_per_contract"],
                }
            )

    summary = {
        "written_utc": utc_now(),
        "research_only": True,
        "candle_path_not_fill": True,
        "universe": "P5 vs P5 KXNCAAMBGAME 2025-26 FIRST80",
        "touch_definition": "first later tradable yes_bid_close <= L (close-path, not wick)",
        "half_definition": (
            "ESPN PBP period + clock of last play with observed wall <= first_80_timestamp; "
            "H1/H2 split at 10:00 remaining (first 10 = remaining > 600s)"
        ),
        "alignment_model": P.ALIGNMENT_MODEL,
        "identity": identity,
        "universe_joints": joints,
        "partition": partition,
        "alignment_counts": alignment_counts,
        "by_bucket": by_bucket,
        "half_tables": {b: by_bucket[b] for b in HALF_BUCKETS},
        "residual": {b: by_bucket[b] for b in ("OT", "UNALIGNED")},
        "ev_cells": ev_cells,
    }
    return {"summary": summary, "rows": rows}


def write_outputs(result: dict) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    OUT.mkdir(parents=True, exist_ok=True)
    summary = result["summary"]
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    pq.write_table(pa.Table.from_pylist(result["rows"]), OUT / "trades.parquet")
    print("wrote", OUT / "summary.json")
    print("partition", summary["partition"])
    print("universe", summary["universe_joints"])
    for b in HALF_BUCKETS:
        q = summary["half_tables"][b]
        print(
            BUCKET_LABELS[b],
            "n",
            q["n"],
            "W¬T60",
            q["levels"]["60"]["pct_winner_before_touch"],
            "W¬T50",
            q["levels"]["50"]["pct_winner_before_touch"],
            "W¬T40",
            q["levels"]["40"]["pct_winner_before_touch"],
        )
    for cell in summary["ev_cells"]:
        print(
            cell["cell"],
            "survive",
            cell["n_survive_win"],
            "touch",
            cell["n_touch"],
            "EV/$1",
            cell["ev_pct_of_1_dollar"],
            "vs hold",
            cell["vs_hold_cents"],
        )


def main() -> int:
    result = analyze()
    write_outputs(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
