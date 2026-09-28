"""±5 path-loss candle windows. Missing minutes are UNAVAILABLE. No forward-fill."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any

from roller.superasi.library import repo_root
from roller.superasi.models import SuperasiError
from roller.superasi.versions import WINDOW_RADIUS

OFFSETS = tuple(range(-WINDOW_RADIUS, WINDOW_RADIUS + 1))
ASKED_SIX_CSV = (
    repo_root()
    / "research"
    / "first80_asked_six_t40_surround_candles"
    / "t40_surround_pm5.csv"
)

# Locked reconciliation (do not fabricate missing +4/+5 bars).
LOCK_PATH_LOSSES = 299
LOCK_OFFSET0_SUM = 10318
LOCK_OFFSET_M1_SUM = 14663
LOCK_PRE_38_40 = 1


def load_asked_six_windows(path: Path | None = None) -> list[dict[str, Any]]:
    src = path or ASKED_SIX_CSV
    if not src.is_file():
        raise SuperasiError("PATH_WINDOW_DATA_REQUIRED", f"missing {src}")
    rows: list[dict[str, Any]] = []
    with src.open(newline="", encoding="utf-8") as fh:
        for raw in csv.DictReader(fh):
            rows.append(_from_asked_six_csv(raw))
    return rows


def attach_derived(windows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_trade: dict[str, dict[int, dict[str, Any]]] = defaultdict(dict)
    for w in windows:
        tid = str(w.get("ticker") or "")
        off = int(w["offset"])
        by_trade[tid][off] = w
    derived: dict[str, dict[str, Any]] = {}
    for tid, offs in by_trade.items():
        def bid(off: int) -> int | None:
            row = offs.get(off)
            if not row:
                return None
            return _int(row.get("yes_bid_close"))

        t40 = bid(0)
        prior = bid(-1)
        plus1 = bid(1)
        plus5 = bid(5)
        plus = [bid(o) for o in range(1, WINDOW_RADIUS + 1)]
        avail_plus = [x for x in plus if x is not None]
        printed = t40 is not None and t40 == 40
        fast = False
        if prior is not None and t40 is not None:
            fast = prior > 40 and t40 < 40 and (prior - t40) >= 10
        derived[tid] = {
            "ticker": tid,
            "prior_close": prior,
            "t40_close": t40,
            "close_1m": plus1,
            "close_5m": plus5,
            "min_close_5m": min(avail_plus) if avail_plus else None,
            "printed_at_barrier": printed,
            "fast_gap": fast,
            "prior_status": "OBSERVED" if prior is not None else "UNAVAILABLE",
            "t40_status": "OBSERVED" if t40 is not None else "UNAVAILABLE",
            "close_1m_status": "OBSERVED" if plus1 is not None else "UNAVAILABLE",
            "close_5m_status": "OBSERVED" if plus5 is not None else "UNAVAILABLE",
            "min_5m_status": "OBSERVED" if avail_plus else "UNAVAILABLE",
        }
    return derived


def apply_derived_to_trades(trades: list[dict[str, Any]], windows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    derived = attach_derived(windows)
    out = []
    for t in trades:
        rec = dict(t)
        d = derived.get(str(rec.get("ticker")))
        if d:
            rec["window_derived"] = d
        out.append(rec)
    return out


def aggregate(windows: list[dict[str, Any]]) -> dict[str, Any]:
    by_off: dict[int, list[int]] = {o: [] for o in OFFSETS}
    pre_3840: set[str] = set()
    tickers: set[str] = set()
    for w in windows:
        tid = str(w.get("ticker") or "")
        tickers.add(tid)
        off = int(w["offset"])
        bid = _int(w.get("yes_bid_close"))
        if bid is not None and off in by_off:
            by_off[off].append(bid)
        if off < 0 and bid is not None and 38 <= bid <= 40:
            pre_3840.add(tid)
    offsets = {}
    for off, xs in by_off.items():
        xs_sorted = sorted(xs)
        offsets[str(off)] = {
            "n": len(xs),
            "sum": sum(xs) if xs else None,
            "mean": None if not xs else {"numer": sum(xs), "denom": len(xs), "status": "OBSERVED"},
            "median": None if not xs else xs_sorted[len(xs_sorted) // 2],
        }
    return {
        "path_loss_n": len(tickers),
        "n_window_rows": len(windows),
        "offsets": offsets,
        "pre_t40_38_40_trades": len(pre_3840),
        "note": "CANDLE PATH ≠ FILL. Missing minutes are UNAVAILABLE.",
        "status": "OBSERVED",
    }


def validate_asked_six_locks(windows: list[dict[str, Any]]) -> None:
    agg = aggregate(windows)
    if agg["path_loss_n"] != LOCK_PATH_LOSSES:
        raise SuperasiError(
            "PATH_WINDOW_DATA_REQUIRED",
            f"path losses {agg['path_loss_n']} != {LOCK_PATH_LOSSES}",
        )
    o0 = agg["offsets"]["0"]["sum"]
    om1 = agg["offsets"]["-1"]["sum"]
    if o0 != LOCK_OFFSET0_SUM:
        raise SuperasiError("PATH_WINDOW_DATA_REQUIRED", f"offset 0 sum {o0} != {LOCK_OFFSET0_SUM}")
    if om1 != LOCK_OFFSET_M1_SUM:
        raise SuperasiError("PATH_WINDOW_DATA_REQUIRED", f"offset -1 sum {om1} != {LOCK_OFFSET_M1_SUM}")
    if agg["pre_t40_38_40_trades"] != LOCK_PRE_38_40:
        raise SuperasiError(
            "PATH_WINDOW_DATA_REQUIRED",
            f"pre-T40 38-40 {agg['pre_t40_38_40_trades']} != {LOCK_PRE_38_40}",
        )


def windows_from_bars(
    ticker: str,
    bars_by_offset: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build a long window from already-aligned bars. Do not invent offsets."""
    rows = []
    for off in OFFSETS:
        bar = bars_by_offset.get(off)
        if bar is None:
            rows.append(
                {
                    "ticker": ticker,
                    "offset": off,
                    "yes_bid_close": None,
                    "yes_ask_close": None,
                    "yes_bid_low": None,
                    "last": None,
                    "spread": None,
                    "tradable": None,
                    "candle_ts": None,
                    "status": "UNAVAILABLE",
                }
            )
            continue
        rows.append(_bar_row(ticker, off, bar))
    return rows


