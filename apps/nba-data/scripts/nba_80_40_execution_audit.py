#!/usr/bin/env python3
"""NBA 80¢ maker / 40¢ stop execution-realism audit.

Research only. Does not change live FIRST01. Does not invent L2, queue
position, or a production KalshiFeeModel.

Reproduces the existing first-80 study baseline (game-day tradable bid-close
cross) BEFORE any execution filter. If baseline counts do not match, exit 1.

Fill confidence uses ONLY the crossing candle (no later candles).
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(
    "/Users/user/Desktop/Momento/Backtesting Suite/Data/NBA/2025-2026/warehouse"
)
NORM = ROOT / "normalized" / "nba"
OUT = ROOT / "derived" / "nba" / "first80_execution_audit"

HIT80 = 8000
HIT40 = 4000
HIT39 = 3900
HIT38 = 3800
MAX_SPREAD = 1000  # 10¢, same as the original study
R_CENTS = 20  # +1R = +20¢ (80→100); -2R = -40¢ (80→40)

# A priori chronological cuts on game_date. Frozen before looking at OOS.
# Not taken from MLB B1 (those dates predate this NBA season).
SPLIT_RESEARCH_END = "2025-12-31"  # inclusive
SPLIT_VAL_END = "2026-03-15"  # inclusive; OOS is after this

EXPECTED_GAMES = 1362
EXPECTED_FIRST80 = 1230
EXPECTED_SURVIVORS = 910
EXPECTED_STOPS = 320

# Published Kalshi quadratic schedule (research estimate). Production
# FeeModel is UNRESOLVED / ZeroFeeModel — this is NOT wired into live risk.
TAKER_COEF = 0.07
MAKER_COEF = 0.0175


def _opt_int(v):
    return None if v is None else int(v)


def parse_ts(s):
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def parse_game_date(s):
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def dataset_split(game_date: str | None) -> str:
    if not game_date:
        return "UNSPLIT"
    if game_date <= SPLIT_RESEARCH_END:
        return "IN_SAMPLE"
    if game_date <= SPLIT_VAL_END:
        return "VALIDATION"
    return "OOS"


def season_regime(game_date: str | None) -> str:
    if not game_date:
        return "UNKNOWN"
    if game_date < "2026-01-01":
        return "EARLY"
    if game_date < "2026-04-01":
        return "MIDDLE"
    return "LATE"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float | None, float | None, float | None]:
    if n <= 0:
        return None, None, None
    p = k / n
    z2 = z * z
    den = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / den
    rad = z * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n) / den
    lo = max(0.0, center - rad)
    hi = min(1.0, center + rad)
    return round(p * 100, 4), round(lo * 100, 4), round(hi * 100, 4)


def rate(num, den):
    if den == 0:
        return None
    return round(100.0 * num / den, 4)


def ceil_e6(x: float) -> int:
    """Ceil dollars to 1e-6 (Kalshi trade-fee granularity)."""
    return int(math.ceil(x * 1_000_000.0 - 1e-12))


def quadratic_fee_e6(coef: float, contracts: int, price_e4: int) -> int:
    """Research estimate: ceil(coef * C * P * (1-P)) to $0.000001.

    Not a production KalshiFeeModel. Series multiplier assumed 1.
    KXNBAGAME maker-fee multiplier is UNKNOWN in the warehouse.
    """
    if contracts <= 0:
        return 0
    p = price_e4 / 10000.0
    raw = coef * contracts * p * (1.0 - p)
    return ceil_e6(raw)


def load_markets():
    t = pq.read_table(
        NORM / "markets" / "markets.parquet",
        columns=[
            "ticker",
            "event_id",
            "market_id",
            "team",
            "yes_subtitle",
            "result",
            "settlement_value_e4",
            "season_phase",
            "close_time",
        ],
    )
    rows = []
    for i in range(t.num_rows):
        rows.append(
            {
                "ticker": t.column("ticker")[i].as_py(),
                "event_id": t.column("event_id")[i].as_py(),
                "market_id": t.column("market_id")[i].as_py(),
                "team": t.column("team")[i].as_py()
                or t.column("yes_subtitle")[i].as_py(),
                "result": t.column("result")[i].as_py(),
                "settlement_value_e4": _opt_int(
                    t.column("settlement_value_e4")[i].as_py()
                ),
                "season_phase": t.column("season_phase")[i].as_py(),
                "close_ts": parse_ts(t.column("close_time")[i].as_py()),
            }
        )
    return rows


def load_games():
    t = pq.read_table(NORM / "games" / "nba_games.parquet")
    names = t.column_names
    rows = []
    for i in range(t.num_rows):
        row = {n: t.column(n)[i].as_py() for n in names}
        gd = parse_game_date(row.get("game_date"))
        if gd:
            row["game_window_start"] = int((gd + timedelta(hours=16)).timestamp())
            row["game_window_end"] = int((gd + timedelta(hours=52)).timestamp())
        else:
            row["game_window_start"] = None
            row["game_window_end"] = None
        rows.append(row)
    return rows


def settled_yes(m):
    if m["result"] == "yes":
        return True
    if m["result"] == "no":
        return False
    if m["settlement_value_e4"] == 10000:
        return True
    if m["settlement_value_e4"] == 0:
        return False
    return None


def quality(bid, ask, vol, had_quality):
    if bid is None or ask is None:
        return False
    if bid > ask:
        return False
    if ask - bid > MAX_SPREAD:
        return False
    if vol is not None and vol > 0:
        return True
    return had_quality


def scan(markets, games):
    """Same game-window tradable-cross as the original study, plus candle snapshot."""
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
        "yes_ask_open_e4",
        "yes_ask_high_e4",
        "yes_ask_low_e4",
        "yes_ask_close_e4",
        "price_open_e4",
        "price_high_e4",
        "price_low_e4",
        "price_close_e4",
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
                    "bid_o": _opt_int(get["yes_bid_open_e4"][i].as_py()),
                    "bid_h": _opt_int(get["yes_bid_high_e4"][i].as_py()),
                    "bid_l": _opt_int(get["yes_bid_low_e4"][i].as_py()),
                    "bid_c": _opt_int(get["yes_bid_close_e4"][i].as_py()),
                    "ask_o": _opt_int(get["yes_ask_open_e4"][i].as_py()),
                    "ask_h": _opt_int(get["yes_ask_high_e4"][i].as_py()),
                    "ask_l": _opt_int(get["yes_ask_low_e4"][i].as_py()),
                    "ask_c": _opt_int(get["yes_ask_close_e4"][i].as_py()),
                    "px_o": _opt_int(get["price_open_e4"][i].as_py()),
                    "px_h": _opt_int(get["price_high_e4"][i].as_py()),
                    "px_l": _opt_int(get["price_low_e4"][i].as_py()),
                    "px_c": _opt_int(get["price_close_e4"][i].as_py()),
                    "vol": _opt_int(get["volume_hundredths"][i].as_py()),
                }
            )

    first80 = {}
    first40_close = {}
    first40_low = {}
    first39_close = {}
    first38_close = {}
    subsequent_80 = {}
    for ticker, rows in quotes.items():
        rows.sort(key=lambda r: r["ts"])
        had_q = False
        seen_below_80 = False
        f80 = None
        for q in rows:
            if not quality(q["bid_c"], q["ask_c"], q["vol"], had_q):
                continue
            had_q = True
            if q["bid_c"] < HIT80:
                seen_below_80 = True
            if f80 is None and q["bid_c"] >= HIT80 and seen_below_80:
                f80 = q
                first80[ticker] = q
        if not f80:
            continue
        n80 = 0
        for q in rows:
            if q["ts"] <= f80["ts"]:
                continue
            if not quality(q["bid_c"], q["ask_c"], q["vol"], True):
                continue
            if q["bid_c"] >= HIT80:
                n80 += 1
            if ticker not in first40_close and q["bid_c"] <= HIT40:
                first40_close[ticker] = q
            if ticker not in first39_close and q["bid_c"] <= HIT39:
                first39_close[ticker] = q
            if ticker not in first38_close and q["bid_c"] <= HIT38:
                first38_close[ticker] = q
            if ticker not in first40_low and q["bid_l"] is not None and q["bid_l"] <= HIT40:
                first40_low[ticker] = q
        subsequent_80[ticker] = n80
        # Same-minute 80-and-40 on the entry candle (only possible via low).
        if (
            ticker not in first40_low
            and f80["bid_l"] is not None
            and f80["bid_l"] <= HIT40
        ):
            first40_low[ticker] = f80
    return {
        "first80": first80,
        "first40_close": first40_close,
        "first40_low": first40_low,
        "first39_close": first39_close,
        "first38_close": first38_close,
        "subsequent_80": subsequent_80,
        "meta": meta,
    }


def last_print_through_80(q) -> bool:
    """Last-trade OHLC includes 80¢. Not a maker fill. Not L2."""
    lo, hi = q["px_l"], q["px_h"]
    if lo is not None and hi is not None:
        return lo <= HIT80 <= hi
    c = q["px_c"]
    return c is not None and c == HIT80


def maker_fill_confidence(q) -> str:
    """Classify from the crossing candle only. Estimated, not a historical fill.

    HIGH: last trade printed through 80, volume, spread ≤ 5¢, bid still ≥ 80
          at close, bid range ≤ 15¢ (not a one-minute explosion).
    MEDIUM: last trade printed through 80, volume, bid close ≥ 80.
    LOW: tradable bid close ≥ 80 without last-trade evidence at 80.
    """
    spread = None
    if q["bid_c"] is not None and q["ask_c"] is not None:
        spread = q["ask_c"] - q["bid_c"]
    rng = None
    if q["bid_h"] is not None and q["bid_l"] is not None:
        rng = q["bid_h"] - q["bid_l"]
    vol = q["vol"] or 0
    touched = last_print_through_80(q)
    if (
        touched
        and vol > 0
        and spread is not None
        and 0 <= spread <= 500
        and q["bid_c"] is not None
        and q["bid_c"] >= HIT80
        and rng is not None
        and rng <= 1500
    ):
        return "HIGH"
    if touched and vol > 0 and q["bid_c"] is not None and q["bid_c"] >= HIT80:
        return "MEDIUM"
    return "LOW"


def iso(ts):
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def build_candidates(markets, games, scanned):
    by_event = defaultdict(list)
    for m in markets:
        by_event[m["event_id"]].append(m)
    games_by_event = {g["event_id"]: g for g in games}
    rows = []
    for event_id, ms in sorted(by_event.items()):
        g = games_by_event.get(event_id, {})
        hits = []
        for m in ms:
            q = scanned["first80"].get(m["ticker"])
            if q:
                hits.append((q["ts"], m["ticker"], m, q))
        hits.sort(key=lambda x: (x[0], x[1]))
        rec = {
            "event_id": event_id,
            "game_id": g.get("game_id") or event_id,
            "event_ticker": g.get("event_ticker"),
            "season_phase": g.get("season_phase") or (ms[0]["season_phase"] if ms else None),
            "game_date": g.get("game_date"),
            "home_team": g.get("home_team") or g.get("home_team_code"),
            "away_team": g.get("away_team") or g.get("away_team_code"),
            "status": "NO_FIRST_80",
            "dataset_split": dataset_split(g.get("game_date")),
            "regime": season_regime(g.get("game_date")),
        }
        if not hits:
            rows.append(rec)
            continue
        ts, ticker, m0, q = hits[0]
        if len([h for h in hits if h[0] == ts]) > 1:
            rec["status"] = "TIE_SAME_MINUTE"
            rows.append(rec)
            continue
        won = settled_yes(m0)
        c40 = scanned["first40_close"].get(ticker)
        l40 = scanned["first40_low"].get(ticker)
        rec.update(
            {
                "status": "FIRST_80",
                "market_id": m0["market_id"],
                "ticker": ticker,
                "team": m0["team"],
                "first_80_timestamp": ts,
                "first_80_utc": iso(ts),
                "entry_time_precision": "1m_candle",
                "executable_first_80_estimate": ts,
                "observed_first_80": ts,
                "entry_price_e4": HIT80,
                "entry_bid_open_e4": q["bid_o"],
                "entry_bid_high_e4": q["bid_h"],
                "entry_bid_low_e4": q["bid_l"],
                "entry_bid_close_e4": q["bid_c"],
                "entry_ask_open_e4": q["ask_o"],
                "entry_ask_high_e4": q["ask_h"],
                "entry_ask_low_e4": q["ask_l"],
                "entry_ask_close_e4": q["ask_c"],
                "entry_last_open_e4": q["px_o"],
                "entry_last_high_e4": q["px_h"],
                "entry_last_low_e4": q["px_l"],
                "entry_last_close_e4": q["px_c"],
                "entry_volume_hundredths": q["vol"],
                "trade_count": None,
                "trade_count_available": False,
                "spread_available": q["bid_c"] is not None and q["ask_c"] is not None,
                "entry_spread_e4": None
                if q["bid_c"] is None or q["ask_c"] is None
                else q["ask_c"] - q["bid_c"],
                "last_print_through_80": last_print_through_80(q),
                "maker_fill_confidence": maker_fill_confidence(q),
                "estimated_maker_fill": True,
                "historical_fill_unknown": True,
                "historical_partial_fill_information": "unavailable",
                "orderbook_depth_available": False,
                "market_data_type": "CANDLESTICK_TOP_OF_BOOK",
                "subsequent_80_crossings": scanned["subsequent_80"].get(ticker, 0),
                "first_40_close_ts": None if c40 is None else c40["ts"],
                "first_40_low_ts": None if l40 is None else l40["ts"],
                "stop_close_triggered": c40 is not None,
                "stop_low_triggered": l40 is not None,
                "stop_39_triggered": ticker in scanned["first39_close"],
                "stop_38_triggered": ticker in scanned["first38_close"],
                "same_bar_80_and_40_low": l40 is not None and l40["ts"] == ts,
                "expiration_result_yes": won,
                "close_ts": m0["close_ts"],
            }
        )
        rows.append(rec)
    return rows


def baseline_outcome(rec):
    """Original study: close-only 40 after first 80."""
    if rec["status"] != "FIRST_80":
        return None
    if rec["expiration_result_yes"] is None:
        return None
    if rec["stop_close_triggered"]:
        return "STOP"
    if rec["expiration_result_yes"]:
        return "WIN"
    return "LOSS_NO_STOP"


def scenario_stop(rec, mode: str) -> bool:
    if mode == "conservative":
        return rec["stop_low_triggered"]
    return rec["stop_close_triggered"]


def accept_confidence(conf: str, mode: str) -> bool:
    if mode == "aggressive":
        return True
    if mode == "baseline_exec":
        return conf in ("HIGH", "MEDIUM")
    if mode == "conservative":
        return conf == "HIGH"
    raise ValueError(mode)


def fees_for(outcome: str, maker_fee_on: bool) -> dict:
    entry_maker = quadratic_fee_e6(MAKER_COEF, 1, HIT80) if maker_fee_on else 0
    entry_taker = quadratic_fee_e6(TAKER_COEF, 1, HIT80)
    stop_taker = quadratic_fee_e6(TAKER_COEF, 1, HIT40)
    # Strategy assumes maker entry. Stop is IOC taker in production.
    entry = entry_maker
    exit_f = stop_taker if outcome == "STOP" else 0
    settle = 0
    return {
        "entry_fee_e6": entry,
        "entry_fee_if_taker_e6": entry_taker,
        "exit_fee_e6": exit_f,
        "settlement_fee_e6": settle,
        "total_fee_e6": entry + exit_f + settle,
        "maker_fee_assumed": maker_fee_on,
    }


def gross_cents(outcome: str) -> int:
    if outcome == "WIN":
        return R_CENTS
    if outcome == "STOP":
        return -2 * R_CENTS
    return 0


def apply_scenario(cands, mode: str, stop_level: str = "40_close"):
    accepted = []
    rejected = []
    for rec in cands:
        if rec["status"] != "FIRST_80" or rec["expiration_result_yes"] is None:
            continue
        conf = rec["maker_fill_confidence"]
        if not accept_confidence(conf, mode):
            rejected.append({**rec, "reject_reason": f"FILL_CONFIDENCE_{conf}"})
            continue
        if stop_level == "40_low":
            stopped = rec["stop_low_triggered"]
        elif stop_level == "39_close":
            stopped = rec["stop_39_triggered"]
        elif stop_level == "38_close":
            stopped = rec["stop_38_triggered"]
        else:
            stopped = rec["stop_close_triggered"]
        if stopped:
            outcome = "STOP"
        elif rec["expiration_result_yes"]:
            outcome = "WIN"
        else:
            outcome = "LOSS_NO_STOP"
        trade = {**rec, "outcome": outcome, "scenario": mode, "stop_level": stop_level}
        accepted.append(trade)
    return accepted, rejected


def summarize_trades(trades, label: str, maker_fee_on: bool = False):
    n = len(trades)
    wins = sum(1 for t in trades if t["outcome"] == "WIN")
    stops = sum(1 for t in trades if t["outcome"] == "STOP")
    leak = sum(1 for t in trades if t["outcome"] == "LOSS_NO_STOP")
    gross = [gross_cents(t["outcome"]) for t in trades]
    nets = []
    fee_sum_e6 = 0
    for t in trades:
        f = fees_for(t["outcome"], maker_fee_on)
        fee_sum_e6 += f["total_fee_e6"]
        # e6 dollars → cents: / 10000
        fee_cents = f["total_fee_e6"] / 10000.0
        nets.append(gross_cents(t["outcome"]) - fee_cents)
    wr, lo, hi = wilson(wins, n)
    ev_g = None if n == 0 else round(sum(gross) / n, 4)
    ev_n = None if n == 0 else round(sum(nets) / n, 4)
    ev_g_r = None if n == 0 else round((sum(gross) / n) / R_CENTS, 4)
    ev_n_r = None if n == 0 else round((sum(nets) / n) / R_CENTS, 4)
    return {
        "label": label,
        "trades": n,
        "wins": wins,
        "stops": stops,
        "loss_no_stop": leak,
        "win_rate_pct": wr,
        "win_rate_ci95": [lo, hi],
        "stop_rate_pct": rate(stops, n),
        "p_win_given_first80": wr,
        "p_no40_given_first80": rate(wins, n),  # WIN means never stopped
        "p_win_given_80_to_40": rate(
            0, stops
        ),  # once stopped, strategy records a stop; eventual win is separate
        "gross_ev_cents": ev_g,
        "net_ev_cents": ev_n,
        "gross_ev_R": ev_g_r,
        "net_ev_R": ev_n_r,
        "gross_pnl_cents": sum(gross),
        "net_pnl_cents": None if n == 0 else round(sum(nets), 4),
        "fees_e6": fee_sum_e6,
        "fees_cents": round(fee_sum_e6 / 10000.0, 6),
        "avg_winner_cents": R_CENTS if wins else None,
        "avg_loser_cents": -2 * R_CENTS if stops else None,
        "longest_losing_streak": longest_streak(trades, "STOP"),
        "sample_size": n,
        "maker_fee_on": maker_fee_on,
    }


def longest_streak(trades, outcome):
    ordered = sorted(trades, key=lambda t: (t.get("first_80_timestamp") or 0, t.get("ticker") or ""))
    best = cur = 0
    for t in ordered:
        if t["outcome"] == outcome:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def eventual_win_given_stop(cands, stopped_attr: str) -> dict:
    """P(eventual Kalshi yes | 80 then 40). Distinct from strategy stop P&L."""
    first = [c for c in cands if c["status"] == "FIRST_80" and c["expiration_result_yes"] is not None]
    hit = [c for c in first if c[stopped_attr]]
    still_win = [c for c in hit if c["expiration_result_yes"]]
    n = len(hit)
    wr, lo, hi = wilson(len(still_win), n)
    return {
        "n_80_to_40": n,
        "n_still_won": len(still_win),
        "pct": wr,
        "ci95": [lo, hi],
    }


def portfolio_sim(trades, max_concurrent: int | None, starting_capital: float = 10000.0, r_dollars: float = 100.0):
    """1R = r_dollars. Stop loses 2R. Cannot open if concurrent cap or 2R unavailable."""
    ordered = sorted(trades, key=lambda t: (t["first_80_timestamp"], t["ticker"]))
    capital = starting_capital
    peak = capital
    max_dd = 0.0
    open_pos = []  # (exit_ts, pnl_dollars)
    equity = []
    accepted = 0
    skipped = 0
    max_open = 0
    for t in ordered:
        ts = t["first_80_timestamp"]
        # close expired
        still = []
        for exit_ts, pnl in open_pos:
            if exit_ts <= ts:
                capital += pnl
            else:
                still.append((exit_ts, pnl))
        open_pos = still
        peak = max(peak, capital)
        max_dd = min(max_dd, capital - peak)
        cap_ok = max_concurrent is None or len(open_pos) < max_concurrent
        need = 2 * r_dollars
        if not cap_ok or capital < need:
            skipped += 1
            continue
        if t["outcome"] == "WIN":
            pnl = r_dollars
            exit_ts = t.get("close_ts") or (ts + 1)
        elif t["outcome"] == "STOP":
            pnl = -2 * r_dollars
            exit_ts = t.get("first_40_close_ts") or t.get("first_40_low_ts") or ts + 1
        else:
            pnl = 0.0
            exit_ts = t.get("close_ts") or ts + 1
        open_pos.append((exit_ts, pnl))
        accepted += 1
        max_open = max(max_open, len(open_pos))
        equity.append(capital)
    for _, pnl in open_pos:
        capital += pnl
    peak = max(peak, capital)
    max_dd = min(max_dd, capital - peak)
    return {
        "max_concurrent": max_concurrent if max_concurrent is not None else "unlimited",
        "starting_capital": starting_capital,
        "r_dollars": r_dollars,
        "ending_capital": round(capital, 2),
        "net_pnl": round(capital - starting_capital, 2),
        "return_on_capital_pct": round(100.0 * (capital - starting_capital) / starting_capital, 4),
        "max_drawdown": round(max_dd, 2),
        "accepted": accepted,
        "skipped_overlap": skipped,
        "max_open_observed": max_open,
    }


def by_split(trades, maker_fee_on: bool):
    out = {}
    for split in ("IN_SAMPLE", "VALIDATION", "OOS"):
        sub = [t for t in trades if t["dataset_split"] == split]
        out[split] = summarize_trades(sub, split, maker_fee_on)
    return out


def by_regime(trades, maker_fee_on: bool):
    out = {}
    for reg in ("EARLY", "MIDDLE", "LATE"):
        sub = [t for t in trades if t["regime"] == reg]
        out[reg] = summarize_trades(sub, reg, maker_fee_on)
    return out


def leakage_audit(cands, baseline_ok: bool) -> dict:
    first = [c for c in cands if c["status"] == "FIRST_80"]
    dups = len(first) - len({c["event_id"] for c in first})
    same_bar = sum(1 for c in first if c.get("same_bar_80_and_40_low"))
    return {
        "DATA_LEAKAGE_AUDIT": True,
        "baseline_reproduced": baseline_ok,
        "fill_confidence_uses_future_candles": False,
        "fill_confidence_uses_entry_candle_close": True,
        "fill_confidence_uses_eventual_outcome": False,
        "fill_confidence_uses_settlement": False,
        "thresholds_fit_on_oos": False,
        "thresholds_a_priori": True,
        "duplicate_game_entries": dups,
        "same_minute_80_and_40_via_bid_low": same_bar,
        "entry_timestamp_is_candle_end": True,
        "l2_invented": False,
        "mid_from_last_used_as_80": False,
        "notes": [
            "Maker-fill confidence uses only the crossing 1-minute candle (OHLC bid/ask/last + volume).",
            "Using that candle's close/high/low is same-bar information: the exact intraminute 80 time is unknown (entry_time_precision=1m_candle).",
            "Subsequent candle volume/volatility is not used (would be lookahead).",
            "Settlement is used only as the outcome label after the path is classified.",
            "Chronological splits were fixed before scenario metrics were computed.",
            "Production KalshiFeeModel is UNRESOLVED; fees here are a labeled research estimate.",
        ],
    }


def main():
    markets = load_markets()
    games = load_games()
    scanned = scan(markets, games)
    cands = build_candidates(markets, games, scanned)

    first = [c for c in cands if c["status"] == "FIRST_80" and c["expiration_result_yes"] is not None]
    survivors = [c for c in first if not c["stop_close_triggered"] and c["expiration_result_yes"]]
    stops = [c for c in first if c["stop_close_triggered"]]
    no80 = [c for c in cands if c["status"] == "NO_FIRST_80"]

    baseline_ok = (
        len(cands) == EXPECTED_GAMES
        and len(first) == EXPECTED_FIRST80
        and len(survivors) == EXPECTED_SURVIVORS
        and len(stops) == EXPECTED_STOPS
    )
    if not baseline_ok:
        print("BASELINE MISMATCH — stopping before execution filters.", file=sys.stderr)
        print(
            json.dumps(
                {
                    "games": len(cands),
                    "first80": len(first),
                    "survivors": len(survivors),
                    "stops": len(stops),
                    "no80": len(no80),
                    "expected": {
                        "games": EXPECTED_GAMES,
                        "first80": EXPECTED_FIRST80,
                        "survivors": EXPECTED_SURVIVORS,
                        "stops": EXPECTED_STOPS,
                    },
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    # Baseline strategy trades: all first-80, close-only stop.
    baseline_trades = []
    for c in first:
        outcome = "STOP" if c["stop_close_triggered"] else "WIN"
        if outcome == "WIN" and not c["expiration_result_yes"]:
            outcome = "LOSS_NO_STOP"
        baseline_trades.append({**c, "outcome": outcome, "scenario": "original_baseline"})

    conf_counts = defaultdict(int)
    for c in first:
        conf_counts[c["maker_fill_confidence"]] += 1

    agg, agg_rej = apply_scenario(cands, "aggressive")
    base_e, base_rej = apply_scenario(cands, "baseline_exec")
    cons, cons_rej = apply_scenario(cands, "conservative", stop_level="40_low")
    # Decomposition: do not conflate fill filter with stop-on-low.
    high_close, _ = apply_scenario(cands, "conservative", stop_level="40_close")
    all_low, _ = apply_scenario(cands, "aggressive", stop_level="40_low")

    maker_off = False
    s_orig = summarize_trades(baseline_trades, "original_baseline", maker_off)
    s_agg = summarize_trades(agg, "aggressive", maker_off)
    s_base = summarize_trades(base_e, "base_execution", maker_off)
    s_cons = summarize_trades(cons, "conservative", maker_off)
    s_high_close = summarize_trades(high_close, "high_fill_close_stop", maker_off)
    s_all_low = summarize_trades(all_low, "all_fills_low_stop", maker_off)

    # Fees on: maker 0.0175 at entry (if series charges maker fees).
    s_orig_fee = summarize_trades(baseline_trades, "original_baseline_maker_fee_on", True)
    s_base_fee = summarize_trades(base_e, "base_execution_maker_fee_on", True)
    s_cons_fee = summarize_trades(cons, "conservative_maker_fee_on", True)

    # Eventual win given 40 (observational, not strategy P&L)
    p40_close = eventual_win_given_stop(cands, "stop_close_triggered")
    p40_low = eventual_win_given_stop(cands, "stop_low_triggered")

    # Stop sensitivity on original population
    sens = {}
    for name, attr in (("40_close", "stop_close_triggered"), ("39_close", "stop_39_triggered"), ("38_close", "stop_38_triggered"), ("40_low", "stop_low_triggered")):
        tr = []
        for c in first:
            stopped = c[attr]
            outcome = "STOP" if stopped else ("WIN" if c["expiration_result_yes"] else "LOSS_NO_STOP")
            tr.append({**c, "outcome": outcome})
        sens[name] = summarize_trades(tr, name, False)

    ports = {}
    for k in (1, 2, 3, 5, None):
        ports[str(k) if k else "unlimited"] = portfolio_sim(baseline_trades, k)
    ports_cons = {}
    for k in (1, 2, 3, 5, None):
        ports_cons[str(k) if k else "unlimited"] = portfolio_sim(cons, k)

    wr_b, lo_b, hi_b = wilson(len(survivors), len(first))

    degradation = [
        {
            "step": "original_observed_no40",
            "win_rate_pct": wr_b,
            "n": len(first),
            "note": "P(never tradable bid_close≤40 | first 80). Not a fill.",
        },
        {
            "step": "aggressive_assume_all_fills",
            "win_rate_pct": s_agg["win_rate_pct"],
            "n": s_agg["trades"],
            "note": "Same population as baseline; LOW+MEDIUM+HIGH accepted.",
        },
        {
            "step": "base_require_last_trade_through_80",
            "win_rate_pct": s_base["win_rate_pct"],
            "n": s_base["trades"],
            "note": "Reject LOW (bid≥80 without last-print evidence). Close stop unchanged.",
        },
        {
            "step": "high_fill_only_close_stop",
            "win_rate_pct": s_high_close["win_rate_pct"],
            "n": s_high_close["trades"],
            "note": "Fill filter only. Stop still bid_close≤40. Isolates maker-confidence from stop path.",
        },
        {
            "step": "all_fills_stop_on_bid_low",
            "win_rate_pct": s_all_low["win_rate_pct"],
            "n": s_all_low["trades"],
            "note": "No fill filter. Stop if bid_low≤40. This is the main win-rate drop.",
        },
        {
            "step": "conservative_high_only_stop_on_bid_low",
            "win_rate_pct": s_cons["win_rate_pct"],
            "n": s_cons["trades"],
            "note": "HIGH only; stop if bid_low≤40 (same-bar possible).",
        },
        {
            "step": "conservative_plus_research_taker_stop_fee_maker_entry_0",
            "win_rate_pct": s_cons["win_rate_pct"],
            "net_ev_R": s_cons["net_ev_R"],
            "n": s_cons["trades"],
            "note": "Win rate unchanged by fees; EV reduced. Maker fee multiplier UNKNOWN — this path assumes 0 maker fee, taker stop fee.",
        },
        {
            "step": "conservative_plus_maker_and_taker_fees",
            "win_rate_pct": s_cons_fee["win_rate_pct"],
            "net_ev_R": s_cons_fee["net_ev_R"],
            "n": s_cons_fee["trades"],
            "note": "If KXNBAGAME charges maker fees at 0.0175 quadratic.",
        },
        {
            "step": "conservative_max_concurrent_1",
            "win_rate_pct": None,
            "n": ports_cons["1"]["accepted"],
            "net_pnl": ports_cons["1"]["net_pnl"],
            "note": "Skipped overlapping signals; win rate of remaining trades is a selected subset.",
        },
    ]

    summary = {
        "price_interpretation": {
            "yes_bid_ohlc": "1-minute Kalshi yes_bid top-of-book OHLC. Not last, not mid, not L2.",
            "yes_ask_ohlc": "1-minute Kalshi yes_ask top-of-book OHLC.",
            "price_ohlc": "1-minute last-trade OHLC (Kalshi candle price.*).",
            "first_80_original": "first tradable yes_bid_close >= 8000 after a prior tradable close < 8000, game-day window",
            "first_40_original": "later tradable yes_bid_close <= 4000",
            "maker_buy_at_80": "Resting bid. Bid>=80 does not prove a maker fill. Last-trade through 80 is evidence a trade occurred at that price, still not queue position.",
            "stop_at_40": "Production liquidation is taker IOC. Candle bid_close<=40 means the bid printed 40 at minute end. bid_low<=40 means the bid traded as low as 40 inside the minute. Neither proves a 40.00 fill.",
            "spread": "ask_close - bid_close on the crossing candle. Candle range is NOT used as spread.",
            "orderbook_depth_available": False,
        },
        "fees": {
            "production_fee_model": "UNRESOLVED. ZeroFeeModel is a paper placeholder. Not used here as truth.",
            "research_formula": "ceil_6dp(coef * C * P * (1-P)), M=1",
            "taker_coef": TAKER_COEF,
            "maker_coef": MAKER_COEF,
            "kxnbagame_maker_multiplier": "UNKNOWN_NOT_IN_WAREHOUSE",
            "settlement_fee": "documented 0 for simple yes/no",
            "per_contract_e6": {
                "maker_entry_80": quadratic_fee_e6(MAKER_COEF, 1, HIT80),
                "taker_entry_80": quadratic_fee_e6(TAKER_COEF, 1, HIT80),
                "taker_stop_40": quadratic_fee_e6(TAKER_COEF, 1, HIT40),
            },
            "label": "RESEARCH_PUBLISHED_SCHEDULE_ESTIMATE",
        },
        "baseline": {
            "games": len(cands),
            "no_first_80": len(no80),
            "first80_settled": len(first),
            "survivors_no40": len(survivors),
            "stops_40_close": len(stops),
            "strategy_win_rate_pct": wr_b,
            "strategy_win_rate_ci95": [lo_b, hi_b],
            "reproduced": True,
            "p_win_kalshi_yes": rate(sum(1 for c in first if c["expiration_result_yes"]), len(first)),
            "p_no40": rate(len(survivors), len(first)),
            "p_eventual_win_given_40_close": p40_close,
            "p_eventual_win_given_40_low": p40_low,
            "loss_no_stop": sum(1 for t in baseline_trades if t["outcome"] == "LOSS_NO_STOP"),
        },
        "fill_confidence_counts": dict(conf_counts),
        "fill_confidence_rules": {
            "uses_future_candles": False,
            "HIGH": "last-trade OHLC includes 80 AND volume>0 AND close spread<=5¢ AND bid_close>=80 AND bid range<=15¢",
            "MEDIUM": "last-trade OHLC includes 80 AND volume>0 AND bid_close>=80",
            "LOW": "tradable bid_close>=80 without last-trade evidence at 80",
            "not_a_historical_fill": True,
        },
        "models": {
            "original_baseline": s_orig,
            "aggressive_execution": s_agg,
            "base_execution": s_base,
            "conservative_execution": s_cons,
            "high_fill_close_stop": s_high_close,
            "all_fills_bid_low_stop": s_all_low,
            "original_baseline_maker_fee_on": s_orig_fee,
            "base_execution_maker_fee_on": s_base_fee,
            "conservative_execution_maker_fee_on": s_cons_fee,
        },
        "rejected": {
            "aggressive": len(agg_rej),
            "base": len(base_rej),
            "conservative": len(cons_rej),
        },
        "stop_sensitivity": sens,
        "splits": {
            "cuts": {
                "IN_SAMPLE": f"game_date <= {SPLIT_RESEARCH_END}",
                "VALIDATION": f"{SPLIT_RESEARCH_END} < game_date <= {SPLIT_VAL_END}",
                "OOS": f"game_date > {SPLIT_VAL_END}",
            },
            "original_baseline": by_split(baseline_trades, False),
            "base_execution": by_split(base_e, False),
            "conservative_execution": by_split(cons, False),
        },
        "regimes": {
            "cuts": {"EARLY": "< 2026-01-01", "MIDDLE": "2026-01-01 .. 2026-03-31", "LATE": ">= 2026-04-01"},
            "original_baseline": by_regime(baseline_trades, False),
            "conservative_execution": by_regime(cons, False),
        },
        "portfolio": {"original_baseline": ports, "conservative": ports_cons},
        "degradation": degradation,
        "leakage": leakage_audit(cands, True),
        "research_console": "NOT_WIRED. frontend/research-console is the MLB B1 research OS. This audit is a standalone NBA warehouse artifact.",
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    # Ledgers
    def ledger_row(t):
        f = fees_for(t["outcome"], False)
        return {
            "game_id": t.get("game_id"),
            "market_id": t.get("market_id"),
            "event_ticker": t.get("event_ticker"),
            "team": t.get("team"),
            "game_date": t.get("game_date"),
            "dataset_split": t.get("dataset_split"),
            "regime": t.get("regime"),
            "season_phase": t.get("season_phase"),
            "first_80_timestamp": t.get("first_80_timestamp"),
            "first_80_utc": t.get("first_80_utc"),
            "entry_price": 0.80,
            "entry_confidence": t.get("maker_fill_confidence"),
            "entry_candle_open": t.get("entry_bid_open_e4"),
            "entry_candle_high": t.get("entry_bid_high_e4"),
            "entry_candle_low": t.get("entry_bid_low_e4"),
            "entry_candle_close": t.get("entry_bid_close_e4"),
            "entry_candle_volume": t.get("entry_volume_hundredths"),
            "entry_last_low": t.get("entry_last_low_e4"),
            "entry_last_high": t.get("entry_last_high_e4"),
            "entry_spread_e4": t.get("entry_spread_e4"),
            "last_print_through_80": t.get("last_print_through_80"),
            "subsequent_80_crossings": t.get("subsequent_80_crossings"),
            "first_40_timestamp": t.get("first_40_close_ts"),
            "stop_triggered": t["outcome"] == "STOP",
            "stop_price_assumed": 0.40 if t["outcome"] == "STOP" else None,
            "expiration_result": t.get("expiration_result_yes"),
            "winner_or_stop": t["outcome"],
            "gross_pnl_cents": gross_cents(t["outcome"]),
            "entry_fee_e6": f["entry_fee_e6"],
            "exit_fee_e6": f["exit_fee_e6"],
            "settlement_fee_e6": f["settlement_fee_e6"],
            "net_pnl_cents": gross_cents(t["outcome"]) - f["total_fee_e6"] / 10000.0,
            "scenario": t.get("scenario"),
        }

    (OUT / "ledger_baseline.json").write_text(
        json.dumps([ledger_row(t) for t in baseline_trades]) + "\n"
    )
    (OUT / "ledger_conservative.json").write_text(
        json.dumps([ledger_row(t) for t in cons]) + "\n"
    )
    (OUT / "rejected_conservative.json").write_text(
        json.dumps(
            [
                {
                    "event_ticker": r["event_ticker"],
                    "team": r.get("team"),
                    "confidence": r.get("maker_fill_confidence"),
                    "reason": r.get("reject_reason"),
                    "game_date": r.get("game_date"),
                }
                for r in cons_rej
            ]
        )
        + "\n"
    )
    (OUT / "candidates.json").write_text(json.dumps(cands) + "\n")

    print(json.dumps({
        "baseline_ok": True,
        "first80": len(first),
        "survivors": len(survivors),
        "stops": len(stops),
        "confidence": dict(conf_counts),
        "models": {
            k: {
                "trades": v["trades"],
                "win_rate_pct": v["win_rate_pct"],
                "ci95": v["win_rate_ci95"],
                "stop_rate_pct": v["stop_rate_pct"],
                "gross_ev_R": v["gross_ev_R"],
                "net_ev_R": v["net_ev_R"],
            }
            for k, v in summary["models"].items()
        },
        "p_eventual_win_40_close": p40_close,
        "splits_baseline": {
            k: {"n": v["trades"], "wr": v["win_rate_pct"], "ci": v["win_rate_ci95"]}
            for k, v in summary["splits"]["original_baseline"].items()
        },
        "out": str(OUT),
    }, indent=2))


if __name__ == "__main__":
    main()
