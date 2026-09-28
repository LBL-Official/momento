"""Four-partition 2H-last-10 measurement. Warehouse bars + PBP clock. No Austin."""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from roller.choosin_texas.houston import declared_lock_vs_entry_cents, declared_no_taker_cents
from roller.choosin_texas.katy.common import examine_at_mark, mean_cents, summarize_rule
from roller.choosin_texas.locks import PARTITIONS
from roller.choosin_texas.models import ChoosinTexasError
from roller.choosin_texas.sources import default_asked_six_csv
from roller.config import RollerConfig
from roller.warehouse.layout import observations_dir, pbp_dir
from roller.warehouse.partitioning import list_month_parquets

ENTRY_CENTS = 80
GAIN_CENTS = 20
HOLD_LOSS_CENTS = 80
STOP_CENTS = 40
SEASON = "2025-2026"
NBA_MARK_PERIOD = 4
NBA_MARK_REMAINING = 720
NCAAB_MARK_PERIOD = 2
NCAAB_MARK_REMAINING = 600
ISO_CLOCK = re.compile(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?$")

FOUR = (
    ("nba_2q", "NBA", "Q2", "NBA 2Q", NBA_MARK_PERIOD, NBA_MARK_REMAINING),
    ("nba_3q", "NBA", "Q3", "NBA 3Q", NBA_MARK_PERIOD, NBA_MARK_REMAINING),
    ("ncaab_h1_2", "NCAAB", "H1_2", "NCAAB 1H second 10", NCAAB_MARK_PERIOD, NCAAB_MARK_REMAINING),
    ("ncaab_h2_1", "NCAAB", "H2_1", "NCAAB 2H first 10", NCAAB_MARK_PERIOD, NCAAB_MARK_REMAINING),
)

# 2H last 10 clock conversion. NBA Q4 12:00 ≡ NCAAB 2H 10:00.
# Early last-10 (≤55): NBA Q4 rem > 6:00 ≡ NCAAB 2H rem > 5:00.
# Mid last-10 (≤45): NBA Q4 6:00–3:00 ≡ NCAAB 2H 5:00–2:30.
LAST10 = {
    "NBA": {"period": 4, "start_rem": 720, "early_cut": 360, "mid_lo": 180, "label": "Q4 12:00 → 2H last 10"},
    "NCAAB": {"period": 2, "start_rem": 600, "early_cut": 300, "mid_lo": 150, "label": "2H 10:00 = 2H last 10"},
}


def parse_utc(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)


def clock_to_seconds(value: object) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    iso = ISO_CLOCK.match(text)
    if iso is not None:
        hours = int(iso.group(1) or 0)
        mins = int(iso.group(2) or 0)
        secs = float(iso.group(3) or 0.0)
        return int(round(hours * 3600 + mins * 60 + secs))
    if ":" in text:
        left, right = text.split(":", 1)
        try:
            return int(left) * 60 + int(round(float(right)))
        except (TypeError, ValueError):
            return None
    try:
        return int(round(float(text)))
    except (TypeError, ValueError):
        return None


def period_num(value: object) -> int | None:
    text = str(value or "").strip().upper()
    if not text:
        return None
    if text.startswith("Q"):
        text = text[1:]
    if text.endswith("H") and text[0].isdigit():
        text = text[0]
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def e4_cents(value: object) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(round(int(str(value).strip()) / 100.0))
    except (TypeError, ValueError):
        return None


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def hold_pnl(won: bool) -> int:
    return GAIN_CENTS if won else -HOLD_LOSS_CENTS


def taker_8040_pnl(won: bool, hit_40: bool) -> int:
    if hit_40:
        return -STOP_CENTS
    return hold_pnl(won)


def load_four_trades() -> dict[str, list[dict[str, Any]]]:
    path = default_asked_six_csv()
    if not path.is_file():
        raise ChoosinTexasError("DATA_REQUIRED", f"missing {path}")
    wanted = {(row[1], row[2]): row[0] for row in FOUR}
    out: dict[str, list[dict[str, Any]]] = {key: [] for key in wanted.values()}
    with path.open(newline="", encoding="utf-8") as fh:
        for rec in csv.DictReader(fh):
            pid = wanted.get((str(rec.get("sport") or "").strip(), str(rec.get("slice") or "").strip()))
            if pid is None:
                continue
            out[pid].append(rec)
    locked = {p.partition_id: p.n for p in PARTITIONS}
    for pid, rows in out.items():
        if len(rows) != locked[pid]:
            raise ChoosinTexasError(
                "LOCK_MISMATCH",
                f"{pid} CSV N {len(rows)} != lock {locked[pid]}",
            )
    return out


def _load_bars(sport: str, tickers: set[str]) -> tuple[dict[str, list[tuple[datetime, int]]], dict[str, str]]:
    import pandas as pd

    cfg = RollerConfig()
    directory = observations_dir(cfg, sport=sport, season=SEASON)
    files = list_month_parquets(directory)
    if not files:
        raise ChoosinTexasError("DATA_REQUIRED", f"no observation parquet under {directory}")
    grouped: dict[str, list[tuple[datetime, int]]] = defaultdict(list)
    gids: dict[str, str] = {}
    for path in files:
        frame = pd.read_parquet(path, columns=["ticker", "available_at", "yes_bid_close", "internal_game_id"])
        frame = frame[frame["ticker"].isin(tickers)]
        for rec in frame.itertuples(index=False):
            stamp = parse_utc(rec.available_at)
            close = e4_cents(rec.yes_bid_close)
            if stamp is None or close is None:
                continue
            grouped[str(rec.ticker)].append((stamp, close))
            if rec.internal_game_id:
                gids[str(rec.ticker)] = str(rec.internal_game_id)
    for ticker, rows in grouped.items():
        rows.sort(key=lambda item: item[0])
        grouped[ticker] = rows
    return grouped, gids


def _load_pbp(sport: str, game_ids: set[str]) -> dict[str, list[dict[str, Any]]]:
    import pandas as pd

    cfg = RollerConfig()
    directory = pbp_dir(cfg, sport=sport, season=SEASON)
    files = list_month_parquets(directory)
    if not files:
        raise ChoosinTexasError("DATA_REQUIRED", f"no PBP parquet under {directory}")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in files:
        frame = pd.read_parquet(
            path,
            columns=["internal_game_id", "event_timestamp", "period", "clock", "home_score", "away_score"],
        )
        frame["internal_game_id"] = frame["internal_game_id"].astype(str)
        frame = frame[frame["internal_game_id"].isin(game_ids)]
        for rec in frame.itertuples(index=False):
            stamp = parse_utc(rec.event_timestamp)
            per = period_num(rec.period)
            rem = clock_to_seconds(rec.clock)
            if stamp is None or per is None or rem is None:
                continue
            grouped[str(rec.internal_game_id)].append(
                {
                    "ts": stamp,
                    "period": per,
                    "remaining": rem,
                    "home_score": None if rec.home_score in ("", None) else int(rec.home_score),
                    "away_score": None if rec.away_score in ("", None) else int(rec.away_score),
                }
            )
    for gid, rows in grouped.items():
        rows.sort(key=lambda item: item["ts"])
        grouped[gid] = rows
    return grouped


def first_mark(events: list[dict[str, Any]], *, period: int, mark: int) -> dict[str, Any] | None:
    eligible = [row for row in events if row["period"] == period and row["remaining"] <= mark]
    if not eligible:
        return None
    eligible.sort(key=lambda row: -int(row["remaining"]))
    return eligible[0]


def last10_stop(sport: str, period: int | None, remaining: int | None) -> int:
    """Active path stop inside converted 2H last 10. T40 elsewhere. Not a fill."""
    if period is None or remaining is None:
        return STOP_CENTS
    spec = LAST10[sport]
    if int(period) != int(spec["period"]):
        return STOP_CENTS
    rem = int(remaining)
    if rem > int(spec["start_rem"]):
        return STOP_CENTS
    if rem > int(spec["early_cut"]):
        return 55
    if rem >= int(spec["mid_lo"]):
        return 45
    return STOP_CENTS


def last10_open_state(events: list[dict[str, Any]], sport: str) -> dict[str, Any] | None:
    spec = LAST10[sport]
    return first_mark(events, period=int(spec["period"]), mark=int(spec["start_rem"]))


def last_bar_before(bars: list[tuple[datetime, int]], when: datetime) -> tuple[datetime, int] | None:
    chosen = None
    for stamp, close in bars:
        if stamp < when:
            chosen = (stamp, close)
        else:
            break
    return chosen


def already_stopped(bars: list[tuple[datetime, int]], *, entry: datetime | None, mark: datetime) -> bool:
    for stamp, close in bars:
        if entry is not None and stamp <= entry:
            continue
        if stamp >= mark:
            break
        if close <= 40:
            return True
    return False


def score_diff(home: int | None, away: int | None, side: str) -> int | None:
    if home is None or away is None:
        return None
    if side == "home":
        return home - away
    if side == "away":
        return away - home
    return None


def classify_price(price: int | None, *, lo: int, hi: int, stopped: bool) -> str:
    if price is None:
        return "PRICE_UNAVAILABLE"
    if stopped or price < lo:
        return "THROUGH_BAND"
    if price > hi:
        return "NOT_UNDERWATER"
    return "HEDGE_SCENARIO"


def apply_price_rule(base_rows: list[dict[str, Any]], *, lo: int, hi: int) -> list[dict[str, Any]]:
    out = []
    for raw in base_rows:
        row = dict(raw)
        if not raw.get("run_mark_reached"):
            row["action"] = "RUN_MARK_MISSING"
            row["in_price_band"] = False
            row["katy_pnl_cents"] = raw.get("hold_pnl_cents")
            row["katy_8040_pnl_cents"] = raw.get("taker_8040_pnl_cents")
            out.append(row)
            continue
        price = raw.get("yes_bid")
        stopped = bool(raw.get("t40_already_at_mark"))
        action = classify_price(None if price is None else int(price), lo=lo, hi=hi, stopped=stopped)
        lock = raw.get("lock_pnl_cents")
        hedge = action == "HEDGE_SCENARIO" and lock is not None
        row["in_price_band"] = price is not None and lo <= int(price) <= hi
        row["action"] = action
        row["katy_pnl_cents"] = lock if hedge else raw.get("hold_pnl_cents")
        row["katy_8040_pnl_cents"] = lock if hedge else raw.get("taker_8040_pnl_cents")
        out.append(row)
    return out


def score_price_cell(base_rows: list[dict[str, Any]], *, lo: int, hi: int) -> dict[str, Any]:
    applied = apply_price_rule(base_rows, lo=lo, hi=hi)
    reached = [
        r
        for r in applied
        if r.get("run_mark_reached") and r.get("taker_8040_pnl_cents") is not None and r.get("katy_8040_pnl_cents") is not None
    ]
    base = [int(r["taker_8040_pnl_cents"]) for r in reached]
    mixed = [int(r["katy_8040_pnl_cents"]) for r in reached]
    hedges = [r for r in reached if r.get("action") == "HEDGE_SCENARIO"]
    delta = int(sum(mixed) - sum(base)) if base else 0
    return {
        "price_lo": lo,
        "price_hi": hi,
        "n_hedge": len(hedges),
        "n_hedge_losers": sum(1 for r in hedges if r.get("won") is False),
        "n_hedge_winners": sum(1 for r in hedges if r.get("won") is True),
        "baseline_8040": mean_cents(base),
        "mixed_8040": mean_cents(mixed),
        "delta_sum_cents": delta,
        "delta_mean_cents": None if not base else delta / len(base),
    }


def measure_four() -> dict[str, dict[str, Any]]:
    trades = load_four_trades()
    cache: dict[str, tuple[dict[str, list[tuple[datetime, int]]], dict[str, str], dict[str, list[dict[str, Any]]]]] = {}
    out: dict[str, dict[str, Any]] = {}
    for pid, sport, _slice, label, period, mark in FOUR:
        recs = trades[pid]
        if sport not in cache:
            all_tickers = {
                str(r["ticker"])
                for key, rows in trades.items()
                for r in rows
                if (sport == "NBA" and key.startswith("nba_")) or (sport == "NCAAB" and key.startswith("ncaab_"))
            }
            bars, gids = _load_bars(sport, all_tickers)
            pbp = _load_pbp(sport, set(gids.values()))
            cache[sport] = (bars, gids, pbp)
        bars, gids, pbp = cache[sport]
        rows = []
        for rec in recs:
            ticker = str(rec["ticker"])
            won = _truthy(rec.get("W"))
            t40 = _truthy(rec.get("T40"))
            hold = hold_pnl(won)
            taker = taker_8040_pnl(won, t40)
            entry = parse_utc(rec.get("timestamp_utc") or rec.get("timestamp"))
            gid = gids.get(ticker)
            mark_row = None if not gid else first_mark(pbp.get(gid) or [], period=period, mark=mark)
            if mark_row is None:
                rows.append(
                    {
                        "trade_id": ticker,
                        "partition_id": pid,
                        "run_mark_reached": False,
                        "won": won,
                        "t40": t40,
                        "hold_pnl_cents": hold,
                        "taker_8040_pnl_cents": taker,
                    }
                )
                continue
            bar = last_bar_before(bars.get(ticker) or [], mark_row["ts"])
            price = None if bar is None else int(bar[1])
            stopped = already_stopped(bars.get(ticker) or [], entry=entry, mark=mark_row["ts"]) or (
                price is not None and price < 41
            )
            side = str(rec.get("side") or "").strip()
            rows.append(
                {
                    "trade_id": ticker,
                    "partition_id": pid,
                    "run_mark_reached": bar is not None,
                    "period": mark_row["period"],
                    "used_remaining": mark_row["remaining"],
                    "yes_bid": price,
                    "houston_no_taker_cents": None if price is None else declared_no_taker_cents(price),
                    "lock_pnl_cents": None if price is None else declared_lock_vs_entry_cents(price, entry_cents=ENTRY_CENTS),
                    "won": won,
                    "t40": t40,
                    "t40_already_at_mark": stopped,
                    "score_differential": score_diff(mark_row.get("home_score"), mark_row.get("away_score"), side),
                    "hold_pnl_cents": hold,
                    "taker_8040_pnl_cents": taker,
                    "fill_status": "FILL_UNAVAILABLE",
                    "season": SEASON,
                }
            )
        out[pid] = {
            "partition_id": pid,
            "label": label,
            "n_lock": len(recs),
            "rows": rows,
            "loser_exam": examine_at_mark(rows),
        }
    return out


def walk_clock_trail(
    bars: list[tuple[datetime, int]],
    events: list[dict[str, Any]],
    *,
    sport: str,
    entry: datetime | None,
    won: bool,
    csv_t40: bool,
) -> dict[str, Any]:
    """First valid 1m close that meets the converted last-10 stop. Candle path ≠ fill."""
    state = None
    j = 0
    skipped_nonpos = 0
    for stamp, close in bars:
        if entry is not None and stamp <= entry:
            continue
        while j < len(events) and events[j]["ts"] <= stamp:
            state = events[j]
            j += 1
        if close <= 0:
            skipped_nonpos += 1
            continue
        if state is None:
            continue
        stop = last10_stop(sport, state["period"], state["remaining"])
        if close <= stop:
            return {
                "reason": f"STOP_{stop}",
                "stop": stop,
                "obs_px": int(close),
                "quarter": int(state["period"]),
                "remaining": int(state["remaining"]),
                "theoretical_pnl": int(stop) - ENTRY_CENTS,
                "observed_pnl": int(close) - ENTRY_CENTS,
                "skipped_nonpos": skipped_nonpos,
            }
    if csv_t40:
        return {
            "reason": "CSV_T40_UNSEEN",
            "stop": STOP_CENTS,
            "obs_px": None,
            "quarter": None,
            "remaining": None,
            "theoretical_pnl": STOP_CENTS - ENTRY_CENTS,
            "observed_pnl": STOP_CENTS - ENTRY_CENTS,
            "skipped_nonpos": skipped_nonpos,
        }
    hold = hold_pnl(won)
    return {
        "reason": "HOLD",
        "stop": None,
        "obs_px": None,
        "quarter": None,
        "remaining": None,
        "theoretical_pnl": hold,
        "observed_pnl": hold,
        "skipped_nonpos": skipped_nonpos,
    }


def summarize_trail(rows: list[dict[str, Any]], *, book: str) -> dict[str, Any]:
    scored = [
        r
        for r in rows
        if r.get("taker_8040_pnl_cents") is not None and r.get("katy_8040_pnl_cents") is not None
    ]
    reached = [r for r in scored if r.get("run_mark_reached")]
    reasons = Counter(str(r.get("action") or "") for r in scored)
    theo = [int(r["katy_8040_pnl_cents"]) for r in scored]
    obs = [int(r["observed_pnl_cents"]) for r in scored if r.get("observed_pnl_cents") is not None]
    base = [int(r["taker_8040_pnl_cents"]) for r in scored]
    hold = [int(r["hold_pnl_cents"]) for r in scored if r.get("hold_pnl_cents") is not None]
    losers = [r for r in scored if r.get("won") is False]
    cut_winners = sum(
        1
        for r in reached
        if str(r.get("action") or "").startswith("STOP_")
        and r.get("won") is True
        and not r.get("t40")
        and r.get("action") != "STOP_40"
    )
    return {
        "book": book,
        "n_trades": len(rows),
        "n_run_mark_reached": len(reached),
        "n_stop_55": int(reasons.get("STOP_55", 0)),
        "n_stop_45": int(reasons.get("STOP_45", 0)),
        "n_stop_40": int(reasons.get("STOP_40", 0)) + int(reasons.get("CSV_T40_UNSEEN", 0)),
        "n_hold": int(reasons.get("HOLD", 0)),
        "n_hedge_scenario": int(reasons.get("STOP_55", 0)) + int(reasons.get("STOP_45", 0)),
        "n_hedge_losers": sum(1 for r in reached if r.get("action") in {"STOP_55", "STOP_45"} and r.get("won") is False),
        "n_hedge_winners": sum(1 for r in reached if r.get("action") in {"STOP_55", "STOP_45"} and r.get("won") is True),
        "cut_survivors_who_won": cut_winners,
        "always_8040": mean_cents(base),
        "always_hold": mean_cents(hold),
        "katy_vs_8040": mean_cents(theo),
        "katy_path": mean_cents(obs),
        "overlay_theo": mean_cents(theo),
        "overlay_obs": mean_cents(obs),
        "losers_hold": mean_cents([int(r["hold_pnl_cents"]) for r in losers if r.get("hold_pnl_cents") is not None]),
        "losers_katy_8040": mean_cents([int(r["katy_8040_pnl_cents"]) for r in losers if r.get("katy_8040_pnl_cents") is not None]),
        "delta_theo_mean": None if not base or not theo or len(base) != len(theo) else (sum(theo) - sum(base)) / len(base),
        "delta_obs_mean": None if not base or not obs or len(base) != len(obs) else (sum(obs) - sum(base)) / len(base),
        "reasons": dict(reasons),
        "note": "SCENARIO — NOT OBSERVED FILL. Independent of Austin. Books are never combined.",
    }


def measure_clock_trail() -> dict[str, dict[str, Any]]:
    """Independent 55/45 last-10 trail on the four locked books. No Austin."""
    trades = load_four_trades()
    cache: dict[str, tuple[dict[str, list[tuple[datetime, int]]], dict[str, str], dict[str, list[dict[str, Any]]]]] = {}
    out: dict[str, dict[str, Any]] = {}
    for pid, sport, _slice, label, _period, _mark in FOUR:
        recs = trades[pid]
        if sport not in cache:
            all_tickers = {
                str(r["ticker"])
                for key, rows in trades.items()
                for r in rows
                if (sport == "NBA" and key.startswith("nba_")) or (sport == "NCAAB" and key.startswith("ncaab_"))
            }
            bars, gids = _load_bars(sport, all_tickers)
            pbp = _load_pbp(sport, set(gids.values()))
            cache[sport] = (bars, gids, pbp)
        bars, gids, pbp = cache[sport]
        rows = []
        for rec in recs:
            ticker = str(rec["ticker"])
            won = _truthy(rec.get("W"))
            t40 = _truthy(rec.get("T40"))
            hold = hold_pnl(won)
            taker = taker_8040_pnl(won, t40)
            entry = parse_utc(rec.get("timestamp_utc") or rec.get("timestamp"))
            gid = gids.get(ticker)
            events = pbp.get(gid) or []
            mark_row = last10_open_state(events, sport)
            path = bars.get(ticker) or []
            if mark_row is None or not path:
                rows.append(
                    {
                        "trade_id": ticker,
                        "partition_id": pid,
                        "run_mark_reached": False,
                        "won": won,
                        "t40": t40,
                        "action": "RUN_MARK_MISSING",
                        "hold_pnl_cents": hold,
                        "taker_8040_pnl_cents": taker,
                        "katy_8040_pnl_cents": taker,
                        "observed_pnl_cents": taker,
                        "katy_pnl_cents": hold,
                    }
                )
                continue
            bar = last_bar_before(path, mark_row["ts"])
            price = None if bar is None else int(bar[1])
            stopped = already_stopped(path, entry=entry, mark=mark_row["ts"]) or (
                price is not None and price < 41
            )
            trail = walk_clock_trail(path, events, sport=sport, entry=entry, won=won, csv_t40=t40)
            side = str(rec.get("side") or "").strip()
            rows.append(
                {
                    "trade_id": ticker,
                    "partition_id": pid,
                    "run_mark_reached": True,
                    "period": mark_row["period"],
                    "used_remaining": mark_row["remaining"],
                    "yes_bid": price,
                    "houston_no_taker_cents": None if price is None else declared_no_taker_cents(price),
                    "lock_pnl_cents": None if trail.get("obs_px") is None else int(trail["obs_px"]) - ENTRY_CENTS,
                    "won": won,
                    "t40": t40,
                    "t40_already_at_mark": stopped,
                    "score_differential": score_diff(mark_row.get("home_score"), mark_row.get("away_score"), side),
                    "hold_pnl_cents": hold,
                    "taker_8040_pnl_cents": taker,
                    "action": trail["reason"],
                    "stop": trail.get("stop"),
                    "obs_px": trail.get("obs_px"),
                    "exit_period": trail.get("quarter"),
                    "exit_remaining": trail.get("remaining"),
                    "katy_8040_pnl_cents": trail["theoretical_pnl"],
                    "observed_pnl_cents": trail["observed_pnl"],
                    "katy_pnl_cents": trail["observed_pnl"],
                    "fill_status": "FILL_UNAVAILABLE",
                    "season": SEASON,
                }
            )
        out[pid] = {
            "partition_id": pid,
            "label": label,
            "n_lock": len(recs),
            "rows": rows,
            "loser_exam": examine_at_mark(rows),
            "summary": summarize_trail(rows, book=label),
        }
    return out
