"""Shared Path Engine V1 constants and helpers.

Research only. Does not change live FIRST01.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

SCRIPTS_DIR = Path(__file__).resolve().parent
NBA_SCRIPTS = SCRIPTS_DIR.parent
if str(NBA_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(NBA_SCRIPTS))

import nba_80_40_execution_audit as audit  # noqa: E402

ROOT = audit.ROOT
NORM = audit.NORM
OUT = ROOT / "derived" / "nba" / "momento_path_engine_v1"
SPEC_DIR = Path("/Users/user/Desktop/Momento/docs/research/nba/path-engine-v1")

HIT80 = audit.HIT80
HIT40 = audit.HIT40
EXPECTED_GAMES = 1362
EXPECTED_FIRST80 = 1230
EXPECTED_SURVIVORS = 910
EXPECTED_STOPS = 320

Q_UNCONDITIONAL = EXPECTED_STOPS / EXPECTED_FIRST80
EV_UNCONDITIONAL = 1.0 - 3.0 * Q_UNCONDITIONAL
BREAKEVEN_Q = 1.0 / 3.0

SPLIT_TRAIN_END = "2025-12-31"
SPLIT_VAL_END = "2026-03-15"

# Pre-registered reject-high-q thresholds (VALIDATION chooses among these).
FILTER_THRESHOLDS = (0.20, 0.25, 0.30, 0.3333)
MIN_ACCEPTANCE = 0.50
BRIER_IMPROVE = 0.95
ECE_TOLERANCE = 0.005
BUCKET_GAP_PP = 8.0
MIN_BUCKET_N = 30
L2_LAMBDA = 1.0

MODEL2A = [
    "feat_spread_cents",
    "feat_distance_from_80_cents",
    "feat_vol_5m_cents",
    "feat_vol_15m_cents",
    "feat_momentum_5m_cents",
    "feat_range_1m_cents",
    "feat_minutes_to_close",
    "feat_vol_shock",
    "feat_ix_vol5_x_minutes_to_close",
    "feat_ix_vol5_x_spread",
    "feat_ix_momentum5_x_spread",
    "feat_ix_range1m_x_vol_shock",
]

MODEL2B_EXTRA = [
    "feat_momentum_1m_cents",
    "feat_momentum_15m_cents",
    "feat_abs_change_5m_cents",
    "feat_range_5m_mean_cents",
    "feat_range_15m_mean_cents",
    "feat_range_15m_max_cents",
    "feat_up_count_15m",
    "feat_down_count_15m",
    "feat_mae_15m_cents",
    "feat_mfe_15m_cents",
    "feat_dist_from_15m_high_cents",
    "feat_dist_from_15m_low_cents",
    "feat_minutes_since_first_gw_candle",
]

MODEL2B = MODEL2A + MODEL2B_EXTRA

EXPLORATORY = [
    "feat_vol_3m_cents",
    "feat_vol_10m_cents",
    "feat_vol_30m_cents",
    "feat_momentum_3m_cents",
    "feat_momentum_10m_cents",
    "feat_momentum_30m_cents",
    "feat_range_3m_mean_cents",
    "feat_range_10m_mean_cents",
    "feat_range_30m_mean_cents",
    "feat_ix_vol15_x_minutes_to_close",
]

UNIVARIATE_TRAIN = MODEL2A + MODEL2B_EXTRA + EXPLORATORY

assert len(MODEL2A) == 12
assert len(MODEL2B) == 25


def dataset_split(game_date: str | None) -> str:
    if not game_date:
        return "UNSPLIT"
    if game_date <= SPLIT_TRAIN_END:
        return "TRAIN"
    if game_date <= SPLIT_VAL_END:
        return "VALIDATION"
    return "OOS"


def iso(ts):
    return audit.iso(ts)


def e4_to_cents(x):
    if x is None:
        return None
    return x / 100.0


def cents_or_none(x):
    if x is None:
        return None
    return float(x)


def ev_from_q(q: float | None) -> float | None:
    if q is None:
        return None
    return 1.0 - 3.0 * q


def wilson(k: int, n: int, z: float = 1.96):
    p, lo, hi = audit.wilson(k, n, z)
    if p is None:
        return None, None, None
    return p / 100.0, lo / 100.0, hi / 100.0


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=_json_default) + "\n")


def _json_default(o):
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, Path):
        return str(o)
    raise TypeError(type(o))


def write_parquet(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path)


def read_parquet_rows(path: Path) -> list[dict]:
    table = pq.read_table(path)
    names = table.column_names
    rows = []
    n = table.num_rows
    cols = {c: table.column(c) for c in names}
    for i in range(n):
        rows.append({c: cols[c][i].as_py() for c in names})
    return rows


def load_quotes(markets, games):
    """Game-window valid 1m candles. Same windowing as the audit scan."""
    from collections import defaultdict

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
                    "bid_o": audit._opt_int(get["yes_bid_open_e4"][i].as_py()),
                    "bid_h": audit._opt_int(get["yes_bid_high_e4"][i].as_py()),
                    "bid_l": audit._opt_int(get["yes_bid_low_e4"][i].as_py()),
                    "bid_c": audit._opt_int(get["yes_bid_close_e4"][i].as_py()),
                    "ask_o": audit._opt_int(get["yes_ask_open_e4"][i].as_py()),
                    "ask_h": audit._opt_int(get["yes_ask_high_e4"][i].as_py()),
                    "ask_l": audit._opt_int(get["yes_ask_low_e4"][i].as_py()),
                    "ask_c": audit._opt_int(get["yes_ask_close_e4"][i].as_py()),
                    "px_o": audit._opt_int(get["price_open_e4"][i].as_py()),
                    "px_h": audit._opt_int(get["price_high_e4"][i].as_py()),
                    "px_l": audit._opt_int(get["price_low_e4"][i].as_py()),
                    "px_c": audit._opt_int(get["price_close_e4"][i].as_py()),
                    "vol": audit._opt_int(get["volume_hundredths"][i].as_py()),
                }
            )
    for rows in quotes.values():
        rows.sort(key=lambda r: r["ts"])
    return quotes, meta


def index_at_ts(rows, ts):
    for i, r in enumerate(rows):
        if r["ts"] == ts:
            return i
    return None


def stdev(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return None
    return float(np.std(xs, ddof=1))


def mean(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    return float(sum(xs) / len(xs))


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sigmoid(z):
    z = np.clip(z, -30.0, 30.0)
    return 1.0 / (1.0 + np.exp(-z))
