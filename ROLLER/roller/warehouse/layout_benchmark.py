"""Phase 8 NBA layout benchmarks. Numbers are measured, not invented.

Observation workload = TRADABLE_YES_BID 1-minute candles only.
Orderbook is not a benchmark dataset.
Not a Confirm & Run path. Not ResearchContext.
"""

from __future__ import annotations

import resource
import sys
import time
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import pyarrow.parquet as pq

from roller.config import RollerConfig
from roller.io_csv import write_json
from roller.warehouse.layout import (
    DEFAULT_COMPRESSION,
    DEFAULT_ROW_GROUP,
    OBS_FINGERPRINT_COLS,
    OBS_SORT,
    PBP_FINGERPRINT_COLS,
    SETTLE_FINGERPRINT_COLS,
    concat_month_parquets,
    fingerprint_frame,
    inspect_month_dir,
    inspect_parquet_file,
    observations_dir,
    pbp_dir,
    write_sorted_parquet,
)
from roller.warehouse.layout_v0 import (
    crosswalk_path,
    markets_parquet_path,
    observations_dir as v0_obs,
    pbp_dir as v0_pbp,
    settlements_parquet_path,
    warehouse_v0_root,
)
from roller.warehouse.partitioning import list_month_parquets, month_key

BENCH_GAME = "NBA_20251010_BOS_TOR"
BENCH_MARKET = "KXNBAGAME-25OCT10BOSTOR-BOS"
BENCH_DATE_FROM = "2025-10-10T00:00:00Z"
BENCH_DATE_TO = "2025-10-31T23:59:59Z"
SAMPLE_MONTH = "2025-10"


def peak_rss_mb() -> float:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return rss / (1024 * 1024)
    return rss / 1024


def _timed(fn: Callable[[], Any]) -> tuple[Any, dict[str, float]]:
    start = time.perf_counter()
    rss0 = peak_rss_mb()
    value = fn()
    elapsed = time.perf_counter() - start
    return value, {"seconds": round(elapsed, 6), "peak_rss_mb": round(max(rss0, peak_rss_mb()), 3)}


def inspect_baseline(cfg: RollerConfig) -> dict[str, Any]:
    root = warehouse_v0_root(cfg)
    return {
        "root": str(root),
        "markets": inspect_parquet_file(markets_parquet_path(cfg)),
        "settlements": inspect_parquet_file(settlements_parquet_path(cfg)),
        "links": inspect_parquet_file(crosswalk_path(cfg)),
        "observations": inspect_month_dir(v0_obs(cfg)),
        "pbp": inspect_month_dir(v0_pbp(cfg)),
        "orderbook_parquet_files": 0,
    }


def query_observations_game(directory: Path, game_id: str) -> tuple[int, int]:
    files = list_month_parquets(directory)
    rows = 0
    touched = 0
    for path in files:
        touched += 1
        frame = pd.read_parquet(path, columns=["internal_game_id"])
        rows += int((frame["internal_game_id"].astype(str) == game_id).sum())
    return rows, touched


def query_observations_market(directory: Path, ticker: str) -> tuple[int, int]:
    files = list_month_parquets(directory)
    rows = 0
    touched = 0
    for path in files:
        touched += 1
        frame = pd.read_parquet(path, columns=["ticker"])
        rows += int((frame["ticker"].astype(str) == ticker).sum())
    return rows, touched


def query_observations_range(directory: Path, start: str, end: str) -> tuple[int, int]:
    files = list_month_parquets(directory)
    rows = 0
    touched = 0
    for path in files:
        month = month_key(path)
        if month < start[:7] or month > end[:7]:
            continue
        touched += 1
        frame = pd.read_parquet(path, columns=["available_at"])
        ts = frame["available_at"].astype(str)
        rows += int(((ts >= start) & (ts <= end)).sum())
    return rows, touched


def query_observations_season(directory: Path) -> tuple[int, int]:
    files = list_month_parquets(directory)
    rows = 0
    for path in files:
        rows += int(pq.ParquetFile(path).metadata.num_rows)
    return rows, len(files)


def query_pbp_game(directory: Path, game_id: str) -> tuple[int, int]:
    files = list_month_parquets(directory)
    rows = 0
    touched = 0
    for path in files:
        touched += 1
        frame = pd.read_parquet(path, columns=["internal_game_id"])
        rows += int((frame["internal_game_id"].astype(str) == game_id).sum())
    return rows, touched


