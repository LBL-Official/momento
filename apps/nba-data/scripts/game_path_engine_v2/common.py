"""Shared Game Path Engine V2 constants and helpers.

Research only. Does not change live FIRST01, Path Engine V1, or the frozen audit.
"""

from __future__ import annotations

import json
import math
import subprocess
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
OUT = ROOT / "derived" / "nba" / "momento_game_path_engine_v2"
SPEC_DIR = Path("/Users/user/Desktop/Momento/docs/research/nba/game-path-engine-v2")

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
MIN_BUCKET_N_TRAIN = 40
MIN_BUCKET_N_VAL = 30
MIN_LEAF = 40
MIN_ACCEPTANCE_PROD = 0.50
MIN_ACCEPTANCE_RESEARCH = 0.20
EV_MARGIN = 0.03
BH_Q = 0.10
DELTA_Q_TRAIN = 0.04
BRIER_IMPROVE = 0.95
ECE_TOLERANCE = 0.005
BUCKET_GAP_PP = 8.0
MIN_RISK_BUCKET_N = 30
L2_LAMBDA = 1.0
PRIMARY_ALIGN = {"HIGH", "MEDIUM"}

FROZEN_SCORE_BINS = [
    ("large_deficit", None, -15),
    ("medium_deficit", -14, -8),
    ("small_deficit", -7, -1),
    ("tie", 0, 0),
    ("small_lead", 1, 7),
    ("medium_lead", 8, 14),
    ("large_lead", 15, None),
]


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
    if not rows:
        pq.write_table(pa.table({"_empty": pa.array([], type=pa.int8())}), path)
        return
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path)


def read_parquet_rows(path: Path) -> list[dict]:
    table = pq.read_table(path)
    names = table.column_names
    if names == ["_empty"]:
        return []
    rows = []
    n = table.num_rows
    cols = {c: table.column(c) for c in names}
    for i in range(n):
        rows.append({c: cols[c][i].as_py() for c in names})
    return rows


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def git_commit() -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "-C", "/Users/user/Desktop/Momento", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip() or None
    except Exception:  # noqa: BLE001
        return None


def team_code_from_ticker(ticker: str | None) -> str | None:
    if not ticker or "-" not in ticker:
        return None
    code = ticker.rsplit("-", 1)[-1].strip().upper()
    return code or None


def load_crosswalk() -> dict:
    rows = json.loads(CROSSWALK_PATH.read_text())
    return {r["event_id"]: r for r in rows}


def load_quotes(markets, games):
    """Game-window valid 1m candles. Same windowing as the frozen audit."""
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


def sigmoid(z):
    z = np.clip(z, -30.0, 30.0)
    return 1.0 / (1.0 + np.exp(-z))


def frozen_score_bucket(diff: int | None) -> str | None:
    if diff is None:
        return None
    if diff <= -15:
        return "large_deficit"
    if -14 <= diff <= -8:
        return "medium_deficit"
    if -7 <= diff <= -1:
        return "small_deficit"
    if diff == 0:
        return "tie"
    if 1 <= diff <= 7:
        return "small_lead"
    if 8 <= diff <= 14:
        return "medium_lead"
    return "large_lead"


def rate_ci(k: int, n: int) -> dict:
    q, lo, hi = wilson(k, n)
    return {
        "n": n,
        "k": k,
        "q": q,
        "wilson_lo": lo,
        "wilson_hi": hi,
        "ev": ev_from_q(q),
        "delta_q": None if q is None else q - Q_UNCONDITIONAL,
        "delta_ev": None if q is None else ev_from_q(q) - EV_UNCONDITIONAL,
    }


def two_prop_p(k1: int, n1: int, k0: int, n0: int) -> float | None:
    if n1 <= 0 or n0 <= 0:
        return None
    p1 = k1 / n1
    p0 = k0 / n0
    p = (k1 + k0) / (n1 + n0)
    var = p * (1.0 - p) * (1.0 / n1 + 1.0 / n0)
    if var <= 0:
        return None
    z = (p1 - p0) / math.sqrt(var)
    return float(2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0)))))


def benjamini_hochberg(pvals: list[float | None], q: float = BH_Q) -> list[bool]:
    indexed = [(i, p) for i, p in enumerate(pvals) if p is not None]
    m = len(indexed)
    out = [False] * len(pvals)
    if m == 0:
        return out
    indexed.sort(key=lambda t: t[1])
    cutoff = None
    for rank, (i, p) in enumerate(indexed, start=1):
        if p <= q * rank / m:
            cutoff = rank
    if cutoff is None:
        return out
    for rank, (i, _p) in enumerate(indexed, start=1):
        if rank <= cutoff:
            out[i] = True
    return out


def join_maps(*row_lists: list[dict], key: str = "observation_id") -> list[dict]:
    maps = [{r[key]: r for r in rows} for rows in row_lists]
    ids = []
    seen = set()
    for rows in row_lists:
        for r in rows:
            i = r[key]
            if i not in seen:
                seen.add(i)
                ids.append(i)
    out = []
    for i in ids:
        merged = {}
        for m in maps:
            if i in m:
                merged.update(m[i])
        out.append(merged)
    return out


def is_primary(row: dict) -> bool:
    return row.get("alignment_confidence") in PRIMARY_ALIGN


def split_rows(rows: list[dict], split: str, primary_only: bool = True) -> list[dict]:
    out = []
    for r in rows:
        if r.get("dataset_split") != split:
            continue
        if primary_only and not is_primary(r):
            continue
        out.append(r)
    return out
