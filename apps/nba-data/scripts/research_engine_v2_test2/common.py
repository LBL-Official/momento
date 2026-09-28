"""Research Engine V2 Test 2 — shared constants.

Research only. Does not change live FIRST01, Path Engine V1, or GPE V2 artifacts.
"""

from __future__ import annotations

import importlib.util
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
GPE_DIR = NBA_SCRIPTS / "game_path_engine_v2"

# Load GPE V2 pbp without shadowing this module as `common`.
_saved_common = sys.modules.get("common")
_gpe_common_spec = importlib.util.spec_from_file_location(
    "game_path_engine_v2_common", GPE_DIR / "common.py"
)
assert _gpe_common_spec and _gpe_common_spec.loader
_gpe_common = importlib.util.module_from_spec(_gpe_common_spec)
sys.modules["common"] = _gpe_common
_gpe_common_spec.loader.exec_module(_gpe_common)
_pbp_spec = importlib.util.spec_from_file_location("gpe_pbp", GPE_DIR / "pbp.py")
assert _pbp_spec and _pbp_spec.loader
gpe_pbp = importlib.util.module_from_spec(_pbp_spec)
sys.modules["gpe_pbp"] = gpe_pbp
_pbp_spec.loader.exec_module(gpe_pbp)
if _saved_common is not None:
    sys.modules["common"] = _saved_common

if str(NBA_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(NBA_SCRIPTS))
import nba_80_40_execution_audit as audit  # noqa: E402

ROOT = audit.ROOT
NORM = audit.NORM
RAW = ROOT / "raw" / "nba_stats"
PBP_DIR = RAW / "pbp_v3"
BOX_DIR = RAW / "boxscore_summary"
CROSSWALK_PATH = NORM / "pbp" / "game_crosswalk.json"
OUT = ROOT / "derived" / "nba" / "momento_research_engine_v2_test2"
SPEC_DIR = Path("/Users/user/Desktop/Momento/docs/research/nba/research-engine-v2-test2")
DASH_PUBLIC = Path("/Users/user/Desktop/Momento/frontend/nba-research-engine-v2/public/data")

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
PRIMARY_ALIGN = {"HIGH", "MEDIUM"}
POS_WINDOWS = (1, 3, 5, 10, 20, 30)
MIN_ACCEPTANCE = 0.50
MIN_BUCKET_N = 30
FILTER_THRESHOLDS = (0.20, 0.25, 0.30, 0.3333)
BRIER_IMPROVE = 0.95
ECE_TOLERANCE = 0.005
BUCKET_GAP_PP = 8.0
BH_Q = 0.10
L2_LAMBDA = 1.0


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
    if isinstance(o, (np.bool_,)):
        return bool(o)
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
    n = table.num_rows
    cols = {c: table.column(c) for c in names}
    return [{c: cols[c][i].as_py() for c in names} for i in range(n)]


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
                    "bid_c": audit._opt_int(get["yes_bid_close_e4"][i].as_py()),
                    "bid_h": audit._opt_int(get["yes_bid_high_e4"][i].as_py()),
                    "bid_l": audit._opt_int(get["yes_bid_low_e4"][i].as_py()),
                    "ask_c": audit._opt_int(get["yes_ask_close_e4"][i].as_py()),
                    "vol": audit._opt_int(get["volume_hundredths"][i].as_py()),
                }
            )
    for rows in quotes.values():
        rows.sort(key=lambda r: r["ts"])
    return quotes, meta


def mean(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    return float(sum(xs) / len(xs))


def stdev(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return None
    return float(np.std(xs, ddof=1))


def sigmoid(z):
    z = np.clip(z, -30.0, 30.0)
    return 1.0 / (1.0 + np.exp(-z))