def workload(directory_obs: Path, directory_pbp: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    (rows, files), meta = _timed(lambda: query_observations_game(directory_obs, BENCH_GAME))
    out["A_single_game_candles"] = {"rows": rows, "files_touched": files, **meta}
    (rows, files), meta = _timed(lambda: query_observations_market(directory_obs, BENCH_MARKET))
    out["B_single_market_candles"] = {"rows": rows, "files_touched": files, **meta}
    (rows, files), meta = _timed(lambda: query_observations_range(directory_obs, BENCH_DATE_FROM, BENCH_DATE_TO))
    out["C_date_range_candles"] = {"rows": rows, "files_touched": files, **meta}
    (rows, files), meta = _timed(lambda: query_observations_season(directory_obs))
    out["D_season_candles"] = {"rows": rows, "files_touched": files, **meta}
    (rows, files), meta = _timed(lambda: query_pbp_game(directory_pbp, BENCH_GAME))
    out["E_pbp_game"] = {"rows": rows, "files_touched": files, **meta}

    def _joined() -> dict[str, int]:
        obs_rows, obs_files = query_observations_game(directory_obs, BENCH_GAME)
        pbp_rows, pbp_files = query_pbp_game(directory_pbp, BENCH_GAME)
        return {
            "obs_rows": obs_rows,
            "pbp_rows": pbp_rows,
            "files_touched": obs_files + pbp_files,
        }

    joined, meta = _timed(_joined)
    out["F_game_context_storage_join"] = {**joined, **meta}
    return out


def _write_candidate(frame: pd.DataFrame, dest: Path, kind: str, compression: str, row_group: int) -> dict[str, Any]:
    dest.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    if kind == "A":
        write_sorted_parquet(frame, dest / "observations.parquet", sort_cols=OBS_SORT, compression=compression, row_group_size=row_group)
        files = [dest / "observations.parquet"]
    elif kind == "B":
        work = frame.copy()
        work["_day"] = work["available_at"].astype(str).str.slice(0, 10)
        files = []
        for day, part in work.groupby("_day", sort=True):
            path = dest / f"date={day}.parquet"
            write_sorted_parquet(part.drop(columns=["_day"]), path, sort_cols=OBS_SORT, compression=compression, row_group_size=row_group)
            files.append(path)
    elif kind == "C":
        work = frame.copy()
        work["_month"] = work["available_at"].astype(str).str.slice(0, 7)
        files = []
        for month, part in work.groupby("_month", sort=True):
            path = dest / f"month={month}.parquet"
            write_sorted_parquet(part.drop(columns=["_month"]), path, sort_cols=OBS_SORT, compression=compression, row_group_size=row_group)
            files.append(path)
    elif kind == "D":
        files = []
        for gid, part in frame.groupby("internal_game_id", sort=True):
            safe = str(gid).replace("/", "_")
            path = dest / f"game={safe}.parquet"
            write_sorted_parquet(part, path, sort_cols=OBS_SORT, compression=compression, row_group_size=row_group)
            files.append(path)
    else:
        raise ValueError(kind)
    elapsed = time.perf_counter() - t0
    bytes_total = sum(p.stat().st_size for p in files)
    t1 = time.perf_counter()
    if kind == "A":
        read_rows = int(len(pd.read_parquet(files[0], columns=["available_at"])))
        files_touched = 1
    elif kind == "D":
        hit = dest / f"game={BENCH_GAME}.parquet"
        read_rows = int(len(pd.read_parquet(hit, columns=["available_at"]))) if hit.is_file() else 0
        files_touched = 1
    else:
        read_rows = 0
        files_touched = 0
        for path in files:
            part = pd.read_parquet(path, columns=["internal_game_id"])
            files_touched += 1
            read_rows += int((part["internal_game_id"].astype(str) == BENCH_GAME).sum())
    read_s = time.perf_counter() - t1
    return {
        "candidate": kind,
        "files": len(files),
        "bytes": bytes_total,
        "write_seconds": round(elapsed, 6),
        "single_game_read_seconds": round(read_s, 6),
        "single_game_rows": read_rows,
        "single_game_files": files_touched,
    }


def compression_bakeoff(frame: pd.DataFrame, dest: Path, row_group: int) -> list[dict[str, Any]]:
    dest.mkdir(parents=True, exist_ok=True)
    results = []
    for codec in ("none", "snappy", "zstd", "gzip"):
        path = dest / f"obs.{codec}.parquet"
        t0 = time.perf_counter()
        write_sorted_parquet(frame, path, sort_cols=OBS_SORT, compression=codec, row_group_size=row_group)
        write_s = time.perf_counter() - t0
        t1 = time.perf_counter()
        n = int(len(pd.read_parquet(path, columns=["available_at"])))
        read_s = time.perf_counter() - t1
        results.append(
            {
                "compression": codec,
                "bytes": int(path.stat().st_size),
                "rows": n,
                "write_seconds": round(write_s, 6),
                "read_seconds": round(read_s, 6),
            }
        )
    return results


def row_group_bakeoff(frame: pd.DataFrame, dest: Path, compression: str) -> list[dict[str, Any]]:
    dest.mkdir(parents=True, exist_ok=True)
    results = []
    for rg in (0, 65536, 262144, 524288):
        path = dest / f"obs.rg{rg}.parquet"
        size = None if rg == 0 else rg
        t0 = time.perf_counter()
        if size is None:
            work = frame.sort_values(OBS_SORT, kind="mergesort").reset_index(drop=True)
            work.to_parquet(path, index=False, compression=compression)
        else:
            write_sorted_parquet(frame, path, sort_cols=OBS_SORT, compression=compression, row_group_size=size)
        write_s = time.perf_counter() - t0
        info = inspect_parquet_file(path)
        t1 = time.perf_counter()
        _ = pd.read_parquet(path, columns=["internal_game_id", "available_at"])
        read_s = time.perf_counter() - t1
        results.append(
            {
                "row_group_size": rg,
                "bytes": info["bytes"],
                "row_groups": info["row_groups"],
                "avg_row_group_rows": info["avg_row_group_rows"],
                "write_seconds": round(write_s, 6),
                "read_seconds": round(read_s, 6),
            }
        )
    return results


def fingerprints_v0(cfg: RollerConfig) -> dict[str, Any]:
    obs = concat_month_parquets(v0_obs(cfg), OBS_FINGERPRINT_COLS)
    pbp = concat_month_parquets(v0_pbp(cfg), PBP_FINGERPRINT_COLS)
    settle = pd.read_parquet(settlements_parquet_path(cfg), columns=SETTLE_FINGERPRINT_COLS)
    obs_fp, obs_n = fingerprint_frame(obs, OBS_FINGERPRINT_COLS)
    pbp_fp, pbp_n = fingerprint_frame(pbp, PBP_FINGERPRINT_COLS)
    set_fp, set_n = fingerprint_frame(settle, SETTLE_FINGERPRINT_COLS)
    return {
        "observations": {"sha256": obs_fp, "rows": obs_n},
        "pbp": {"sha256": pbp_fp, "rows": pbp_n},
        "settlements": {"sha256": set_fp, "rows": set_n},
    }


def fingerprints_selected(cfg: RollerConfig) -> dict[str, Any]:
    obs = concat_month_parquets(observations_dir(cfg), OBS_FINGERPRINT_COLS)
    pbp = concat_month_parquets(pbp_dir(cfg), PBP_FINGERPRINT_COLS)
    from roller.warehouse.layout import settlements_path

    settle = pd.read_parquet(settlements_path(cfg), columns=SETTLE_FINGERPRINT_COLS)
    obs_fp, obs_n = fingerprint_frame(obs, OBS_FINGERPRINT_COLS)
    pbp_fp, pbp_n = fingerprint_frame(pbp, PBP_FINGERPRINT_COLS)
    set_fp, set_n = fingerprint_frame(settle, SETTLE_FINGERPRINT_COLS)
    return {
        "observations": {"sha256": obs_fp, "rows": obs_n},
        "pbp": {"sha256": pbp_fp, "rows": pbp_n},
        "settlements": {"sha256": set_fp, "rows": set_n},
    }


def run_sample_candidates(cfg: RollerConfig, bench_root: Path) -> dict[str, Any]:
    src = v0_obs(cfg) / f"month={SAMPLE_MONTH}.parquet"
    frame = pd.read_parquet(src)
    games = int(frame["internal_game_id"].nunique())
    days = int(frame["available_at"].astype(str).str.slice(0, 10).nunique())
    out: dict[str, Any] = {
        "sample_month": SAMPLE_MONTH,
        "sample_rows": int(len(frame)),
        "sample_games": games,
        "sample_days": days,
        "candidates": {},
    }
    for kind in ("A", "B", "C", "D"):
        dest = bench_root / f"candidate_{kind}"
        out["candidates"][kind] = _write_candidate(frame, dest, kind, DEFAULT_COMPRESSION, DEFAULT_ROW_GROUP)
    out["compression"] = compression_bakeoff(frame, bench_root / "compression", DEFAULT_ROW_GROUP)
    out["row_groups"] = row_group_bakeoff(frame, bench_root / "row_groups", DEFAULT_COMPRESSION)
    return out


def run_benchmarks(cfg: RollerConfig, *, write_report: bool = True) -> dict[str, Any]:
    bench_root = warehouse_v0_root(cfg).parent / "warehouse_layout_bench"
    if bench_root.exists():
        import shutil

        shutil.rmtree(bench_root)
    bench_root.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "observation_basis": "TRADABLE_YES_BID",
        "observation_resolution": "1_MINUTE_CANDLE",
        "orderbook_benchmarked": False,
        "baseline": inspect_baseline(cfg),
        "baseline_workload": workload(v0_obs(cfg), v0_pbp(cfg)),
        "sample": run_sample_candidates(cfg, bench_root),
        "selected_defaults": {
            "partition": "C_month",
            "sort": OBS_SORT,
            "compression": DEFAULT_COMPRESSION,
            "row_group_size": DEFAULT_ROW_GROUP,
        },
    }
    if write_report:
        write_json(bench_root / "benchmark.json", report)
    return report
