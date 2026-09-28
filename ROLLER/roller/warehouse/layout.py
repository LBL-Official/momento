"""Phase 8 physical NBA warehouse. Storage only.

Writes the selected Parquet tree. Does not switch Confirm & Run.
Does not emit an orderbook dataset. Observation path keeps
basis=tradable_yes_bid. Candle PIT field available_at is preserved exactly.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from roller.config import RollerConfig
from roller.io_csv import read_csv_optional, write_json
from roller.timeutil import now_utc_iso
from roller.warehouse.identity import (
    IDENTITY_ARTIFACT_COLUMNS,
    IDENTITY_RULE_VERSION,
    identity_artifact_path,
    source_system_for,
)
from roller.warehouse.layout_v0 import (
    crosswalk_path,
    markets_parquet_path,
    observations_dir as v0_observations_dir,
    pbp_dir as v0_pbp_dir,
    season_path_key,
    settlements_parquet_path,
    warehouse_v0_root,
)
from roller.warehouse.partitioning import list_month_parquets, month_key, month_parquet

PHASE8_SPORT = "NBA"
WAREHOUSE_NAME = "warehouse"
OBSERVATION_BASIS_DIR = "basis=tradable_yes_bid"
DEFAULT_COMPRESSION = "zstd"
DEFAULT_ROW_GROUP = 262144

GAME_COLUMNS = [
    "internal_game_id",
    "sport",
    "season",
    "league",
    "game_date",
    "home_team_id",
    "away_team_id",
    "home_team_name",
    "away_team_name",
    "source_game_id",
    "warehouse_game_id",
    "event_ticker",
    "source_system",
    "identity_rule_version",
    "mapping_status",
]

OBS_FINGERPRINT_COLS = [
    "ticker",
    "market_id",
    "internal_game_id",
    "available_at",
    "event_timestamp",
    "candle_timestamp",
    "yes_bid_open",
    "yes_bid_high",
    "yes_bid_low",
    "yes_bid_close",
    "yes_ask_open",
    "yes_ask_high",
    "yes_ask_low",
    "yes_ask_close",
    "volume",
    "basis",
    "game_link_status",
]

PBP_FINGERPRINT_COLS = [
    "internal_game_id",
    "event_number",
    "event_timestamp",
    "time_actual",
    "available_at",
    "period",
    "clock",
    "home_score",
    "away_score",
    "event_type",
    "source_game_id",
]

SETTLE_FINGERPRINT_COLS = [
    "market_id",
    "ticker",
    "internal_game_id",
    "settlement_status",
    "settlement_value_e4",
    "source_result",
    "source_settled_at",
]

OBS_SORT = ["internal_game_id", "market_id", "available_at"]
PBP_SORT = ["internal_game_id", "event_number"]
SETTLE_SORT = ["market_id"]
MARKET_SORT = ["market_id"]
LINK_SORT = ["market_id"]
GAME_SORT = ["internal_game_id"]

WAREHOUSE_README = """# NBA warehouse (Phase 8 physical layout)

Not a Confirm & Run source. Execution still reads published CSV.

