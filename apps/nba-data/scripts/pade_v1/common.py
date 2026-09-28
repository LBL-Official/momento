"""PADE V1 shared constants and I/O.

Research only. Does not change live trading. Does not edit FIRST-80 V1/V2.
"""

from __future__ import annotations

import importlib.util
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

PROGRAM = "MOMENTO_POSSESSION_ADJUSTED_DETERIORATION_ENGINE_V1"
SCHEMA_VERSION = "1.0.0"
LIVE_EXECUTION_CHANGED = False

REPO = Path("/Users/user/Desktop/Momento")
NBA_SCRIPTS = REPO / "apps" / "nba-data" / "scripts"
NCAAB_SCRIPTS = REPO / "apps" / "ncaab-data" / "scripts"
WAREHOUSE = (
    REPO / "Backtesting Suite" / "Data" / "NBA" / "2025-2026" / "warehouse"
)
NORM = WAREHOUSE / "normalized" / "nba"
RAW = WAREHOUSE / "raw" / "nba_stats"
PBP_LIVE = RAW / "pbp_live"
PBP_V3 = RAW / "pbp_v3"
BOX_DIR = RAW / "boxscore_summary"
CROSSWALK_PATH = NORM / "pbp" / "game_crosswalk.json"
CANDLES_DIR = NORM / "candles_1m"
OUT = WAREHOUSE / "derived" / "nba" / "possession_adjusted_deterioration_engine_v1"
DASH_PUBLIC = REPO / "frontend" / "pade-v1" / "public" / "data"
DOCS_AUDIT = REPO / "docs" / "research" / "PADE_V1_REPOSITORY_AUDIT.md"
DOCS_REPORT = (
    REPO / "docs" / "research" / "MOMENTO_POSSESSION_ADJUSTED_DETERIORATION_ENGINE_V1.md"
)

GATES_F80 = {"n": 1230, "survivors": 910, "stops": 320, "leaks": 0, "surv_pct": 73.9837}
SPLIT_TRAIN_END = "2025-12-31"
SPLIT_VAL_END = "2026-03-15"
ENTRY_CENTS = 80.0
REG_PERIOD_S = 720.0
OT_PERIOD_S = 300.0
REG_PERIODS = 4
REG_GAME_S = 2880.0

THRESHOLDS = (75, 70, 65, 60, 55, 50, 45, 40, 35, 30, 25, 20, 15, 10, 5)
JUMP_THRESHOLDS = (40, 35, 30, 25, 20, 15, 10, 5)
HORIZONS = (1, 3, 5, 10)
VEL_KS = (1, 2, 3, 5, 10)
MIN_TIMEACTUAL_RATE = 0.95
CLOCK_RE = re.compile(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?$", re.I)


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_v1():
    """Import FIRST-80 V1 as a read-only library. Do not edit that file."""
    if str(NBA_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(NBA_SCRIPTS))
    return _load(
        "first80_exit_fee_v1_for_pade",
        NCAAB_SCRIPTS / "first80_realistic_exit_fee_audit_v1.py",
    )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_clock_seconds(clock) -> float | None:
    if clock is None:
        return None
    s = str(clock).strip()
    if not s:
        return None
    m = CLOCK_RE.match(s)
    if not m:
        return None
    hours = float(m.group(1) or 0)
    minutes = float(m.group(2) or 0)
    secs = float(m.group(3) or 0)
    return hours * 3600.0 + minutes * 60.0 + secs


def parse_timeactual(raw) -> float | None:
    """Return Unix seconds (float, UTC). Observed live-feed wall clock."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        if "." in s:
            head, frac = s.split(".", 1)
            tz = ""
            if "+" in frac:
                frac, tzrest = frac.split("+", 1)
                tz = "+" + tzrest
            s = f"{head}.{frac[:6]:<06}{tz}"
            try:
                dt = datetime.fromisoformat(s)
            except ValueError:
                return None
        else:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def iso_utc(ts: float | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()


def period_length_s(period, period_type: str | None) -> float:
    p = int(period or 0)
    pt = (period_type or "").upper()
    if p >= 5 or "OVER" in pt:
        return OT_PERIOD_S
    return REG_PERIOD_S


def elapsed_game_seconds(period, remaining_s, period_type: str | None) -> float | None:
    if period is None or remaining_s is None:
        return None
    p = int(period)
    rem = float(remaining_s)
    if p <= 0:
        return None
    if p <= REG_PERIODS:
        return (p - 1) * REG_PERIOD_S + max(0.0, REG_PERIOD_S - rem)
    return REG_GAME_S + (p - 5) * OT_PERIOD_S + max(0.0, OT_PERIOD_S - rem)


def game_seconds_remaining_known(period, remaining_s, period_type: str | None) -> float | None:
    """Regulation remaining, or current OT remaining. Future OT is unknown."""
    if period is None or remaining_s is None:
        return None
    p = int(period)
    rem = float(remaining_s)
    if p <= REG_PERIODS:
        return rem + (REG_PERIODS - p) * REG_PERIOD_S
    return rem


def e4_to_cents(v) -> float | None:
    if v is None:
        return None
    return float(v) / 100.0


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=_json_default) + "\n")


def _json_default(o):
    if isinstance(o, Path):
        return str(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        if math.isnan(float(o)):
            return None
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


def write_parquet(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        pq.write_table(pa.table({"_empty": pa.array([], type=pa.int8())}), path)
        return
    clean = []
    for r in rows:
        c = {}
        for k, v in r.items():
            if isinstance(v, (dict, list, tuple)):
                c[k] = json.dumps(v, default=str)
            elif isinstance(v, (np.bool_,)):
                c[k] = bool(v)
            elif isinstance(v, (np.integer,)):
                c[k] = int(v)
            elif isinstance(v, (np.floating,)):
                fv = float(v)
                c[k] = None if math.isnan(fv) else fv
            else:
                c[k] = v
        clean.append(c)
    keys = {k for r in clean for k in r}
    for k in keys:
        types = {type(r.get(k)) for r in clean if r.get(k) is not None}
        if len(types) > 1:
            for r in clean:
                if r.get(k) is not None:
                    r[k] = str(r[k])
    pq.write_table(pa.Table.from_pylist(clean), path)


def read_parquet_rows(path: Path) -> list[dict]:
    table = pq.read_table(path)
    names = table.column_names
    if names == ["_empty"]:
        return []
    cols = {c: table.column(c) for c in names}
    n = table.num_rows
    return [{c: cols[c][i].as_py() for c in names} for i in range(n)]


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text())


def load_crosswalk() -> dict[str, dict]:
    rows = load_json(CROSSWALK_PATH, [])
    return {r["event_id"]: r for r in rows if isinstance(r, dict)}


def team_code_from_ticker(ticker: str | None) -> str | None:
    if not ticker or "-" not in ticker:
        return None
    code = ticker.rsplit("-", 1)[-1].strip().upper()
    return code or None
