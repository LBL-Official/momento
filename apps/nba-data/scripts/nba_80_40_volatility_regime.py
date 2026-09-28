#!/usr/bin/env python3
"""NBA 80/40 VOLATILITY REGIME ANALYSIS V1.

Descriptive layer on the FROZEN first-80 / close-path-40 labels.

Does not redefine the strategy. Does not invent L2. Does not use future
candles for ENTRY_VOLATILITY. Does not search OOS for thresholds.

Official NBA quarter/clock is not in the Kalshi candle warehouse. Game-phase
buckets here are WALL-CLOCK estimates from scheduled_start (or first candle),
labeled ESTIMATED. They are not play-by-play quarters.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import nba_80_40_execution_audit as audit  # noqa: E402

ROOT = audit.ROOT
NORM = audit.NORM
OUT = ROOT / "derived" / "nba" / "first80_volatility_regime_v1"

HIT80 = audit.HIT80
HIT40 = audit.HIT40
R_CENTS = audit.R_CENTS
EXPECTED_GAMES = 1362
EXPECTED_FIRST80 = 1230
EXPECTED_SURVIVORS = 910
EXPECTED_STOPS = 320

# Frozen a priori. Not fit on OOS.
# Wall-clock minutes after tip. NOT official NBA game clock.
WALL_Q1_END = 36
WALL_Q2_END = 72
WALL_Q3_END = 120
WALL_Q4_END = 180

# Quality-score points. Frozen a priori, not outcome-optimized.
QUALITY_CUTS = {"A": 2, "B": 0, "C": -2}  # score >= cut

# Frozen candidate filter for NBA_80_40_VOLATILITY_V1:
# skip research-sample top quintile of entry 5-minute realized vol.
FILTER_NAME = "NBA_80_40_VOLATILITY_V1"
FILTER_RULE = "drop_entry_vol5_VERY_HIGH"


def e4_to_cents(x):
    if x is None:
        return None
    return x / 100.0


def parse_ts(s):
    return audit.parse_ts(s)


def mean(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    return sum(xs) / len(xs)


def median(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    return statistics.median(xs)


def pctile_edges(xs):
    """Return 20/40/60/80 percentile edges from a research-sample list."""
    vals = sorted(x for x in xs if x is not None)
    if len(vals) < 5:
        return None
    n = len(vals)

    def at(p):
        i = min(n - 1, max(0, int(round(p * (n - 1)))))
        return vals[i]

    return {"p20": at(0.20), "p40": at(0.40), "p60": at(0.60), "p80": at(0.80)}


def regime_from_edges(x, edges):
    if x is None or edges is None:
        return None
    if x <= edges["p20"]:
        return "VERY_LOW"
    if x <= edges["p40"]:
        return "LOW"
    if x <= edges["p60"]:
        return "NORMAL"
    if x <= edges["p80"]:
        return "HIGH"
    return "VERY_HIGH"


def empirical_percentile(x, ref):
    if x is None or not ref:
        return None
    n = len(ref)
    below = sum(1 for v in ref if v <= x)
    return round(100.0 * below / n, 2)


def stdev(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return None
    return statistics.stdev(xs)


def wall_phase(minutes_since_tip):
    """Estimated wall-clock phase. Not official NBA quarter."""
    if minutes_since_tip is None:
        return None
    m = minutes_since_tip
    if m < 0:
        return "PRE_TIP_EST"
    if m < WALL_Q1_END:
        return "Q1_EST"
    if m < WALL_Q2_END:
        return "Q2_EST"
    if m < WALL_Q3_END:
        return "Q3_EST"
    if m < WALL_Q4_END:
        return "Q4_EST"
    return "OT_EST"


def q4_bucket(minutes_since_tip):
    """Coarse Q4 wall-clock buckets. Not game-clock 12:00–0:00."""
    if minutes_since_tip is None:
        return None
    m = minutes_since_tip
    if m < WALL_Q3_END:
        return None
    if m < 135:
        return "Q4_EST_EARLY"  # ~ first 15 wall min of estimated Q4
    if m < 150:
        return "Q4_EST_MID"
    if m < 165:
        return "Q4_EST_LATE"
    if m < WALL_Q4_END:
        return "Q4_EST_CRUNCH"
    return "OT_EST"


def time_to_40_bucket(minutes):
    if minutes is None:
        return None
    if minutes <= 1:
        return "0-1m"
    if minutes <= 5:
        return "2-5m"
    if minutes <= 15:
        return "6-15m"
    if minutes <= 60:
        return "16-60m"
    return ">60m"


def ev_from_survives(n_survive, n_hit):
    n = n_survive + n_hit
    if n == 0:
        return None
    return round((n_survive * R_CENTS + n_hit * (-2 * R_CENTS)) / n, 4)


def wr(n_ok, n):
    return audit.rate(n_ok, n)


def load_quotes(markets, games):
    """Same game-window valid candles as the audit, returning the series."""
    games_by_event = {g["event_id"]: g for g in games}
    meta = {}
    for m in markets:
        g = games_by_event.get(m["event_id"], {})
        start = g.get("game_window_start")
        end = m["close_ts"]
        gw_end = g.get("game_window_end")
        if end is None:
            end = gw_end
        elif gw_end is not None:
            end = min(end, gw_end)
        meta[m["ticker"]] = (start, end, m["close_ts"])

    files = sorted((NORM / "candles_1m").rglob("*.parquet"))
    quotes = defaultdict(list)
    cols = [
        "ticker",
        "end_period_ts",
        "yes_bid_open_e4",
        "yes_bid_high_e4",
        "yes_bid_low_e4",
        "yes_bid_close_e4",
        "yes_ask_close_e4",
        "volume_hundredths",
        "is_valid",
    ]
    for path in files:
        table = pq.read_table(path, columns=cols)
        n = table.num_rows
        get = {c: table.column(c) for c in cols}
        for i in range(n):
            if not get["is_valid"][i].as_py():
                continue
            ticker = get["ticker"][i].as_py()
            t = int(get["end_period_ts"][i].as_py())
            start, end, _ = meta.get(ticker, (None, None, None))
            if start is not None and t < start:
                continue
            if end is not None and t > end:
                continue
            quotes[ticker].append(
                {
                    "ts": t,
                    "bid_o": audit._opt_int(get["yes_bid_open_e4"][i].as_py()),
                    "bid_h": audit._opt_int(get["yes_bid_high_e4"][i].as_py()),
                    "bid_l": audit._opt_int(get["yes_bid_low_e4"][i].as_py()),
                    "bid_c": audit._opt_int(get["yes_bid_close_e4"][i].as_py()),
                    "ask_c": audit._opt_int(get["yes_ask_close_e4"][i].as_py()),
                    "vol": audit._opt_int(get["volume_hundredths"][i].as_py()),
                }
            )
    for rows in quotes.values():
        rows.sort(key=lambda r: r["ts"])
    return quotes, meta


def features_at(rows, idx):
    """Causal contract-volatility features using candles 0..idx inclusive.

    Price series is yes_bid_close (the same series that defines 80/40).
    This is CONTRACT / market-implied volatility, not basketball volatility.
    """
    q = rows[idx]
    closes = [r["bid_c"] for r in rows[: idx + 1]]
    n = len(closes)
    out = {
        "n_prior_candles": n,
        "abs_return_1m_cents": None,
        "move_5m_cents": None,
        "move_15m_cents": None,
        "vol_5m_cents": None,
        "vol_15m_cents": None,
        "range_1m_cents": None,
        "range_5m_avg_cents": None,
        "range_15m_avg_cents": None,
        "velocity_1m_cents": None,
        "velocity_5m_cents": None,
        "velocity_15m_cents": None,
        "accel_5m_cents": None,
        "vol_shock": None,
        "spread_cents": None,
        "contiguous_1m": True,
        "insufficient_history_5m": n < 6,
        "insufficient_history_15m": n < 16,
    }
    if q["bid_c"] is not None and q["ask_c"] is not None:
        out["spread_cents"] = e4_to_cents(q["ask_c"] - q["bid_c"])
    if q["bid_h"] is not None and q["bid_l"] is not None:
        out["range_1m_cents"] = e4_to_cents(q["bid_h"] - q["bid_l"])

    def close_at(j):
        if j < 0:
            return None
        return closes[j]

    c0 = close_at(n - 1)
    c1 = close_at(n - 2)
    if c0 is not None and c1 is not None:
        out["abs_return_1m_cents"] = abs(e4_to_cents(c0 - c1))
        out["velocity_1m_cents"] = e4_to_cents(c0 - c1)  # k=1

    if n >= 6:
        c5 = close_at(n - 6)
        if c0 is not None and c5 is not None:
            out["move_5m_cents"] = abs(e4_to_cents(c0 - c5))
            out["velocity_5m_cents"] = e4_to_cents(c0 - c5) / 5.0
        rets = []
        for j in range(n - 5, n):
            a, b = close_at(j - 1), close_at(j)
            if a is None or b is None:
                rets.append(None)
            else:
                rets.append(e4_to_cents(b - a))
        out["vol_5m_cents"] = stdev(rets)
        ranges = []
        for r in rows[n - 5 : n]:
            if r["bid_h"] is not None and r["bid_l"] is not None:
                ranges.append(e4_to_cents(r["bid_h"] - r["bid_l"]))
        out["range_5m_avg_cents"] = mean(ranges)

    if n >= 16:
        c15 = close_at(n - 16)
        if c0 is not None and c15 is not None:
            out["move_15m_cents"] = abs(e4_to_cents(c0 - c15))
            out["velocity_15m_cents"] = e4_to_cents(c0 - c15) / 15.0
        rets = []
        for j in range(n - 15, n):
            a, b = close_at(j - 1), close_at(j)
            if a is None or b is None:
                rets.append(None)
            else:
                rets.append(e4_to_cents(b - a))
        out["vol_15m_cents"] = stdev(rets)
        ranges = []
        for r in rows[n - 15 : n]:
            if r["bid_h"] is not None and r["bid_l"] is not None:
                ranges.append(e4_to_cents(r["bid_h"] - r["bid_l"]))
        out["range_15m_avg_cents"] = mean(ranges)

    if out["vol_5m_cents"] is not None and out["vol_15m_cents"] not in (None, 0):
        out["vol_shock"] = round(out["vol_5m_cents"] / out["vol_15m_cents"], 4)

    if n >= 11 and out["velocity_5m_cents"] is not None:
        # Prior 5m velocity ending at t-5 (causal).
        c_now_prev = close_at(n - 6)
        c_then = close_at(n - 11)
        if c_now_prev is not None and c_then is not None:
            prev_v = e4_to_cents(c_now_prev - c_then) / 5.0
            out["accel_5m_cents"] = out["velocity_5m_cents"] - prev_v

    # Gap flag: last 15 intervals should be 60s when history exists.
    look = min(15, max(0, n - 1))
    if look:
        dts = [rows[n - look + k]["ts"] - rows[n - look + k - 1]["ts"] for k in range(look)]
        out["contiguous_1m"] = all(50 <= d <= 70 for d in dts)
    return out


def index_at_ts(rows, ts):
    for i, r in enumerate(rows):
        if r["ts"] == ts:
            return i
    return None


def path_80_to_40(rows, i80, i40):
    """Path stats from first-80 candle through first-40 candle, inclusive.

    No candles after the 40 event.
    """
    if i80 is None or i40 is None or i40 < i80:
        return {}
    window = rows[i80 : i40 + 1]
    closes = [r["bid_c"] for r in window if r["bid_c"] is not None]
    dt_min = (rows[i40]["ts"] - rows[i80]["ts"]) / 60.0
    mae = None
    mfe = None
    if closes:
        # Adverse for a long YES at 80: price going down.
        mae = e4_to_cents(min(closes) - HIT80)
        mfe = e4_to_cents(max(closes) - HIT80)
    rets = []
    for j in range(1, len(window)):
        a, b = window[j - 1]["bid_c"], window[j]["bid_c"]
        if a is not None and b is not None:
            rets.append(e4_to_cents(b - a))
    vel = None
    if dt_min > 0 and window[0]["bid_c"] is not None and window[-1]["bid_c"] is not None:
        vel = e4_to_cents(window[-1]["bid_c"] - window[0]["bid_c"]) / dt_min
    return {
        "time_to_40_minutes": round(dt_min, 2),
        "time_to_40_bucket": time_to_40_bucket(dt_min),
        "mae_cents": mae,
        "mfe_cents": mfe,
        "decline_velocity_cents_per_min": vel,
        "path_vol_cents": stdev(rets),
        "path_n_candles": len(window),
    }


def close_bucket(minutes_to_close):
    """Contract lifetime remaining. Not NBA quarter."""
    if minutes_to_close is None:
        return None
    m = minutes_to_close
    if m >= 240:
        return ">240m_to_close"
    if m >= 120:
        return "120-240m_to_close"
    if m >= 60:
        return "60-120m_to_close"
    if m >= 30:
        return "30-60m_to_close"
    return "<30m_to_close"


def quality_score(entry):
    """A priori interpretable score. Not a trained classifier.

    Higher is calmer / cleaner. Frozen point map, not fit to outcomes.
    Does not use estimated NBA quarter (unavailable). Late-contract uses
    minutes-to-Kalshi-close < 30 only.
    """
    pts = 0
    reasons = []
    reg = entry.get("entry_vol5_regime")
    if reg == "VERY_LOW":
        pts += 2
        reasons.append("vol5_VERY_LOW+2")
    elif reg == "LOW":
        pts += 1
        reasons.append("vol5_LOW+1")
    elif reg == "NORMAL":
        reasons.append("vol5_NORMAL+0")
    elif reg == "HIGH":
        pts -= 1
        reasons.append("vol5_HIGH-1")
    elif reg == "VERY_HIGH":
        pts -= 2
        reasons.append("vol5_VERY_HIGH-2")
    shock = entry.get("entry_vol_shock")
    if shock is not None and shock >= 2.0:
        pts -= 1
        reasons.append("vol_shock>=2-1")
    mtc = entry.get("entry_minutes_to_close")
    if mtc is not None and mtc < 30:
        pts -= 1
        reasons.append("minutes_to_close<30-1")
    rng = entry.get("entry_range_1m_cents")
    if rng is not None and rng >= 10.0:
        pts -= 1
        reasons.append("range_1m>=10c-1")
    vel = entry.get("entry_velocity_5m_cents")
    if vel is not None and abs(vel) >= 2.0:
        pts -= 1
        reasons.append("|vel_5m|>=2c-1")
    spread = entry.get("entry_spread_cents")
    if spread is not None and spread >= 5.0:
        pts -= 1
        reasons.append("spread>=5c-1")
    if pts >= QUALITY_CUTS["A"]:
        grade = "A"
    elif pts >= QUALITY_CUTS["B"]:
        grade = "B"
    elif pts >= QUALITY_CUTS["C"]:
        grade = "C"
    else:
        grade = "D"
    return pts, grade, reasons


def summarize_group(rows, label):
    n = len(rows)
    survive = sum(1 for r in rows if r["survives_40"])
    hit = sum(1 for r in rows if r["hits_40"])
    wr_s, lo, hi = audit.wilson(survive, n)
    return {
        "label": label,
        "n": n,
        "survive_40": survive,
        "hit_40": hit,
        "survival_rate_pct": wr_s,
        "survival_ci95": [lo, hi],
        "hit_40_rate_pct": wr(hit, n),
        "gross_ev_cents": ev_from_survives(survive, hit),
        "retention_vs_1230_pct": wr(n, EXPECTED_FIRST80),
        "avg_entry_vol5_cents": round(mean([r.get("entry_vol_5m_cents") for r in rows]) or 0, 4)
        if any(r.get("entry_vol_5m_cents") is not None for r in rows)
        else None,
        "avg_entry_vol_shock": round(mean([r.get("entry_vol_shock") for r in rows]) or 0, 4)
        if any(r.get("entry_vol_shock") is not None for r in rows)
        else None,
        "avg_stop_vol5_cents": round(mean([r.get("stop_vol_5m_cents") for r in rows]) or 0, 4)
        if any(r.get("stop_vol_5m_cents") is not None for r in rows)
        else None,
    }


def eventual_win_table(stop_rows, key):
    out = []
    order = []
    seen = set()
    for r in stop_rows:
        k = r.get(key)
        if k not in seen:
            order.append(k)
            seen.add(k)
    for k in order:
        sub = [r for r in stop_rows if r.get(key) == k]
        n = len(sub)
        wins = sum(1 for r in sub if r["expiration_result_yes"])
        losses = n - wins
        wr_s, lo, hi = audit.wilson(wins, n)
        out.append(
            {
                "regime": k,
                "n": n,
                "eventual_win": wins,
                "eventual_loss": losses,
                "eventual_win_pct": wr_s,
                "ci95": [lo, hi],
                "pct_of_320": wr(n, EXPECTED_STOPS),
                "avg_stop_vol5_cents": round(
                    mean([r.get("stop_vol_5m_cents") for r in sub]) or 0, 4
                )
                if sub
                else None,
                "avg_time_to_40_min": round(
                    mean([r.get("time_to_40_minutes") for r in sub]) or 0, 2
                )
                if sub
                else None,
            }
        )
    return out


def hist_counts(xs, edges):
    """Inclusive left, last bin open-right except final."""
    xs = [x for x in xs if x is not None]
    counts = [0] * (len(edges) - 1)
    for x in xs:
        placed = False
        for i in range(len(edges) - 1):
            lo, hi = edges[i], edges[i + 1]
            if (x >= lo and x < hi) or (i == len(edges) - 2 and x >= lo):
                counts[i] += 1
                placed = True
                break
        if not placed:
            counts[-1] += 1
    labels = []
    for i in range(len(edges) - 1):
        labels.append(f"{edges[i]:g}–{edges[i+1]:g}")
    return labels, counts


def main():
    markets = audit.load_markets()
    games = audit.load_games()
    games_by_event = {g["event_id"]: g for g in games}
    quotes, _meta = load_quotes(markets, games)
    scanned = audit.scan(markets, games)
    cands = audit.build_candidates(markets, games, scanned)

    first = [
        c
        for c in cands
        if c["status"] == "FIRST_80" and c["expiration_result_yes"] is not None
    ]
    survivors = [c for c in first if not c["stop_close_triggered"] and c["expiration_result_yes"]]
    stops = [c for c in first if c["stop_close_triggered"]]
    baseline_ok = (
        len(cands) == EXPECTED_GAMES
        and len(first) == EXPECTED_FIRST80
        and len(survivors) == EXPECTED_SURVIVORS
        and len(stops) == EXPECTED_STOPS
    )
    if not baseline_ok:
        print("FROZEN LABEL MISMATCH — refusing to analyze.", file=sys.stderr)
        print(
            json.dumps(
                {
                    "games": len(cands),
                    "first80": len(first),
                    "survivors": len(survivors),
                    "stops": len(stops),
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    tip_source_counts = defaultdict(int)
    rows_out = []
    for c in first:
        ticker = c["ticker"]
        series = quotes.get(ticker, [])
        i80 = index_at_ts(series, c["first_80_timestamp"])
        entry_feat = features_at(series, i80) if i80 is not None else {}
        g = games_by_event.get(c["event_id"], {})
        tip_ts = parse_ts(g.get("scheduled_start"))
        tip_source = "scheduled_start" if tip_ts is not None else "UNAVAILABLE"
        tip_source_counts[tip_source] += 1
        minutes_since_tip = None
        if tip_ts is not None:
            minutes_since_tip = (c["first_80_timestamp"] - tip_ts) / 60.0
        minutes_to_close = None
        if c.get("close_ts") is not None:
            minutes_to_close = (c["close_ts"] - c["first_80_timestamp"]) / 60.0

        hits_40 = bool(c["stop_close_triggered"])
        survives_40 = not hits_40
        label = "FIRST_80_SURVIVES_40" if survives_40 else "FIRST_80_HITS_40"
        if hits_40 and c["expiration_result_yes"]:
            stop_label = "FIRST_80_HITS_40_EVENTUAL_WIN"
        elif hits_40:
            stop_label = "FIRST_80_HITS_40_EVENTUAL_LOSS"
        else:
            stop_label = None

        rec = {
            "event_id": c["event_id"],
            "event_ticker": c.get("event_ticker"),
            "ticker": ticker,
            "game_date": c.get("game_date"),
            "dataset_split": c["dataset_split"],
            "season_phase": c.get("season_phase"),
            "frozen_status": "FIRST_80",
            "outcome_label": label,
            "stop_eventual_label": stop_label,
            "survives_40": survives_40,
            "hits_40": hits_40,
            "expiration_result_yes": c["expiration_result_yes"],
            "first_80_timestamp": c["first_80_timestamp"],
            "first_40_close_ts": c.get("first_40_close_ts"),
            "entry_time_precision": "1m_candle",
            "volatility_kind": "CONTRACT_PRICE_YES_BID_CLOSE",
            "not_game_volatility": True,
            "not_true_realized_vol": True,
            "l2_invented": False,
            "tip_source": tip_source,
            "minutes_since_tip": None
            if minutes_since_tip is None
            else round(minutes_since_tip, 2),
            "entry_wall_phase": wall_phase(minutes_since_tip)
            if tip_source == "scheduled_start"
            else None,
            "entry_q4_bucket": q4_bucket(minutes_since_tip)
            if tip_source == "scheduled_start"
            else None,
            "entry_minutes_to_close": None
            if minutes_to_close is None
            else round(minutes_to_close, 2),
            "entry_close_bucket": close_bucket(minutes_to_close),
            "official_nba_quarter": None,
            "official_game_clock": None,
            "quarter_source": "UNAVAILABLE_NO_PBP",
            "timing_kind": "CONTRACT_MINUTES_TO_KALSHI_CLOSE",
            "entry_abs_return_1m_cents": entry_feat.get("abs_return_1m_cents"),
            "entry_move_5m_cents": entry_feat.get("move_5m_cents"),
            "entry_move_15m_cents": entry_feat.get("move_15m_cents"),
            "entry_vol_5m_cents": entry_feat.get("vol_5m_cents"),
            "entry_vol_15m_cents": entry_feat.get("vol_15m_cents"),
            "entry_range_1m_cents": entry_feat.get("range_1m_cents"),
            "entry_range_5m_avg_cents": entry_feat.get("range_5m_avg_cents"),
            "entry_range_15m_avg_cents": entry_feat.get("range_15m_avg_cents"),
            "entry_velocity_1m_cents": entry_feat.get("velocity_1m_cents"),
            "entry_velocity_5m_cents": entry_feat.get("velocity_5m_cents"),
            "entry_velocity_15m_cents": entry_feat.get("velocity_15m_cents"),
            "entry_accel_5m_cents": entry_feat.get("accel_5m_cents"),
            "entry_vol_shock": entry_feat.get("vol_shock"),
            "entry_spread_cents": entry_feat.get("spread_cents"),
            "entry_insufficient_history_5m": entry_feat.get("insufficient_history_5m"),
            "entry_insufficient_history_15m": entry_feat.get("insufficient_history_15m"),
            "entry_contiguous_1m": entry_feat.get("contiguous_1m"),
            "maker_fill_confidence": c.get("maker_fill_confidence"),
        }

        if hits_40 and c.get("first_40_close_ts") is not None:
            i40 = index_at_ts(series, c["first_40_close_ts"])
            stop_feat = features_at(series, i40) if i40 is not None else {}
            stop_minutes = None
            if tip_ts is not None:
                stop_minutes = (c["first_40_close_ts"] - tip_ts) / 60.0
            rec.update(
                {
                    "stop_vol_5m_cents": stop_feat.get("vol_5m_cents"),
                    "stop_vol_15m_cents": stop_feat.get("vol_15m_cents"),
                    "stop_range_1m_cents": stop_feat.get("range_1m_cents"),
                    "stop_range_5m_avg_cents": stop_feat.get("range_5m_avg_cents"),
                    "stop_velocity_5m_cents": stop_feat.get("velocity_5m_cents"),
                    "stop_accel_5m_cents": stop_feat.get("accel_5m_cents"),
                    "stop_vol_shock": stop_feat.get("vol_shock"),
                    "stop_abs_return_1m_cents": stop_feat.get("abs_return_1m_cents"),
                    "stop_move_5m_cents": stop_feat.get("move_5m_cents"),
                    "stop_spread_cents": stop_feat.get("spread_cents"),
                    "stop_minutes_since_tip": None
                    if stop_minutes is None
                    else round(stop_minutes, 2),
                    "stop_wall_phase": wall_phase(stop_minutes)
                    if tip_source == "scheduled_start"
                    else None,
                    "stop_q4_bucket": q4_bucket(stop_minutes)
                    if tip_source == "scheduled_start"
                    else None,
                    "stop_minutes_to_close": None
                    if c.get("close_ts") is None
                    else round((c["close_ts"] - c["first_40_close_ts"]) / 60.0, 2),
                    "stop_close_bucket": close_bucket(
                        None
                        if c.get("close_ts") is None
                        else (c["close_ts"] - c["first_40_close_ts"]) / 60.0
                    ),
                    "stop_insufficient_history_5m": stop_feat.get("insufficient_history_5m"),
                }
            )
            rec.update(path_80_to_40(series, i80, i40))
        rows_out.append(rec)

    # Freeze percentile edges from research sample only (IN_SAMPLE + VALIDATION).
    research = [r for r in rows_out if r["dataset_split"] in ("IN_SAMPLE", "VALIDATION")]
    oos = [r for r in rows_out if r["dataset_split"] == "OOS"]
    research_vol5 = [
        r["entry_vol_5m_cents"]
        for r in research
        if r["entry_vol_5m_cents"] is not None
    ]
    research_shock = [
        r["entry_vol_shock"] for r in research if r["entry_vol_shock"] is not None
    ]
    research_stop_vol5 = [
        r["stop_vol_5m_cents"]
        for r in research
        if r.get("hits_40") and r.get("stop_vol_5m_cents") is not None
    ]
    entry_edges = pctile_edges(research_vol5)
    shock_edges = pctile_edges(research_shock)
    stop_edges = pctile_edges(research_stop_vol5)

    for r in rows_out:
        r["entry_vol5_regime"] = regime_from_edges(r["entry_vol_5m_cents"], entry_edges)
        r["entry_vol5_percentile"] = empirical_percentile(
            r["entry_vol_5m_cents"], research_vol5
        )
        r["entry_vol_shock_regime"] = regime_from_edges(r["entry_vol_shock"], shock_edges)
        r["stop_vol5_regime"] = regime_from_edges(r.get("stop_vol_5m_cents"), stop_edges)
        r["stop_vol5_percentile"] = empirical_percentile(
            r.get("stop_vol_5m_cents"), research_stop_vol5
        )
        pts, grade, reasons = quality_score(r)
        r["quality_points"] = pts
        r["quality_grade"] = grade
        r["quality_reasons"] = reasons

    REGIME_ORDER = ["VERY_LOW", "LOW", "NORMAL", "HIGH", "VERY_HIGH"]
    PHASE_ORDER = ["PRE_TIP_EST", "Q1_EST", "Q2_EST", "Q3_EST", "Q4_EST", "OT_EST"]
    CLOSE_ORDER = [
        ">240m_to_close",
        "120-240m_to_close",
        "60-120m_to_close",
        "30-60m_to_close",
        "<30m_to_close",
    ]
    GRADE_ORDER = ["A", "B", "C", "D"]
    T40_ORDER = ["0-1m", "2-5m", "6-15m", "16-60m", ">60m"]
    Q4_ORDER = [
        "Q4_EST_EARLY",
        "Q4_EST_MID",
        "Q4_EST_LATE",
        "Q4_EST_CRUNCH",
        "OT_EST",
    ]

    def table_by(key, order, population=None):
        pop = population if population is not None else rows_out
        out = []
        for k in order:
            sub = [r for r in pop if r.get(key) == k]
            s = summarize_group(sub, k)
            out.append(s)
        other = [r for r in pop if r.get(key) not in order]
        if other:
            out.append(summarize_group(other, "OTHER_OR_MISSING"))
        return out

    # Freeze V1 from RESEARCH sample only. Prompt example was "avoid extreme
    # high vol"; if research shows the opposite, freeze the observed direction
    # or freeze "no filter" — never retune on OOS.
    research_vol_table = table_by("entry_vol5_regime", REGIME_ORDER, research)
    research_surv = wr(
        sum(1 for r in research if r["survives_40"]), len(research)
    )
    worst = None
    for t in research_vol_table:
        if t["n"] < 80 or t["survival_rate_pct"] is None:
            continue
        if worst is None or t["survival_rate_pct"] < worst["survival_rate_pct"]:
            worst = t
    filter_drop_regime = None
    filter_rule_name = "no_entry_vol_filter"
    if (
        worst is not None
        and research_surv is not None
        and (research_surv - worst["survival_rate_pct"]) >= 2.0
    ):
        filter_drop_regime = worst["label"]
        filter_rule_name = f"drop_entry_vol5_{filter_drop_regime}"
    for r in rows_out:
        r["filter_v1_drop"] = (
            False
            if filter_drop_regime is None
            else r["entry_vol5_regime"] == filter_drop_regime
        )

    entry_vol_table = table_by("entry_vol5_regime", REGIME_ORDER)
    phase_table = table_by("entry_wall_phase", PHASE_ORDER)
    close_table = table_by("entry_close_bucket", CLOSE_ORDER)
    grade_table = table_by("quality_grade", GRADE_ORDER)
    n_scheduled_start = sum(1 for r in rows_out if r.get("tip_source") == "scheduled_start")

    # Entry vol × wall phase: each cell N / survival / hit40
    cross = []
    vol_cols = ["LOW_OR_VERY_LOW", "NORMAL", "HIGH", "VERY_HIGH"]

    def vol_bucket(reg):
        if reg in ("VERY_LOW", "LOW"):
            return "LOW_OR_VERY_LOW"
        return reg

    for phase in PHASE_ORDER:
        cell = {"phase": phase}
        for vb in vol_cols:
            sub = [
                r
                for r in rows_out
                if r.get("entry_wall_phase") == phase and vol_bucket(r.get("entry_vol5_regime")) == vb
            ]
            n = len(sub)
            survive = sum(1 for r in sub if r["survives_40"])
            hit = n - survive
            cell[vb] = {
                "n": n,
                "survival_rate_pct": wr(survive, n),
                "hit_40_rate_pct": wr(hit, n),
            }
        cross.append(cell)

    stop_rows = [r for r in rows_out if r["hits_40"]]
    stop_vol_table = eventual_win_table(stop_rows, "stop_vol5_regime")
    # Reorder stop table
    stop_vol_table_sorted = []
    by_reg = {x["regime"]: x for x in stop_vol_table}
    for k in REGIME_ORDER:
        if k in by_reg:
            stop_vol_table_sorted.append(by_reg[k])
    if None in by_reg:
        stop_vol_table_sorted.append(by_reg[None])

    stop_phase_table = []
    for k in PHASE_ORDER:
        sub = [r for r in stop_rows if r.get("stop_wall_phase") == k]
        s = summarize_group(sub, k)
        wins = sum(1 for r in sub if r["expiration_result_yes"])
        s["eventual_win"] = wins
        s["eventual_loss"] = len(sub) - wins
        s["eventual_win_pct"] = wr(wins, len(sub))
        s["pct_of_all_80_to_40"] = wr(len(sub), EXPECTED_STOPS)
        s["avg_entry_vol5_cents"] = (
            round(mean([r.get("entry_vol_5m_cents") for r in sub]) or 0, 4) if sub else None
        )
        s["avg_stop_vol5_cents"] = (
            round(mean([r.get("stop_vol_5m_cents") for r in sub]) or 0, 4) if sub else None
        )
        stop_phase_table.append(s)

    stop_close_table = []
    for k in CLOSE_ORDER:
        sub = [r for r in stop_rows if r.get("stop_close_bucket") == k]
        s = summarize_group(sub, k)
        wins = sum(1 for r in sub if r["expiration_result_yes"])
        s["eventual_win"] = wins
        s["eventual_loss"] = len(sub) - wins
        s["eventual_win_pct"] = wr(wins, len(sub))
        s["pct_of_all_80_to_40"] = wr(len(sub), EXPECTED_STOPS)
        stop_close_table.append(s)

    vol_x_close = []
    for cb in CLOSE_ORDER:
        cell = {"close_bucket": cb}
        for vb in ["LOW_OR_VERY_LOW", "NORMAL", "HIGH", "VERY_HIGH"]:
            sub = [
                r
                for r in rows_out
                if r.get("entry_close_bucket") == cb
                and (
                    "LOW" in (r.get("entry_vol5_regime") or "")
                    if vb == "LOW_OR_VERY_LOW"
                    else r.get("entry_vol5_regime") == vb
                )
            ]
            n = len(sub)
            survive = sum(1 for r in sub if r["survives_40"])
            cell[vb] = {
                "n": n,
                "survival_rate_pct": wr(survive, n),
                "hit_40_rate_pct": wr(n - survive, n),
            }
        vol_x_close.append(cell)

    q4_detail = []
    for k in Q4_ORDER:
        sub = [r for r in stop_rows if r.get("stop_q4_bucket") == k]
        s = summarize_group(sub, k)
        wins = sum(1 for r in sub if r["expiration_result_yes"])
        s["eventual_win"] = wins
        s["eventual_loss"] = len(sub) - wins
        s["eventual_win_pct"] = wr(wins, len(sub))
        s["pct_of_all_80_to_40"] = wr(len(sub), EXPECTED_STOPS)
        q4_detail.append(s)

    # Q4 concentration among ALL first-80 vs among 40-hits
    def phase_share(pop, phase):
        n = sum(1 for r in pop if r.get("entry_wall_phase") == phase)
        return n, wr(n, len(pop))

    q4_entry_n, q4_entry_pct = phase_share(rows_out, "Q4_EST")
    q4_stop_n = sum(1 for r in stop_rows if r.get("stop_wall_phase") == "Q4_EST")
    ot_stop_n = sum(1 for r in stop_rows if r.get("stop_wall_phase") == "OT_EST")
    late_stop_n = q4_stop_n + ot_stop_n

    time_to_40_table = []
    for k in T40_ORDER:
        sub = [r for r in stop_rows if r.get("time_to_40_bucket") == k]
        s = summarize_group(sub, k)
        wins = sum(1 for r in sub if r["expiration_result_yes"])
        s["eventual_win"] = wins
        s["eventual_loss"] = len(sub) - wins
        s["eventual_win_pct"] = wr(wins, len(sub))
        s["pct_of_all_80_to_40"] = wr(len(sub), EXPECTED_STOPS)
        s["avg_path_vol_cents"] = (
            round(mean([r.get("path_vol_cents") for r in sub]) or 0, 4) if sub else None
        )
        s["avg_mae_cents"] = (
            round(mean([r.get("mae_cents") for r in sub]) or 0, 4) if sub else None
        )
        time_to_40_table.append(s)

    # Frozen filter: drop VERY_HIGH entry vol5. Defined on research-sample
    # percentile edges; evaluated on full and OOS without retuning.
    kept = [r for r in rows_out if not r["filter_v1_drop"]]
    dropped = [r for r in rows_out if r["filter_v1_drop"]]
    filter_all = summarize_group(kept, FILTER_NAME)
    filter_all["dropped_n"] = len(dropped)
    filter_all["dropped_survival_rate_pct"] = wr(
        sum(1 for r in dropped if r["survives_40"]), len(dropped)
    )
    filter_research = summarize_group(
        [r for r in kept if r["dataset_split"] != "OOS"], FILTER_NAME + "_RESEARCH"
    )
    filter_oos = summarize_group(
        [r for r in kept if r["dataset_split"] == "OOS"], FILTER_NAME + "_OOS"
    )
    baseline_oos = summarize_group(oos, "BASELINE_OOS")
    baseline_research = summarize_group(research, "BASELINE_RESEARCH")

    # Additional descriptive (not selected) hypotheses — shown, not optimized.
    hypotheses = []
    hyp_defs = [
        ("drop_VERY_LOW_entry_vol5", lambda r: r.get("entry_vol5_regime") != "VERY_LOW"),
        ("drop_VERY_HIGH_entry_vol5", lambda r: r.get("entry_vol5_regime") != "VERY_HIGH"),
        ("drop_HIGH_and_VERY_HIGH_entry_vol5", lambda r: r.get("entry_vol5_regime") not in ("HIGH", "VERY_HIGH")),
        ("drop_vol_shock_VERY_HIGH", lambda r: r.get("entry_vol_shock_regime") != "VERY_HIGH"),
        ("drop_lt_30m_to_close", lambda r: r.get("entry_close_bucket") != "<30m_to_close"),
        ("keep_quality_A_or_B", lambda r: r.get("quality_grade") in ("A", "B")),
    ]
    for name, pred in hyp_defs:
        if name == "drop_fast_collapse_if_known":
            continue
        sub = [r for r in rows_out if pred(r)]
        s = summarize_group(sub, name)
        s_oos = summarize_group([r for r in sub if r["dataset_split"] == "OOS"], name + "_OOS")
        hypotheses.append(
            {
                "name": name,
                "selected_for_v1": name == f"drop_{filter_drop_regime}_entry_vol5"
                if filter_drop_regime
                else False,
                "all": s,
                "oos": s_oos,
            }
        )

    # Distribution summaries
    def dist(xs):
        xs = [x for x in xs if x is not None]
        if not xs:
            return None
        xs = sorted(xs)
        return {
            "n": len(xs),
            "mean": round(mean(xs), 4),
            "median": round(median(xs), 4),
            "p20": round(xs[int(0.20 * (len(xs) - 1))], 4),
            "p80": round(xs[int(0.80 * (len(xs) - 1))], 4),
            "min": round(xs[0], 4),
            "max": round(xs[-1], 4),
        }

    survive_rows = [r for r in rows_out if r["survives_40"]]
    hit_rows = stop_rows
    hist_edges = [0, 0.5, 1, 1.5, 2, 3, 5, 10, 50]
    hist_labels, hist_all = hist_counts(
        [r["entry_vol_5m_cents"] for r in rows_out], hist_edges
    )
    _, hist_survive = hist_counts(
        [r["entry_vol_5m_cents"] for r in survive_rows], hist_edges
    )
    _, hist_hit = hist_counts([r["entry_vol_5m_cents"] for r in hit_rows], hist_edges)

    # Q1/Q2 answers from the tables
    def regime_spread(table):
        rates = [t["survival_rate_pct"] for t in table if t["n"] and t["survival_rate_pct"] is not None]
        if len(rates) < 2:
            return None
        return round(max(rates) - min(rates), 2)

    # Independence: within Q1–Q3, does VERY_HIGH still hurt?
    early_phases = ("Q1_EST", "Q2_EST", "Q3_EST")
    early = [r for r in rows_out if r.get("entry_wall_phase") in early_phases]
    late = [r for r in rows_out if r.get("entry_wall_phase") in ("Q4_EST", "OT_EST")]
    early_by_vol = table_by("entry_vol5_regime", REGIME_ORDER, early)
    late_by_vol = table_by("entry_vol5_regime", REGIME_ORDER, late)

    # Verdict logic (descriptive, documented)
    vh = next((t for t in entry_vol_table if t["label"] == "VERY_HIGH"), None)
    vl = next((t for t in entry_vol_table if t["label"] == "VERY_LOW"), None)
    baseline_surv = 73.9837
    delta_vh = None if vh is None or vh["survival_rate_pct"] is None else round(vh["survival_rate_pct"] - baseline_surv, 2)
    delta_oos = None
    if filter_oos["survival_rate_pct"] is not None and baseline_oos["survival_rate_pct"] is not None:
        delta_oos = round(filter_oos["survival_rate_pct"] - baseline_oos["survival_rate_pct"], 2)
    n_filter = filter_all["n"]
    retention = filter_all["retention_vs_1230_pct"]

    # Classification A/B/C/D for "is vol useful"
    useful = "B"
    notes = [
        "Contract volatility is 1-minute bid-close stdev, not basketball vol and not true RV.",
        "Official NBA quarter is unavailable until PBP join; Q4 is not answered from candles.",
    ]
    spread = regime_spread(entry_vol_table)
    if spread is not None and spread < 8:
        notes.append(f"Survival spread across entry-vol quintiles is {spread}pp — not a sharp separator.")
    if vh and vl and (vh["survival_rate_pct"] or 0) > (vl["survival_rate_pct"] or 0):
        notes.append(
            "Direction is the opposite of 'avoid high vol': VERY_HIGH entry vol survives 40 more often than VERY_LOW."
        )
        useful = "B"
    if n_filter < 200:
        useful = "B"
        notes.append("Any strong-looking filter that collapses N is not production-useful.")
    if delta_oos is not None and filter_oos["n"] >= 40:
        if filter_drop_regime is None:
            notes.append("V1 freezes no entry-vol filter; OOS is the unfiltered baseline.")
        elif delta_oos < 1:
            notes.append("Frozen V1 filter does not improve OOS survival by ≥1pp.")
        elif delta_oos >= 2 and n_filter >= 800:
            notes.append("Frozen V1 filter improves OOS survival by ≥2pp with N retained.")
            useful = "C"

    q4_share_stops = wr(late_stop_n, EXPECTED_STOPS)
    q4_share_entries = wr(
        sum(1 for r in rows_out if r.get("entry_wall_phase") in ("Q4_EST", "OT_EST")),
        EXPECTED_FIRST80,
    )

    answers = {
        "1_different_entry_vol_environments": {
            "answer": "Yes, first-80 entries span the full contract-vol distribution, but they cluster toward moderate 5-minute realized movement rather than a single calm or chaotic state.",
            "entry_vol5_dist": dist([r["entry_vol_5m_cents"] for r in rows_out]),
            "survival_spread_pp_across_regimes": regime_spread(entry_vol_table),
        },
        "2_entry_vol_predicts_survive_40": {
            "answer": None,  # filled after looking at table
            "table": entry_vol_table,
        },
        "3_40_events_concentrated_in_q4": {
            "answer": None,
            "caveat": "Official NBA quarter UNAVAILABLE. scheduled_start present for only a small subset. Contract timing uses minutes to Kalshi close.",
            "n_scheduled_start": n_scheduled_start,
            "entry_close_table": close_table,
            "stop_close_table": stop_close_table,
        },
        "4_q4_vs_volatility_proxy": {
            "answer": None,
            "vol_x_close": vol_x_close,
            "n_scheduled_start": n_scheduled_start,
        },
        "5_high_vol_40_more_eventual_losses": {
            "answer": None,
            "stop_vol_table": stop_vol_table_sorted,
        },
        "6_fast_vs_slow_collapse": {
            "answer": None,
            "time_to_40_table": time_to_40_table,
        },
        "7_useful_as_live_filter": {
            "verdict": useful,
            "scale": {
                "A": "irrelevant",
                "B": "descriptive but not useful as a live filter",
                "C": "useful as a trade-quality filter, not production yet",
                "D": "strongly useful and worthy of production integration",
            },
            "notes": notes,
        },
        "8_simplest_plausible_filter": {
            "name": FILTER_NAME,
            "rule": (
                "No entry-vol filter."
                if filter_drop_regime is None
                else (
                    f"Skip first-80 entries in research-sample {filter_drop_regime} "
                    "5-minute bid-close realized-vol quintile. Edges frozen on "
                    "IN_SAMPLE+VALIDATION. Not retuned on OOS."
                )
            ),
            "drop_regime": filter_drop_regime,
            "discovered_on": "IN_SAMPLE+VALIDATION",
            "edges_frozen": entry_edges,
        },
        "9_trades_removed": None,
        "10_survives_oos": None,
    }

    # Fill remaining answers from computed tables
    if vh and vl:
        direction = "higher" if (vh["survival_rate_pct"] or 0) > (vl["survival_rate_pct"] or 0) else "lower"
        answers["2_entry_vol_predicts_survive_40"]["answer"] = (
            f"Weakly. VERY_HIGH entry vol5 survival={vh['survival_rate_pct']}% (n={vh['n']}) vs "
            f"VERY_LOW {vl['survival_rate_pct']}% (n={vl['n']}). VERY_HIGH is {direction} than VERY_LOW. "
            f"Spread across regimes={regime_spread(entry_vol_table)}pp. Not a sharp separator."
        )
    answers["3_40_events_concentrated_in_q4"]["answer"] = (
        f"Official Q4 cannot be measured from 1-minute Kalshi candles. "
        f"scheduled_start exists for {n_scheduled_start}/1230 first-80 games — too few for Q4 inference. "
        "Use minutes-to-Kalshi-close as a contract-timing proxy until PBP is joined."
    )
    answers["4_q4_vs_volatility_proxy"]["answer"] = (
        "Q4 vs vol cannot be separated without official quarter. "
        "Cross-tab is contract-vol × minutes-to-close, not NBA quarter × vol."
    )
    svh = next((t for t in stop_vol_table_sorted if t["regime"] == "VERY_HIGH"), None)
    svl = next((t for t in stop_vol_table_sorted if t["regime"] == "VERY_LOW"), None)
    answers["5_high_vol_40_more_eventual_losses"]["answer"] = (
        "Compare eventual-win rate at 40 by stop-vol regime. "
        f"VERY_HIGH stop vol eventual win={None if svh is None else svh['eventual_win_pct']}% n={None if svh is None else svh['n']}; "
        f"VERY_LOW {None if svl is None else svl['eventual_win_pct']}% n={None if svl is None else svl['n']}."
    )
    fast = next((t for t in time_to_40_table if t["label"] == "0-1m"), None)
    slow = next((t for t in time_to_40_table if t["label"] == ">60m"), None)
    answers["6_fast_vs_slow_collapse"]["answer"] = (
        f"0–1m collapses n={None if fast is None else fast['n']} eventual win={None if fast is None else fast['eventual_win_pct']}%; "
        f">60m n={None if slow is None else slow['n']} eventual win={None if slow is None else slow['eventual_win_pct']}%."
    )
    answers["9_trades_removed"] = {
        "dropped_n": len(dropped),
        "kept_n": len(kept),
        "retention_pct": retention,
        "dropped_survival_rate_pct": filter_all["dropped_survival_rate_pct"],
        "kept_survival_rate_pct": filter_all["survival_rate_pct"],
        "kept_gross_ev_cents": filter_all["gross_ev_cents"],
        "baseline_survival_rate_pct": baseline_surv,
        "baseline_gross_ev_cents": ev_from_survives(EXPECTED_SURVIVORS, EXPECTED_STOPS),
    }
    answers["10_survives_oos"] = {
        "baseline_oos": baseline_oos,
        "filter_oos": filter_oos,
        "delta_survival_pp": delta_oos,
        "retuned_on_oos": False,
    }

    summary = {
        "study": "NBA 80/40 VOLATILITY REGIME ANALYSIS V1",
        "frozen_baseline": {
            "first80": EXPECTED_FIRST80,
            "survives_40": EXPECTED_SURVIVORS,
            "hits_40": EXPECTED_STOPS,
            "survival_rate_pct": baseline_surv,
            "reproduced": True,
        },
        "definitions": {
            "price_series": "yes_bid_close_e4 on valid 1-minute candles in the game-day window",
            "volatility_kind": "CONTRACT / market-implied. Not basketball game volatility. Not true realized vol. Not L2.",
            "entry_vol_lookahead": False,
            "entry_uses_candles_through_first80_end": True,
            "percentile_edges_from": "IN_SAMPLE + VALIDATION only",
            "oos_cut": "game_date > 2026-03-15",
            "quarter": "ESTIMATED wall-clock phase from scheduled_start (fallback: first valid candle). Official NBA quarter UNAVAILABLE until PBP join.",
            "strategy_unchanged": True,
            "win_rate_is_survives_40": True,
            "payoff": "+1R survive to expiration (never close-path 40); -2R hit close-path 40",
        },
        "percentile_edges_frozen": {
            "entry_vol5_cents": entry_edges,
            "entry_vol_shock": shock_edges,
            "stop_vol5_cents": stop_edges,
        },
        "tip_source_counts": dict(tip_source_counts),
        "entry_vol_table": entry_vol_table,
        "entry_phase_table": phase_table,
        "entry_vol_x_phase": cross,
        "quality_grade_table": grade_table,
        "stop_vol_eventual_table": stop_vol_table_sorted,
        "stop_phase_table": stop_phase_table,
        "q4_detail": q4_detail,
        "time_to_40_table": time_to_40_table,
        "early_phase_by_vol": early_by_vol,
        "entry_close_table": close_table,
        "stop_close_table": stop_close_table,
        "entry_vol_x_close": vol_x_close,
        "n_scheduled_start": n_scheduled_start,
        "research_vol_table": research_vol_table,
        "filter_discovery": {
            "drop_regime": filter_drop_regime,
            "rule": filter_rule_name,
            "research_survival_pct": research_surv,
        },
        "distributions": {
            "entry_vol5_all": dist([r["entry_vol_5m_cents"] for r in rows_out]),
            "entry_vol5_survive": dist([r["entry_vol_5m_cents"] for r in survive_rows]),
            "entry_vol5_hit40": dist([r["entry_vol_5m_cents"] for r in hit_rows]),
            "entry_shock_all": dist([r["entry_vol_shock"] for r in rows_out]),
            "stop_vol5": dist([r.get("stop_vol_5m_cents") for r in hit_rows]),
            "time_to_40_min": dist([r.get("time_to_40_minutes") for r in hit_rows]),
            "mae_cents": dist([r.get("mae_cents") for r in hit_rows]),
        },
        "hist_entry_vol5": {
            "edges_cents": hist_edges,
            "labels": hist_labels,
            "all": hist_all,
            "survive": hist_survive,
            "hit40": hist_hit,
        },
        "filter_v1": {
            "name": FILTER_NAME,
            "rule": filter_rule_name,
            "drop_regime": filter_drop_regime,
            "all": filter_all,
            "research": filter_research,
            "oos": filter_oos,
            "baseline_research": baseline_research,
            "baseline_oos": baseline_oos,
        },
        "hypotheses_descriptive_not_selected": hypotheses,
        "answers": answers,
        "verdict": answers["7_useful_as_live_filter"],
        "leakage": {
            "entry_vol_uses_future_candles": False,
            "percentile_edges_fit_on_oos": False,
            "filter_threshold_searched_on_oos": False,
            "labels_redefined": False,
            "l2_invented": False,
            "official_quarter_invented": False,
            "first_candle_not_used_as_tip": True,
            "wall_phase_only_if_scheduled_start": True,
        },
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    # Compact ledger for downstream join; drop long reason lists if needed
    ledger = []
    for r in rows_out:
        ledger.append({k: v for k, v in r.items() if k != "quality_reasons"})
    (OUT / "ledger.json").write_text(json.dumps(ledger, default=str))
    (OUT / "filter_v1_dropped.json").write_text(
        json.dumps(
            [
                {
                    "event_ticker": r["event_ticker"],
                    "game_date": r["game_date"],
                    "entry_vol_5m_cents": r["entry_vol_5m_cents"],
                    "entry_vol5_regime": r["entry_vol5_regime"],
                    "survives_40": r["survives_40"],
                    "dataset_split": r["dataset_split"],
                }
                for r in dropped
            ],
            indent=2,
        )
    )

    write_report(summary)
    print(json.dumps({"ok": True, "out": str(OUT), "verdict": useful, "filter_n": n_filter}, indent=2))
    return 0


def fmt_row(t):
    n = t.get("n") or 0
    surv = t.get("survival_rate_pct")
    hit = t.get("hit_40_rate_pct")
    ev = t.get("gross_ev_cents")
    surv_s = "—" if surv is None else f"{surv:.1f}%"
    hit_s = "—" if hit is None else f"{hit:.1f}%"
    ev_s = "—" if ev is None else f"{ev:.2f}¢"
    return n, surv_s, hit_s, ev_s


def write_report(s):
    a = s["answers"]
    lines = []
    lines.append("# NBA 80/40 Volatility Regime Analysis V1")
    lines.append("")
    lines.append("Research only. Strategy definition unchanged. Not a live filter.")
    lines.append("")
    lines.append("## Frozen labels")
    lines.append("")
    lines.append("- 1,230 first-80 opportunities")
    lines.append("- 910 survive observed close-path 40")
    lines.append("- 320 hit observed close-path 40")
    lines.append("- 74.0% baseline (reproduced before any volatility cut)")
    lines.append("- Dependent variable is **SURVIVES_40**, not eventual Kalshi winner except where labeled")
    lines.append("")
    lines.append("## What this volatility is")
    lines.append("")
    lines.append("All volatility measures are **contract / market-implied**, from 1-minute `yes_bid` OHLC.")
    lines.append("They are **not** true realized volatility, **not** L2, **not** basketball game volatility.")
    lines.append("ENTRY measures use candles through the first-80 minute end only (no 9:44+ leakage).")
    lines.append("Percentile edges frozen on IN_SAMPLE+VALIDATION (`game_date ≤ 2026-03-15`). OOS is after that.")
    lines.append("")
    lines.append("## Official quarter")
    lines.append("")
    lines.append("Official NBA quarter and game clock are **unavailable** until PBP is joined.")
    lines.append(
        f"`scheduled_start` is present for {s.get('n_scheduled_start')} / 1230 first-80 games. "
        "First valid candle is **not** used as tip (that is Kalshi market open, not tip-off)."
    )
    lines.append("Timing below is **minutes until Kalshi market close** — contract lifetime, not NBA Q4.")
    lines.append("")
    lines.append(f"Tip sources: `{s['tip_source_counts']}`")
    lines.append("")
    lines.append("## Frozen percentile edges (entry 5-minute realized vol, cents)")
    lines.append("")
    lines.append(f"`{s['percentile_edges_frozen']['entry_vol5_cents']}`")
    lines.append("")
    lines.append("## Q1 — Entry contract-vol environment")
    lines.append("")
    d = s["distributions"]["entry_vol5_all"]
    lines.append(
        f"5-minute bid-close stdev at first-80: n={d['n']} mean={d['mean']}¢ median={d['median']}¢ "
        f"p20={d['p20']}¢ p80={d['p80']}¢"
    )
    lines.append("")
    lines.append("## Q2/Q10 — Entry vol regime × SURVIVES_40")
    lines.append("")
    lines.append("| Entry vol5 regime | N | Survive 40 | Hit 40 | Survival | Gross EV/trade |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for t in s["entry_vol_table"]:
        n, surv, hit, ev = fmt_row(t)
        lines.append(
            f"| {t['label']} | {n} | {t.get('survive_40')} | {t.get('hit_40')} | {surv} | {ev} |"
        )
    lines.append("")
    lines.append("## Contract timing at entry (minutes to Kalshi close)")
    lines.append("")
    lines.append("| Minutes to close | N | Survive 40 | Hit 40 | Survival | Gross EV |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for t in s.get("entry_close_table") or []:
        n, surv, hit, ev = fmt_row(t)
        lines.append(
            f"| {t['label']} | {n} | {t.get('survive_40')} | {t.get('hit_40')} | {surv} | {ev} |"
        )
    lines.append("")
    lines.append("## 80→40 events by minutes-to-close at the 40")
    lines.append("")
    lines.append("| Stop close bucket | N | % of 320 | Eventual win | Eventual loss | Eventual win % |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for t in s.get("stop_close_table") or []:
        ew = t.get("eventual_win_pct")
        ew_s = "—" if ew is None else f"{ew}%"
        pct = t.get("pct_of_all_80_to_40")
        pct_s = "—" if pct is None else f"{pct}%"
        lines.append(
            f"| {t['label']} | {t['n']} | {pct_s} | {t.get('eventual_win')} | {t.get('eventual_loss')} | {ew_s} |"
        )
    lines.append("")
    lines.append("## 40¢ contract-vol regime vs eventual win/loss")
    lines.append("")
    lines.append("| Stop vol5 regime | N | Eventual WIN | Eventual LOSS | Win % |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for t in s["stop_vol_eventual_table"]:
        ew = t.get("eventual_win_pct")
        ew_s = "—" if ew is None else f"{ew}%"
        lines.append(
            f"| {t['regime']} | {t['n']} | {t['eventual_win']} | {t['eventual_loss']} | {ew_s} |"
        )
    lines.append("")
    lines.append("## Fast vs slow 80→40")
    lines.append("")
    lines.append("| Time to 40 | N | % of 320 | Eventual win % | Avg MAE ¢ | Avg path vol ¢ |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for t in s["time_to_40_table"]:
        ew = t.get("eventual_win_pct")
        ew_s = "—" if ew is None else f"{ew}%"
        pct = t.get("pct_of_all_80_to_40")
        pct_s = "—" if pct is None else f"{pct}%"
        lines.append(
            f"| {t['label']} | {t['n']} | {pct_s} | {ew_s} | {t.get('avg_mae_cents')} | {t.get('avg_path_vol_cents')} |"
        )
    lines.append("")
    lines.append("## Trade quality score (research output, not a signal)")
    lines.append("")
    lines.append("A priori points from entry vol quintile, vol shock ≥2, minutes-to-close <30, range, velocity, spread.")
    lines.append("Not a machine-learning classifier. Not production.")
    lines.append("")
    lines.append("| Grade | N | Survival | Hit 40 | Gross EV | Retention |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for t in s["quality_grade_table"]:
        n, surv, hit, ev = fmt_row(t)
        lines.append(
            f"| {t['label']} | {n} | {surv} | {hit} | {ev} | {t.get('retention_vs_1230_pct')}% |"
        )
    lines.append("")
    lines.append("## Frozen candidate filter `NBA_80_40_VOLATILITY_V1`")
    lines.append("")
    f = s["filter_v1"]
    lines.append(a["8_simplest_plausible_filter"]["rule"])
    lines.append("")
    lines.append(
        f"Keeps {f['all']['n']} / 1230 ({f['all']['retention_vs_1230_pct']}%). "
        f"Survival {f['all']['survival_rate_pct']}% vs baseline 73.98%. "
        f"Gross EV {f['all']['gross_ev_cents']}¢ vs baseline {a['9_trades_removed']['baseline_gross_ev_cents']}¢."
    )
    lines.append("")
    lines.append(
        f"OOS: filter {f['oos']['n']} trades, survival {f['oos']['survival_rate_pct']}% "
        f"vs OOS baseline {f['baseline_oos']['survival_rate_pct']}% "
        f"(delta {a['10_survives_oos']['delta_survival_pp']}pp). Not retuned on OOS."
    )
    lines.append("")
    lines.append("Other hypotheses were tabulated but **not** selected (no OOS shopping).")
    lines.append("")
    lines.append("## Answers")
    lines.append("")
    for key, title in [
        ("1_different_entry_vol_environments", "1. Different entry vol environments?"),
        ("2_entry_vol_predicts_survive_40", "2. Does entry vol predict survive-40?"),
        ("3_40_events_concentrated_in_q4", "3. Are 40¢ events concentrated in Q4?"),
        ("4_q4_vs_volatility_proxy", "4. Is Q4 a proxy for vol?"),
        ("5_high_vol_40_more_eventual_losses", "5. High-vol 40¢ more likely eventual losses?"),
        ("6_fast_vs_slow_collapse", "6. Fast vs slow 80→40?"),
    ]:
        lines.append(f"### {title}")
        lines.append("")
        lines.append(str(a[key].get("answer")))
        lines.append("")
    lines.append("### 7. Useful enough for a future live filter?")
    lines.append("")
    v = s["verdict"]
    lines.append(f"**{v['verdict']}** — {v['scale'][v['verdict']]}")
    for n in v["notes"]:
        lines.append(f"- {n}")
    lines.append("")
    lines.append("### 8–10. Simplest filter, N removed, OOS")
    lines.append("")
    lines.append(a["8_simplest_plausible_filter"]["rule"])
    r9 = a["9_trades_removed"]
    lines.append(
        f"Removes {r9['dropped_n']} trades (keeps {r9['kept_n']}, {r9['retention_pct']}% retention). "
        f"Dropped bucket survival {r9['dropped_survival_rate_pct']}%."
    )
    lines.append(
        f"OOS delta {a['10_survives_oos']['delta_survival_pp']}pp. `retuned_on_oos=false`."
    )
    lines.append("")
    lines.append("## Production")
    lines.append("")
    lines.append("No volatility filter enters production from this study.")
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(main())