observation_basis: TRADABLE_YES_BID
observation_resolution: 1_MINUTE_CANDLE
tick_data_available: false
orderbook_data_available: false
candle_pit_available: true
candle_pit_field: available_at
pbp_pit_aligned_to_candles: false
"""


def warehouse_root(cfg: RollerConfig, sport: str = PHASE8_SPORT, season: str = "2025-2026") -> Path:
    key = season_path_key(cfg, sport, season)
    return cfg.root / "data" / sport.lower() / key / "derived" / WAREHOUSE_NAME


def games_path(cfg: RollerConfig, sport: str = PHASE8_SPORT, season: str = "2025-2026") -> Path:
    return warehouse_root(cfg, sport, season) / "games" / "games.parquet"


def markets_path(cfg: RollerConfig, sport: str = PHASE8_SPORT, season: str = "2025-2026") -> Path:
    return warehouse_root(cfg, sport, season) / "markets" / "markets.parquet"


def links_path(cfg: RollerConfig, sport: str = PHASE8_SPORT, season: str = "2025-2026") -> Path:
    return warehouse_root(cfg, sport, season) / "game_market_links" / "links.parquet"


def settlements_path(cfg: RollerConfig, sport: str = PHASE8_SPORT, season: str = "2025-2026") -> Path:
    return warehouse_root(cfg, sport, season) / "settlements" / "settlements.parquet"


def observations_dir(
    cfg: RollerConfig,
    sport: str = PHASE8_SPORT,
    season: str = "2025-2026",
    *,
    basis: str | None = None,
) -> Path:
    token = str(basis or "").strip().upper().replace(" ", "_")
    folder = OBSERVATION_BASIS_DIR
    if token == "LAST_TRADE_PRINT":
        folder = "basis=last_trade_print"
    return warehouse_root(cfg, sport, season) / "observations" / folder


def pbp_dir(cfg: RollerConfig, sport: str = PHASE8_SPORT, season: str = "2025-2026") -> Path:
    return warehouse_root(cfg, sport, season) / "pbp"


def manifest_path(cfg: RollerConfig, sport: str = PHASE8_SPORT, season: str = "2025-2026") -> Path:
    return warehouse_root(cfg, sport, season) / "manifest.json"


def _stringify(frame: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    work = pd.DataFrame()
    for col in cols:
        if col not in frame.columns:
            work[col] = ""
        else:
            work[col] = frame[col].map(lambda v: "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v))
    return work


def fingerprint_frame(frame: pd.DataFrame, cols: list[str]) -> tuple[str, int]:
    if frame is None or frame.empty:
        return hashlib.sha256(b"empty").hexdigest(), 0
    work = _stringify(frame, cols)
    work = work.sort_values(cols, kind="mergesort").reset_index(drop=True)
    digest = hashlib.sha256(pd.util.hash_pandas_object(work, index=False).values.tobytes()).hexdigest()
    return digest, int(len(work))


def concat_month_parquets(directory: Path, columns: list[str] | None = None) -> pd.DataFrame:
    files = list_month_parquets(directory)
    if not files:
        return pd.DataFrame(columns=columns or [])
    parts = [pd.read_parquet(path, columns=columns) for path in files]
    return pd.concat(parts, ignore_index=True)


def write_sorted_parquet(
    frame: pd.DataFrame,
    path: Path,
    *,
    sort_cols: list[str],
    compression: str = DEFAULT_COMPRESSION,
    row_group_size: int = DEFAULT_ROW_GROUP,
) -> None:
    present = [c for c in sort_cols if c in frame.columns]
    work = frame.sort_values(present, kind="mergesort").reset_index(drop=True) if present else frame.reset_index(drop=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(work, preserve_index=False)
    pq.write_table(table, path, compression=compression, row_group_size=row_group_size)


def project_games(identity: pd.DataFrame, *, sport: str = PHASE8_SPORT) -> pd.DataFrame:
    if identity.empty:
        return pd.DataFrame(columns=GAME_COLUMNS)
    scoped = identity
    if "sport" in identity.columns:
        scoped = identity[identity["sport"].astype(str) == sport]
    rows = []
    for rec in scoped.to_dict("records"):
        gid = str(rec.get("internal_game_id") or "").strip()
        if not gid:
            continue
        rows.append(
            {
                "internal_game_id": gid,
                "sport": str(rec.get("sport") or sport),
                "season": str(rec.get("season") or ""),
                "league": str(rec.get("sport") or sport),
                "game_date": str(rec.get("game_date") or ""),
                "home_team_id": str(rec.get("home_team_id") or ""),
                "away_team_id": str(rec.get("away_team_id") or ""),
                "home_team_name": str(rec.get("home_team_name") or ""),
                "away_team_name": str(rec.get("away_team_name") or ""),
                "source_game_id": str(rec.get("source_game_id") or ""),
                "warehouse_game_id": str(rec.get("warehouse_game_id") or ""),
                "event_ticker": str(rec.get("event_ticker") or ""),
                "source_system": source_system_for(sport) or "nba_stats",
                "identity_rule_version": IDENTITY_RULE_VERSION,
                "mapping_status": str(rec.get("mapping_status") or ""),
            }
        )
    frame = pd.DataFrame(rows, columns=GAME_COLUMNS)
    return frame.sort_values(GAME_SORT, kind="mergesort").reset_index(drop=True)


def inspect_parquet_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"path": str(path), "exists": False}
    pf = pq.ParquetFile(path)
    groups = []
    for i in range(pf.metadata.num_row_groups):
        rg = pf.metadata.row_group(i)
        groups.append({"rows": rg.num_rows, "bytes": rg.total_byte_size})
    codecs = set()
    if pf.metadata.num_row_groups:
        rg0 = pf.metadata.row_group(0)
        for c in range(rg0.num_columns):
            codecs.add(str(rg0.column(c).compression))
    return {
        "path": str(path),
        "exists": True,
        "bytes": int(path.stat().st_size),
        "rows": int(pf.metadata.num_rows),
        "row_groups": int(pf.metadata.num_row_groups),
        "avg_row_group_rows": (
            int(pf.metadata.num_rows / pf.metadata.num_row_groups) if pf.metadata.num_row_groups else 0
        ),
        "compression": sorted(codecs),
        "columns": [f.name for f in pf.schema_arrow],
        "row_group_detail": groups,
    }


def inspect_month_dir(directory: Path) -> dict[str, Any]:
    files = list_month_parquets(directory)
    details = [inspect_parquet_file(p) | {"month": month_key(p)} for p in files]
    return {
        "dir": str(directory),
        "file_count": len(files),
        "total_bytes": sum(int(d.get("bytes") or 0) for d in details),
        "total_rows": sum(int(d.get("rows") or 0) for d in details),
        "files": details,
    }


def available_at_values(frame: pd.DataFrame) -> list[str]:
    if frame.empty or "available_at" not in frame.columns:
        return []
    return ["" if v is None else str(v) for v in frame["available_at"].tolist()]


def orderbook_partition_exists(root: Path) -> bool:
    folder = root / "orderbook"
    if not folder.exists():
        return False
    return any(folder.glob("*.parquet"))


def write_nba_warehouse(
    cfg: RollerConfig,
    *,
    season: str = "2025-2026",
    compression: str = DEFAULT_COMPRESSION,
    row_group_size: int = DEFAULT_ROW_GROUP,
    dest: Path | None = None,
) -> dict[str, Any]:
    dest = Path(dest) if dest is not None else warehouse_root(cfg, PHASE8_SPORT, season)
    dest.mkdir(parents=True, exist_ok=True)
    identity = read_csv_optional(identity_artifact_path(cfg), IDENTITY_ARTIFACT_COLUMNS)
    games = project_games(identity)
    write_sorted_parquet(
        games,
        dest / "games" / "games.parquet",
        sort_cols=GAME_SORT,
        compression=compression,
        row_group_size=row_group_size,
    )

    markets_src = markets_parquet_path(cfg)
    markets = pd.read_parquet(markets_src) if markets_src.is_file() else pd.DataFrame()
    write_sorted_parquet(
        markets,
        dest / "markets" / "markets.parquet",
        sort_cols=MARKET_SORT,
        compression=compression,
        row_group_size=row_group_size,
    )

    links_src = crosswalk_path(cfg)
    links = pd.read_parquet(links_src) if links_src.is_file() else pd.DataFrame()
    write_sorted_parquet(
        links,
        dest / "game_market_links" / "links.parquet",
        sort_cols=LINK_SORT,
        compression=compression,
        row_group_size=row_group_size,
    )

    settle_src = settlements_parquet_path(cfg)
    settles = pd.read_parquet(settle_src) if settle_src.is_file() else pd.DataFrame()
    write_sorted_parquet(
        settles,
        dest / "settlements" / "settlements.parquet",
        sort_cols=SETTLE_SORT,
        compression=compression,
        row_group_size=row_group_size,
    )

    obs_src = v0_observations_dir(cfg)
    obs_dest = dest / "observations" / OBSERVATION_BASIS_DIR
    obs_dest.mkdir(parents=True, exist_ok=True)
    obs_months: dict[str, int] = {}
    obs_fps: list[str] = []
    available_at_ok = True
    for src in list_month_parquets(obs_src):
        month = month_key(src)
        frame = pd.read_parquet(src)
        before = available_at_values(frame)
        write_sorted_parquet(
            frame,
            month_parquet(obs_dest, month),
            sort_cols=OBS_SORT,
            compression=compression,
            row_group_size=row_group_size,
        )
        written = pd.read_parquet(month_parquet(obs_dest, month))
        after = available_at_values(written)
        if sorted(before) != sorted(after):
            available_at_ok = False
            raise ValueError(f"available_at PIT drift in month {month}")
        obs_months[month] = int(len(frame))
        fp, n = fingerprint_frame(frame, OBS_FINGERPRINT_COLS)
        fp2, n2 = fingerprint_frame(written, OBS_FINGERPRINT_COLS)
        if fp != fp2 or n != n2:
            raise ValueError(f"observation fingerprint mismatch month {month}")
        obs_fps.append(f"{month}:{fp}")

    pbp_src = v0_pbp_dir(cfg)
    pbp_dest = dest / "pbp"
    pbp_dest.mkdir(parents=True, exist_ok=True)
    pbp_months: dict[str, int] = {}
    for src in list_month_parquets(pbp_src):
        month = month_key(src)
        frame = pd.read_parquet(src)
        write_sorted_parquet(
            frame,
            month_parquet(pbp_dest, month),
            sort_cols=PBP_SORT,
            compression=compression,
            row_group_size=row_group_size,
        )
        written = pd.read_parquet(month_parquet(pbp_dest, month))
        fp, n = fingerprint_frame(frame, PBP_FINGERPRINT_COLS)
        fp2, n2 = fingerprint_frame(written, PBP_FINGERPRINT_COLS)
        if fp != fp2 or n != n2:
            raise ValueError(f"PBP fingerprint mismatch month {month}")
        pbp_months[month] = n

    if orderbook_partition_exists(dest):
        raise ValueError("selected warehouse must not contain an orderbook parquet partition")

    (dest / "README.md").write_text(WAREHOUSE_README, encoding="utf-8")
    manifest = {
        "artifact": "nba_warehouse",
        "sport": PHASE8_SPORT,
        "season": season,
        "observation_basis": "TRADABLE_YES_BID",
        "observation_resolution": "1_MINUTE_CANDLE",
        "tick_data_available": False,
        "orderbook_data_available": False,
        "candle_pit_available": True,
        "candle_pit_field": "available_at",
        "pbp_pit_aligned_to_candles": False,
        "partition": "sport/season/month",
        "observation_path": f"observations/{OBSERVATION_BASIS_DIR}/month=YYYY-MM.parquet",
        "sort": {
            "observations": OBS_SORT,
            "pbp": PBP_SORT,
            "settlements": SETTLE_SORT,
        },
        "compression": compression,
        "row_group_size": row_group_size,
        "games": int(len(games)),
        "markets": int(len(markets)),
        "links": int(len(links)),
        "settlements": int(len(settles)),
        "observation_months": obs_months,
        "observation_rows": int(sum(obs_months.values())),
        "pbp_months": pbp_months,
        "pbp_rows": int(sum(pbp_months.values())),
        "available_at_preserved": available_at_ok,
        "baseline_root": str(warehouse_v0_root(cfg)),
        "warehouse_root": str(dest),
        "updated_at": now_utc_iso(),
    }
    write_json(dest / "manifest.json", manifest)
    return manifest


def assert_layout_contract(root: Path) -> None:
    obs = root / "observations" / OBSERVATION_BASIS_DIR
    if not obs.is_dir():
        raise ValueError("observations must live under basis=tradable_yes_bid")
    if (root / "observations" / "basis=orderbook_snapshot").exists():
        raise ValueError("orderbook observation partition is not part of this contract")
    if (root / "observations" / "basis=last_trade_print").exists():
        raise ValueError("tick/last-trade partition is not part of this contract")
    if orderbook_partition_exists(root):
        raise ValueError("orderbook parquet partition is not part of this contract")
