"""NBA orderbook data-contract boundary. Phase 7.

This ROLLER version has exactly one historical market-observation basis:
TRADABLE_YES_BID = 1-minute Kalshi candles.

There are no historical NBA tick or L2/orderbook observations.
This module declares that absence. It does not build an orderbook warehouse.

Not used by execute / compile_draft / load_dataset.
Never connected to Phase 4 candle projection.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from roller.config import RollerConfig
from roller.ingest.games import load_sport_games
from roller.io_csv import sha256_file, write_json
from roller.paths import canonical_dir, raw_dir
from roller.timeutil import now_utc_iso
from roller.warehouse.layout_v0 import (
    orderbook_capability_path,
    orderbook_dir,
    season_path_key,
    warehouse_v0_readme_path,
)

PHASE7_SPORT = "NBA"
AVAILABILITY_UNAVAILABLE = "SOURCE_UNAVAILABLE"
MARKET_DATA_BASIS = "ONE_MINUTE_CANDLE"

CANDLE_INSUFFICIENT_COLUMNS = (
    "yes_bid_open",
    "yes_bid_high",
    "yes_bid_low",
    "yes_bid_close",
    "volume",
)

HYPOTHETICAL_BOOK_FIELDS = (
    "best_yes_bid_e4",
    "best_yes_ask_e4",
    "yes_levels",
    "no_levels",
    "levels",
    "yes_bid_depth",
    "yes_ask_depth",
)


def _csv_data_rows(path: Path) -> int:
    if not path.is_file():
        return 0
    # Header-only files have zero data rows.
    with path.open("r", encoding="utf-8") as fh:
        lines = [ln for ln in fh.read().splitlines() if ln.strip()]
    return max(0, len(lines) - 1) if lines else 0


def _dir_listing_hash(path: Path) -> str:
    """Hash a directory listing. Empty / missing dirs hash the empty listing."""
    if not path.exists() or not path.is_dir():
        return _hash_text(f"missing:{path.as_posix()}")
    names = sorted(p.name for p in path.iterdir())
    return _hash_text("\n".join(names))


def _hash_text(text: str) -> str:
    from hashlib import sha256

    return sha256(text.encode("utf-8")).hexdigest()


def inspected_nba_paths(cfg: RollerConfig, season: str = "2025-2026") -> dict[str, Path]:
    key = season_path_key(cfg, PHASE7_SPORT, season)
    canon = canonical_dir(cfg.root, PHASE7_SPORT, key)
    raw = raw_dir(cfg.root, PHASE7_SPORT, key)
    _, _, wh = load_sport_games(cfg, PHASE7_SPORT, season)
    sport_key = str(cfg.season_meta(PHASE7_SPORT, season)["warehouse_sport"])
    return {
        "canonical_stub": canon / "kalshi_orderbook_snapshots" / "month=empty.csv",
        "raw_orderbook": raw / "kalshi" / "orderbook",
        "suite_raw_kalshi": wh / "raw" / "kalshi" / sport_key,
        "suite_manifest": wh / "manifests" / sport_key / "dataset_manifest.json",
    }


def inventory_nba_orderbook(cfg: RollerConfig, season: str = "2025-2026") -> dict[str, Any]:
    paths = inspected_nba_paths(cfg, season)
    hashes: dict[str, str] = {}
    notes: dict[str, Any] = {}
    stub = paths["canonical_stub"]
    hashes["canonical_stub"] = sha256_file(stub) if stub.is_file() else ""
    notes["canonical_stub_rows"] = _csv_data_rows(stub)
    raw = paths["raw_orderbook"]
    hashes["raw_orderbook"] = _dir_listing_hash(raw)
    notes["raw_orderbook_files"] = (
        len([p for p in raw.iterdir() if p.is_file()]) if raw.is_dir() else 0
    )
    suite_raw = paths["suite_raw_kalshi"]
    hashes["suite_raw_kalshi"] = _dir_listing_hash(suite_raw)
    notes["suite_raw_children"] = (
        sorted(p.name for p in suite_raw.iterdir()) if suite_raw.is_dir() else []
    )
    notes["suite_raw_has_orderbook"] = "orderbook" in notes["suite_raw_children"]
    man = paths["suite_manifest"]
    hashes["suite_manifest"] = sha256_file(man) if man.is_file() else ""
    notes["orderbook_depth_available"] = False
    notes["market_data_type"] = ""
    if man.is_file():
        import json

        payload = json.loads(man.read_text(encoding="utf-8"))
        notes["orderbook_depth_available"] = bool(payload.get("orderbook_depth_available"))
        notes["market_data_type"] = str(payload.get("market_data_type") or "")
    snapshot_rows = int(notes["canonical_stub_rows"])
    if notes["raw_orderbook_files"] or notes["suite_raw_has_orderbook"] or notes["orderbook_depth_available"]:
        # NBA contract for this version is still SOURCE_UNAVAILABLE unless a
        # real NBA snapshot file exists. Do not ingest; report the finding.
        pass
    return {
        "availability": AVAILABILITY_UNAVAILABLE,
        "snapshot_rows": snapshot_rows,
        "depth": "NONE",
        "top_of_book": "NONE",
        "market_data_basis": MARKET_DATA_BASIS,
        "inspected_paths": [str(p) for p in paths.values()],
        "source_hashes": hashes,
        "inventory": notes,
        "sport": PHASE7_SPORT,
        "season": season,
    }


def reject_hypothetical_l2(frame: pd.DataFrame) -> None:
    """Fixture-only schema guard. Never called from NBA warehouse construction.

    Candle columns are not an orderbook snapshot. Must never emit parquet.
    """
    if frame is None or frame.empty:
        raise ValueError("hypothetical L2 fixture is empty")
    cols = {str(c) for c in frame.columns}
    candle = [c for c in CANDLE_INSUFFICIENT_COLUMNS if c in cols]
    book = [c for c in HYPOTHETICAL_BOOK_FIELDS if c in cols]
    if candle and not book:
        raise ValueError(
            f"candle columns are not an orderbook snapshot: {candle}"
        )
    if candle:
        raise ValueError(
            f"candle columns cannot upgrade to L2 even with book fields present: {candle}"
        )
    if not book:
        raise ValueError("hypothetical L2 fixture has no book fields")
    for rec in frame.to_dict("records"):
        for name in ("yes_bid_depth", "yes_ask_depth"):
            raw = rec.get(name)
            if raw in (None, ""):
                continue
            try:
                depth = int(raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"malformed {name}: {raw!r}") from exc
            if depth < 0:
                raise ValueError(f"negative depth is not repaired: {name}={depth}")
        levels = rec.get("levels") or rec.get("yes_levels")
        if isinstance(levels, str) and levels.strip() and levels.strip()[0] not in "[{":
            raise ValueError(f"malformed levels: {levels!r}")


def declare_nba_orderbook_capability(
    cfg: RollerConfig,
    *,
    season: str = "2025-2026",
    write: bool = True,
) -> dict[str, Any]:
    """Persist capability.json only. Never writes OrderbookSnapshot parquet."""
    inv = inventory_nba_orderbook(cfg, season)
    payload = {
        "availability": AVAILABILITY_UNAVAILABLE,
        "snapshot_rows": 0,
        "depth": "NONE",
        "top_of_book": "NONE",
        "market_data_basis": MARKET_DATA_BASIS,
        "inspected_paths": inv["inspected_paths"],
        "source_hashes": inv["source_hashes"],
        "inventory": inv["inventory"],
        "sport": PHASE7_SPORT,
        "season": season,
        "parquet_emitted": False,
        "updated_at": now_utc_iso(),
    }
    if write:
        dest = orderbook_capability_path(cfg, PHASE7_SPORT, season)
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Refuse any leftover parquet if a previous experiment created one.
        for leftover in dest.parent.glob("*.parquet"):
            raise ValueError(f"NBA orderbook parquet must not exist: {leftover}")
        write_json(dest, payload)
        readme = warehouse_v0_readme_path(cfg, PHASE7_SPORT, season)
        if not readme.is_file():
            readme.write_text(
                "Provisional NBA warehouse_v0. Not Confirm & Run. Phase 8 will relocate.\n",
                encoding="utf-8",
            )
    payload["capability_path"] = str(orderbook_capability_path(cfg, PHASE7_SPORT, season))
    payload["orderbook_dir"] = str(orderbook_dir(cfg, PHASE7_SPORT, season))
    return payload


def nba_orderbook_parquet_files(cfg: RollerConfig, season: str = "2025-2026") -> list[Path]:
    folder = orderbook_dir(cfg, PHASE7_SPORT, season)
    if not folder.is_dir():
        return []
    return sorted(folder.glob("*.parquet"))
