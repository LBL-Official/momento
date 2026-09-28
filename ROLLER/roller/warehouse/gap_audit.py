"""Machine-readable coverage. Missing ≠ unavailable. Never fill rows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from roller.config import RollerConfig
from roller.research_query.indexes.builder import index_root
from roller.research_query.indexes.manifest import MANIFEST_NAME, read_manifest
from roller.research_query.models import BASIS_LAST_TRADE, BASIS_TRADABLE
from roller.warehouse.catalog import UNAVAILABLE_SPORTS, catalog
from roller.warehouse.freshness import classify_dataset, evaluate

STATUSES = (
    "COMPLETE",
    "PARTIAL",
    "MISSING",
    "SOURCE_UNAVAILABLE",
    "NOT_APPLICABLE",
    "INVALID",
    "STALE",
)


def _file_rows(path: Path) -> int | None:
    if not path.is_file():
        return None
    # Header + newline count via buffer; avoid per-line Python overhead on 6M-row months.
    n = 0
    with path.open("rb") as fh:
        buf = fh.read(1 << 20)
        if not buf:
            return 0
        n += buf.count(b"\n")
        leftover = buf
        while True:
            chunk = fh.read(1 << 20)
            if not chunk:
                break
            n += chunk.count(b"\n")
            leftover = chunk
        if leftover and not leftover.endswith(b"\n"):
            n += 1
    return max(n - 1, 0)


def _dir_rows(path: Path) -> int:
    total = 0
    if not path.is_dir():
        return 0
    for child in path.glob("month=*.csv"):
        rows = _file_rows(child) or 0
        total += rows
    return total


def _dataset_status(ref) -> str:
    if ref.kind == "missing":
        if ref.dataset in {"kalshi_last_trade", "kalshi_orderbook_snapshots", "kalshi_trades"}:
            return "NOT_APPLICABLE" if ref.sport in {"NBA", "NCAAB", "WNBA"} else "MISSING"
        if ref.dataset == "kalshi_markets" and ref.sport in {"NBA", "NCAAB", "WNBA"}:
            return "MISSING"
        if "2026-2027" in ref.season or "2026_2027" in str(ref.path):
            return "NOT_APPLICABLE"
        return "MISSING"
    if ref.kind == "file":
        rows = _file_rows(ref.path) or 0
        if rows <= 0:
            return "MISSING"
        return "COMPLETE"
    if not ref.months:
        return "MISSING" if ref.dataset.startswith("kalshi") or ref.dataset == "pbp" else "NOT_APPLICABLE"
    return "PARTIAL" if ref.dataset in {"kalshi_candles", "kalshi_last_trade", "pbp"} else "COMPLETE"


def _index_leaf(cfg: RollerConfig, sport: str, season: str, basis: str) -> dict[str, Any] | None:
    root = index_root(cfg, sport, season, league=sport, basis=basis)
    man = root / MANIFEST_NAME
    if not man.is_file():
        return None
    m = read_manifest(man)
    return {
        "path": str(root),
        "tickers": m.ticker_count,
        "games": m.game_count,
        "bar_rows": m.bar_rows,
        "settlement_rows": m.settlement_rows,
        "dataset_version": m.dataset_version,
    }


def run_audit(cfg: RollerConfig | None = None, *, count_rows: bool = False) -> dict[str, Any]:
    cfg = cfg or RollerConfig()
    sports: list[dict[str, Any]] = []
    for name in UNAVAILABLE_SPORTS:
        sports.append(
            {
                "sport": name,
                "status": "SOURCE_UNAVAILABLE",
                "seasons": [],
                "note": "No warehouse tree on disk. Not MISSING.",
            }
        )
    for season in catalog(cfg):
        root_exists = season.root.is_dir()
        datasets: dict[str, Any] = {}
        for name, ref in season.datasets.items():
            rows = None
            if count_rows:
                if ref.kind == "file":
                    rows = _file_rows(ref.path) or 0
                elif ref.kind == "directory":
                    rows = _dir_rows(ref.path)
            status = "NOT_APPLICABLE" if not root_exists else _dataset_status(ref)
            fresh = evaluate(
                classification=classify_dataset(name, sport=season.sport),
                warehouse_latest=ref.months[-1] if ref.months else None,
            )
            datasets[name] = {
                "status": status,
                "kind": ref.kind,
                "path": str(ref.path),
                "months": list(ref.months),
                "parquet_months": list(ref.parquet_months),
                "rows": rows,
                "freshness": {
                    "classification": fresh.classification,
                    "status": fresh.status,
                    "warehouse_latest_timestamp": fresh.warehouse_latest_timestamp,
                },
            }
        indexes = {
            "tradable": _index_leaf(cfg, season.sport, season.season, BASIS_TRADABLE),
            "last_trade": _index_leaf(cfg, season.sport, season.season, BASIS_LAST_TRADE),
        }
        sports.append(
            {
                "sport": season.sport,
                "league": season.league,
                "season": season.season,
                "root": str(season.root),
                "root_exists": root_exists,
                "status": "COMPLETE" if root_exists else "NOT_APPLICABLE",
                "datasets": datasets,
                "indexes": indexes,
            }
        )
    return {
        "statuses": list(STATUSES),
        "sports": sports,
        "invariants": [
            "LAST_TRADE_PRINT != TRADABLE_YES_BID",
            "CANDLE_PATH != FILL",
            "MISSING != ZERO",
            "UNAVAILABLE != MISSING",
            "NO_SETTLEMENT != NO",
        ],
    }


def write_reports(dest_md: Path, dest_json: Path, cfg: RollerConfig | None = None) -> dict[str, Any]:
    audit = run_audit(cfg, count_rows=True)
    dest_json.parent.mkdir(parents=True, exist_ok=True)
    dest_json.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Data coverage",
        "",
        "Generated by `python -m roller.warehouse gap_audit`. Facts only. NHL is SOURCE_UNAVAILABLE.",
        "",
        "| Sport | Season | Root | Candles | Last-trade | PBP | Kalshi markets | Orderbook | Index tradable | Index last-trade |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in audit["sports"]:
        if row.get("status") == "SOURCE_UNAVAILABLE":
            lines.append(
                f"| {row['sport']} | — | UNAVAILABLE | — | — | — | — | — | — | — |"
            )
            continue
        ds = row.get("datasets") or {}
        idx = row.get("indexes") or {}

        def cell(name: str) -> str:
            item = ds.get(name) or {}
            st = item.get("status", "—")
            rows = item.get("rows")
            months = item.get("months") or []
            extra = f" {rows}r/{len(months)}m" if rows is not None and item.get("kind") != "missing" else ""
            return f"{st}{extra}"

        tr = idx.get("tradable")
        lt = idx.get("last_trade")
        lines.append(
            "| {sport} | {season} | {root} | {c} | {lt} | {p} | {m} | {ob} | {itr} | {ilt} |".format(
                sport=row["sport"],
                season=row.get("season", ""),
                root="yes" if row.get("root_exists") else "no",
                c=cell("kalshi_candles"),
                lt=cell("kalshi_last_trade"),
                p=cell("pbp"),
                m=cell("kalshi_markets"),
                ob=cell("kalshi_orderbook_snapshots"),
                itr=f"{tr['bar_rows']} bars" if tr else "absent",
                ilt=f"{lt['bar_rows']} bars" if lt else "absent",
            )
        )
    dest_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return audit


if __name__ == "__main__":
    import sys

    from roller.config import RollerConfig

    cfg = RollerConfig()
    root = Path(__file__).resolve().parents[3]
    dest_md = root / "research" / "parquet_migration" / "DATA_COVERAGE.md"
    dest_json = cfg.root / "reports" / "warehouse" / "gap_audit.json"
    write_reports(dest_md, dest_json, cfg)
    sys.exit(0)