def _bar_row(ticker: str, off: int, bar: dict[str, Any]) -> dict[str, Any]:
    bid = _int(bar.get("yes_bid_close") if bar.get("yes_bid_close") is not None else bar.get("bid"))
    ask = _int(bar.get("yes_ask_close") if bar.get("yes_ask_close") is not None else bar.get("ask"))
    low = _int(bar.get("yes_bid_low") if bar.get("yes_bid_low") is not None else bar.get("low"))
    last = _int(bar.get("last") if bar.get("last") is not None else bar.get("last_cents"))
    spread = None if bid is None or ask is None else ask - bid
    return {
        "ticker": ticker,
        "offset": off,
        "yes_bid_close": bid,
        "yes_ask_close": ask,
        "yes_bid_low": low,
        "last": last,
        "spread": spread,
        "tradable": bar.get("tradable"),
        "candle_ts": bar.get("candle_ts") or bar.get("ts"),
        "status": "OBSERVED" if bid is not None else "UNAVAILABLE",
    }


def _from_asked_six_csv(raw: dict[str, str]) -> dict[str, Any]:
    bid = _int(raw.get("yes_bid_close_cents"))
    ask = _int(raw.get("yes_ask_close_cents"))
    return {
        "ticker": raw.get("ticker"),
        "internal_game_id": raw.get("event_id") or raw.get("game_id"),
        "sport": raw.get("sport"),
        "slice": raw.get("slice"),
        "offset": int(raw["offset_min"]),
        "yes_bid_close": bid,
        "yes_ask_close": ask,
        "yes_bid_low": _int(raw.get("yes_bid_low_cents")),
        "last": _int(raw.get("last_cents")),
        "spread": _int(raw.get("spread_cents")),
        "tradable": _bool(raw.get("tradable")),
        "candle_ts": raw.get("candle_ts_utc") or raw.get("candle_ts"),
        "status": "OBSERVED" if bid is not None else "UNAVAILABLE",
        "is_t40_bar": _bool(raw.get("is_t40_bar")),
    }


def _int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if value is True or value is False:
        return bool(value)
    if str(value).lower() in {"true", "1", "yes"}:
        return True
    if str(value).lower() in {"false", "0", "no"}:
        return False
    return None
