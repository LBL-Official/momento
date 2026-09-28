"""Deterministic UTF-8 CSV I/O and file hashing."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

CSV_NA = ""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_json(obj: Any) -> str:
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return sha256_bytes(payload)


def write_csv(path: Path, df: pd.DataFrame, columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    if columns is not None:
        for c in columns:
            if c not in out.columns:
                out[c] = ""
        out = out[columns]
    out.to_csv(path, index=False, encoding="utf-8", lineterminator="\n")


def read_csv(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(path)
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def read_csv_optional(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame(columns=columns or [])
    return read_csv(path)


def partition_months(date_from: str | None, date_to: str | None) -> set[str] | None:
    """YYYY-MM keys covering a query window, plus the adjacent months.

    Adjacent months cover UTC spill and extra-inning games that cross midnight.
    None means read every partition (no date window).
    """
    if not date_from and not date_to:
        return None

    def _day(raw: str) -> date:
        return date.fromisoformat(str(raw)[:10])

    lo = _day(date_from) if date_from else _day(str(date_to))
    hi = _day(date_to) if date_to else _day(str(date_from))
    if hi < lo:
        lo, hi = hi, lo
    lo = date(lo.year, lo.month, 1)
    if lo.month == 1:
        lo = date(lo.year - 1, 12, 1)
    else:
        lo = date(lo.year, lo.month - 1, 1)
    if hi.month == 12:
        hi = date(hi.year + 1, 1, 1)
    else:
        hi = date(hi.year, hi.month + 1, 1)
    out: set[str] = set()
    cur = lo
    while cur <= hi:
        out.add(cur.strftime("%Y-%m"))
        cur = date(cur.year + 1, 1, 1) if cur.month == 12 else date(cur.year, cur.month + 1, 1)
    return out


def concat_partition_csvs(
    directory: Path,
    *,
    months: set[str] | None = None,
) -> pd.DataFrame:
    if not directory.is_dir():
        return pd.DataFrame()
    files = sorted(directory.glob("*.csv"))
    if months is not None:
        keep: list[Path] = []
        for path in files:
            stem = path.stem
            if "=" in stem and stem.split("=", 1)[-1] not in months:
                continue
            keep.append(path)
        files = keep
    if not files:
        return pd.DataFrame()
    frames = [read_csv(p) for p in files]
    return pd.concat(frames, ignore_index=True)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
