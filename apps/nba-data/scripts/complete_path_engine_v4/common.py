"""Complete Path Engine V4 — shared constants. Research only."""

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
OUT = ROOT / "derived" / "nba" / "momento_complete_path_engine_v4"
SPEC_DIR = Path("/Users/user/Desktop/Momento/docs/research/nba/complete-path-engine-v4")

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
GRID_N = 32
DTW_CAP = 96
N_PERM = 300
MIN_PATH_POINTS = 3
REJECT_Q = (0.30, 1.0 / 3.0, 0.40)


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


def metrics_block(y, p):
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    k = int(y.sum())
    n = int(len(y))
    return {
        "n": n,
        "k": k,
        "q": float(y.mean()) if n else None,
        "brier": brier(y, p) if n else None,
        "log_loss": log_loss(y, p) if n else None,
        "auc": roc_auc(y, p) if n else None,
        "ece": ece(y, p) if n else None,
        "mean_p": float(p.mean()) if n else None,
        "ev": ev_from_q(float(y.mean()) if n else None),
    }


def add_intercept(X):
    return np.column_stack([np.ones(len(X)), X])


def impute_scale(X, fit=False, medians=None, means=None, stds=None):
    out = np.asarray(X, dtype=float).copy()
    n, p = out.shape
    if fit:
        medians = np.zeros(p)
        for j in range(p):
            vals = out[np.isfinite(out[:, j]), j]
            medians[j] = float(np.median(vals)) if len(vals) else 0.0
    for j in range(p):
        miss = ~np.isfinite(out[:, j])
        out[miss, j] = medians[j]
    if fit:
        means = out.mean(axis=0)
        stds = out.std(axis=0, ddof=0)
        stds = np.where(stds < 1e-12, 1.0, stds)
    return (out - means) / stds, medians, means, stds


def fit_l2(X, y, l2=L2_LAMBDA, max_iter=80):
    w = np.zeros(X.shape[1])
    pen = np.ones(X.shape[1]) * l2
    pen[0] = 0.0
    y = np.asarray(y, dtype=float)
    for _ in range(max_iter):
        p_hat = sigmoid(X @ w)
        wdiag = np.clip(p_hat * (1.0 - p_hat), 1e-6, None)
        H = X.T @ (wdiag[:, None] * X) + np.diag(pen)
        g = X.T @ (p_hat - y) + pen * w
        try:
            delta = np.linalg.solve(H, g)
        except np.linalg.LinAlgError:
            delta = np.linalg.lstsq(H, g, rcond=None)[0]
        w = w - delta
        if np.max(np.abs(delta)) < 1e-8:
            break
    return w


def resample_series(ts, vals, n=GRID_N):
    ts = np.asarray(ts, dtype=float)
    vals = np.asarray(vals, dtype=float)
    if len(ts) < 2 or ts[-1] <= ts[0]:
        return np.full(n, float(vals[-1]) if len(vals) else np.nan)
    u = np.linspace(0.0, 1.0, n)
    tq = ts[0] + u * (ts[-1] - ts[0])
    return np.interp(tq, ts, vals)


def downsample(vals, cap=DTW_CAP):
    vals = np.asarray(vals, dtype=float)
    if len(vals) <= cap:
        return vals
    idx = np.linspace(0, len(vals) - 1, cap).round().astype(int)
    return vals[idx]


def dtw_abs(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    n, m = len(a), len(b)
    D = np.full((n + 1, m + 1), np.inf)
    D[0, 0] = 0.0
    for i in range(1, n + 1):
        ai = a[i - 1]
        for j in range(1, m + 1):
            cost = abs(ai - b[j - 1])
            D[i, j] = cost + min(D[i - 1, j], D[i, j - 1], D[i - 1, j - 1])
    return float(D[n, m])
