"""Dynamic Path Engine V3 — shared constants. Research only."""

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
RAW = ROOT / "raw" / "nba_stats"
PBP_DIR = RAW / "pbp_v3"
BOX_DIR = RAW / "boxscore_summary"
CROSSWALK_PATH = NORM / "pbp" / "game_crosswalk.json"
V2_OUT = ROOT / "derived" / "nba" / "momento_game_path_engine_v2"
OUT = ROOT / "derived" / "nba" / "momento_dynamic_path_engine_v3"
SPEC_DIR = Path("/Users/user/Desktop/Momento/docs/research/nba/dynamic-path-engine-v3")

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
SEED = 42
BRIER_IMPROVE = 0.95
ECE_TOLERANCE = 0.005
L2_LAMBDA = 1.0
HAZARD_THRESHOLDS = (0.05, 0.10, 0.15, 0.20, 0.25)
PERSIST_N = (1, 2, 3)
MAX_ALIVE_MINUTES = 180


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


def ev_from_q(q):
    if q is None:
        return None
    return 1.0 - 3.0 * q


def wilson(k: int, n: int, z: float = 1.96):
    p, lo, hi = audit.wilson(k, n, z)
    if p is None:
        return None, None, None
    return p / 100.0, lo / 100.0, hi / 100.0


def utc_now():
    return datetime.now(timezone.utc).isoformat()


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
    if not rows:
        pq.write_table(pa.table({"_empty": pa.array([], type=pa.int8())}), path)
        return
    pq.write_table(pa.Table.from_pylist(rows), path)


def write_cols(path: Path, cols: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table(cols), path)


def read_parquet_rows(path: Path) -> list[dict]:
    table = pq.read_table(path)
    names = table.column_names
    if names == ["_empty"]:
        return []
    cols = {c: table.column(c) for c in names}
    n = table.num_rows
    return [{c: cols[c][i].as_py() for c in names} for i in range(n)]


def team_code_from_ticker(ticker: str | None) -> str | None:
    if not ticker or "-" not in ticker:
        return None
    return ticker.rsplit("-", 1)[-1].strip().upper() or None


def load_crosswalk() -> dict:
    return {r["event_id"]: r for r in json.loads(CROSSWALK_PATH.read_text())}


def sigmoid(z):
    z = np.clip(z, -30.0, 30.0)
    return 1.0 / (1.0 + np.exp(-z))


def load_quotes(markets, games):
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
                    "ask_o": audit._opt_int(get["yes_ask_open_e4"][i].as_py()),
                    "ask_c": audit._opt_int(get["yes_ask_close_e4"][i].as_py()),
                    "vol": audit._opt_int(get["volume_hundredths"][i].as_py()),
                }
            )
    for rows in quotes.values():
        rows.sort(key=lambda r: r["ts"])
    return quotes, meta


def brier(y, p):
    return float(np.mean((np.asarray(p) - np.asarray(y)) ** 2))


def log_loss(y, p):
    p = np.clip(np.asarray(p, dtype=float), 1e-12, 1 - 1e-12)
    y = np.asarray(y, dtype=float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def roc_auc(y, p):
    y = np.asarray(y).astype(int)
    p = np.asarray(p, dtype=float)
    n1 = int(y.sum())
    n0 = len(y) - n1
    if n0 == 0 or n1 == 0:
        return None
    order = np.argsort(p, kind="mergesort")
    ranks = np.empty(len(p), dtype=float)
    ranks[order] = np.arange(1, len(p) + 1, dtype=float)
    sp = p[order]
    i = 0
    while i < len(p):
        j = i
        while j + 1 < len(p) and sp[j + 1] == sp[i]:
            j += 1
        if j > i:
            avg = 0.5 * (ranks[order[i]] + ranks[order[j]])
            ranks[order[i : j + 1]] = avg
        i = j + 1
    u = ranks[y == 1].sum() - n1 * (n1 + 1) / 2.0
    return float(u / (n1 * n0))


def ece(y, p, n_bins=10):
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    total = 0.0
    n = len(y)
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        m = (p >= lo) & (p <= hi) if i == n_bins - 1 else (p >= lo) & (p < hi)
        k = int(m.sum())
        if k == 0:
            continue
        total += (k / n) * abs(float(y[m].mean()) - float(p[m].mean()))
    return float(total)
