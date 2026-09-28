"""Phase 8 parquet desk via in-memory DuckDB. Pointers only. Never write parquet."""

from __future__ import annotations

import json
import math
import re
import threading
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from roller.config import RollerConfig
from roller.jump.errors import JumpError
from roller.jump.library import repo_root
from roller.jump.versions import LIVE_EXECUTION
from roller.jump.warehouse import DEFAULT_LIMIT, MAX_LIMIT
from roller.jump.warehouse.registry import WarehouseRecord, get_warehouse, require_available
from roller.jump.warehouse.sql_guard import assert_readonly_sql
from roller.warehouse.coverage import (
    DATA_REQUIRED_CAPABILITIES,
    OPERATION_REQUIRED_CAPABILITIES,
    OBS_BASIS,
    OBS_RESOLUTION,
    PIT_FIELD,
    CapabilityName,
)
from roller.warehouse.desk import DEFAULT_SEASON
from roller.warehouse.layout import (
    GAME_COLUMNS,
    OBS_FINGERPRINT_COLS,
    PBP_FINGERPRINT_COLS,
    SETTLE_FINGERPRINT_COLS,
    games_path,
    inspect_parquet_file,
    links_path,
    markets_path,
    observations_dir,
    pbp_dir,
    settlements_path,
    warehouse_root,
)
from roller.warehouse.market_link import MARKET_COLUMNS
from roller.warehouse.partitioning import list_month_parquets, month_key

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_FILTER_OPS = {
    "eq": "=",
    "ne": "<>",
    "lt": "<",
    "lte": "<=",
    "gt": ">",
    "gte": ">=",
}
LINK_COLUMNS = [
    "market_id",
    "ticker",
    "internal_game_id",
    "event_ticker",
    "link_status",
    "link_method",
    "source_evidence",
    "sport",
    "season",
    "team_side",
    "identity_rule_version",
    "link_rule_version",
]
RESEARCH_USERS = {
    "nba": ("FIRST80_ASKED_SIX_80_40",),
    "ncaab": ("FIRST80_ASKED_SIX_80_40",),
    "wnba": ("FIRST80_ASKED_SIX_80_40",),
}

_COLUMN_HELP = {
    "internal_game_id": "Warehouse game identity. Declared join key.",
    "market_id": "Warehouse market identity. Declared join key.",
    "ticker": "Kalshi ticker. Declared join key via GameMarketLink.",
    "available_at": "Candle PIT field. Not PBP↔candle alignment.",
    "event_timestamp": "Source event time. Alignment to candles is OPERATION_REQUIRED for PBP.",
    "basis": "Observation basis. TRADABLE_YES_BID is not LAST_TRADE_PRINT.",
    "yes_bid_close": "Tradable YES bid close. Candle path is not a fill.",
    "settlement_value_e4": "Settlement in e4 integer units. Not invented L2.",
    "pbp_pit_aligned_to_candles": "False on this desk. OPERATION_REQUIRED.",
    "link_status": "GameMarketLink status. Canonical mapping, not name match.",
}

_LOCK = threading.Lock()
_CONNECTIONS: dict[str, Any] = {}

LOGICAL_TABLES = (
    "games",
    "markets",
    "game_market_links",
    "observations",
    "pbp",
    "settlements",
)


def _cfg(root: Path | None = None) -> RollerConfig:
    return RollerConfig(root=(root or repo_root()) / "ROLLER")


def _ident(name: str, *, what: str = "identifier") -> str:
    token = str(name or "").strip()
    if not _IDENT.match(token):
        raise JumpError("QUERY_REJECTED", f"invalid {what}")
    return token


def _cell(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    text = str(value)
    if text in {"NaT", "NaN", "None", "<NA>"}:
        return None
    return value if isinstance(value, str) else text


def _limit(raw: int | None) -> int:
    try:
        value = int(raw if raw is not None else DEFAULT_LIMIT)
    except (TypeError, ValueError) as exc:
        raise JumpError("QUERY_REJECTED", "limit must be an integer") from exc
    if value < 1:
        value = DEFAULT_LIMIT
    return min(value, MAX_LIMIT)


def _page(raw: int | None) -> int:
    try:
        value = int(raw if raw is not None else 1)
    except (TypeError, ValueError):
        value = 1
    return max(value, 1)


def _sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def _parquet_rows(path: Path) -> int:
    if not path.is_file():
        return 0
    return int(pq.ParquetFile(path).metadata.num_rows)


def _month_meta(directory: Path) -> list[dict[str, Any]]:
    out = []
    for path in list_month_parquets(directory):
        info = inspect_parquet_file(path)
        out.append(
            {
                "month": month_key(path),
                "path": str(path.name),
                "rows": info.get("rows") or 0,
                "bytes": info.get("bytes") or 0,
                "columns": info.get("columns") or [],
            }
        )
    return out


def _schema_names(path: Path) -> list[str]:
    if path.is_file():
        return [f.name for f in pq.ParquetFile(path).schema_arrow]
    files = list_month_parquets(path)
    if not files:
        return []
    return [f.name for f in pq.ParquetFile(files[0]).schema_arrow]


def _column_types(path: Path) -> list[dict[str, Any]]:
    target = path if path.is_file() else (list_month_parquets(path)[0] if path.is_dir() else None)
    if target is None or not target.is_file():
        return []
    pf = pq.ParquetFile(target)
    out = []
    for field in pf.schema_arrow:
        out.append(
            {
                "name": field.name,
                "type": str(field.type),
                "nullable": bool(field.nullable),
                "description": _COLUMN_HELP.get(field.name, "Unavailable"),
                "pit": field.name == PIT_FIELD,
            }
        )
    return out


def table_spec(record: WarehouseRecord, name: str, *, root: Path | None = None) -> dict[str, Any]:
    table = str(name or "").strip().lower()
    if table not in LOGICAL_TABLES:
        raise JumpError("RESULT_NOT_FOUND", f"unknown table {name}")
    cfg = _cfg(root)
    sport = record.sport
    season = record.season or DEFAULT_SEASON
    desk = warehouse_root(cfg, sport, season)
    users = list(RESEARCH_USERS.get(record.id, ()))
    if table == "games":
        path = games_path(cfg, sport, season)
        return {
            "name": table,
            "logical_name": f"{record.id}.{table}",
            "kind": "identity",
            "partitioned": False,
            "path": path,
            "glob": None,
            "declared_columns": list(GAME_COLUMNS),
            "sort": ["internal_game_id"],
            "row_count": _parquet_rows(path),
            "pit_field": None,
            "pit_status": "NOT_APPLICABLE",
            "used_by": users,
        }
    if table == "markets":
        path = markets_path(cfg, sport, season)
        return {
            "name": table,
            "logical_name": f"{record.id}.{table}",
            "kind": "identity",
            "partitioned": False,
            "path": path,
            "glob": None,
            "declared_columns": list(MARKET_COLUMNS),
            "sort": ["market_id"],
            "row_count": _parquet_rows(path),
            "pit_field": None,
            "pit_status": "NOT_APPLICABLE",
            "used_by": users,
        }
    if table == "game_market_links":
        path = links_path(cfg, sport, season)
        return {
            "name": table,
            "logical_name": f"{record.id}.{table}",
            "kind": "canonical_mapping",
            "partitioned": False,
            "path": path,
            "glob": None,
            "declared_columns": list(LINK_COLUMNS),
            "sort": ["market_id"],
            "row_count": _parquet_rows(path),
            "pit_field": None,
            "pit_status": "NOT_APPLICABLE",
            "used_by": users,
        }
    if table == "observations":
        directory = observations_dir(cfg, sport, season)
        months = _month_meta(directory)
        return {
            "name": table,
            "logical_name": f"{record.id}.{table}",
            "kind": "tradable_yes_bid",
            "partitioned": True,
            "path": directory,
            "glob": directory / "month=*.parquet",
            "declared_columns": list(OBS_FINGERPRINT_COLS),
            "sort": ["internal_game_id", "market_id", "available_at"],
            "row_count": sum(int(m["rows"]) for m in months),
            "months": months,
            "pit_field": PIT_FIELD,
            "pit_status": "CANDLE_PIT",
            "observation_basis": OBS_BASIS,
            "observation_resolution": OBS_RESOLUTION,
            "used_by": users,
        }
    if table == "pbp":
        directory = pbp_dir(cfg, sport, season)
        months = _month_meta(directory)
        return {
            "name": table,
            "logical_name": f"{record.id}.{table}",
            "kind": "sequence_only",
            "partitioned": True,
            "path": directory,
            "glob": directory / "month=*.parquet",
            "declared_columns": list(PBP_FINGERPRINT_COLS),
            "sort": ["internal_game_id", "event_number"],
            "row_count": sum(int(m["rows"]) for m in months),
            "months": months,
            "pit_field": PIT_FIELD,
            "pit_status": "OPERATION_REQUIRED",
            "pbp_pit_aligned_to_candles": False,
            "used_by": users,
        }
    path = settlements_path(cfg, sport, season)
    return {
        "name": table,
        "logical_name": f"{record.id}.{table}",
        "kind": "settlement",
        "partitioned": False,
        "path": path,
        "glob": None,
        "declared_columns": list(SETTLE_FINGERPRINT_COLS),
        "sort": ["market_id"],
        "row_count": _parquet_rows(path),
        "pit_field": None,
        "pit_status": "NOT_APPLICABLE",
        "used_by": users,
        "desk": desk,
    }


def _view_sql(spec: dict[str, Any]) -> str:
    target = spec.get("glob") or spec["path"]
    return f"SELECT * FROM read_parquet('{_sql_path(Path(target))}', union_by_name=true, hive_partitioning=0)"


def _connect(record: WarehouseRecord, *, root: Path | None = None):
    import duckdb

    key = f"{record.id}:{record.season}"
    with _LOCK:
        con = _CONNECTIONS.get(key)
        if con is not None:
            return con
        con = duckdb.connect(database=":memory:")
        con.execute("SET enable_progress_bar=false")
        for name in LOGICAL_TABLES:
            spec = table_spec(record, name, root=root)
            path = spec.get("glob") or spec["path"]
            if spec["partitioned"]:
                files = list_month_parquets(Path(spec["path"]))
                if not files:
                    continue
            elif not Path(path).is_file() and not spec["partitioned"]:
                if not Path(spec["path"]).is_file():
                    continue
            con.execute(f"CREATE VIEW {name} AS {_view_sql(spec)}")
        _CONNECTIONS[key] = con
        return con


def reset_connections() -> None:
    with _LOCK:
        _CONNECTIONS.clear()


def _parse_filters(raw: Any) -> list[dict[str, Any]]:
    if raw is None or raw == "":
        return []
    if isinstance(raw, list):
        return [row for row in raw if isinstance(row, dict)]
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                body = json.loads(text)
            except json.JSONDecodeError as exc:
                raise JumpError("QUERY_REJECTED", "filters must be JSON") from exc
            if isinstance(body, list):
                return [row for row in body if isinstance(row, dict)]
        parts = []
        for chunk in text.split(";"):
            bits = chunk.split(":", 2)
            if len(bits) >= 2:
                parts.append(
                    {
                        "column": bits[0],
                        "op": bits[1],
                        "value": bits[2] if len(bits) == 3 else None,
                    }
                )
        return parts
    raise JumpError("QUERY_REJECTED", "filters must be a list")


def _where(filters: list[dict[str, Any]], columns: list[str]) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    allowed = set(columns)
    for row in filters:
        col = _ident(str(row.get("column") or ""), what="filter column")
        if col not in allowed:
            raise JumpError("QUERY_REJECTED", f"unknown filter column {col}")
        op = str(row.get("op") or "eq").strip().lower()
        if op in {"is_null", "null"}:
            clauses.append(f"{col} IS NULL")
            continue
        if op in {"not_null", "is_not_null"}:
            clauses.append(f"{col} IS NOT NULL")
            continue
        if op == "contains":
            clauses.append(f"CAST({col} AS VARCHAR) LIKE ?")
            params.append(f"%{row.get('value') or ''}%")
            continue
        if op not in _FILTER_OPS:
            raise JumpError("QUERY_REJECTED", f"unsupported filter op {op}")
        clauses.append(f"{col} {_FILTER_OPS[op]} ?")
        params.append(row.get("value"))
    if not clauses:
        return "", []
    return " WHERE " + " AND ".join(clauses), params


def _wrap_limit(sql: str, limit: int) -> str:
    upper = sql.upper()
    if upper.startswith(("EXPLAIN", "DESCRIBE", "DESC ", "SHOW")):
        return sql
    match = list(re.finditer(r"\bLIMIT\s+(\d+)\b", sql, flags=re.IGNORECASE))
    if match:
        last = match[-1]
        user_n = int(last.group(1))
        if user_n > limit:
            return sql[: last.start(1)] + str(limit) + sql[last.end(1) :]
        return sql
    return f"SELECT * FROM ({sql}) AS _jump_q LIMIT {limit}"


class ParquetDeskAdapter:
    def __init__(self, warehouse_id: str, *, root: Path | None = None):
        self.warehouse_id = warehouse_id
        self.root = root or repo_root()
        self.record = require_available(warehouse_id, root=self.root)

    def _con(self):
        return _connect(self.record, root=self.root)

    def inspect(self) -> dict[str, Any]:
        rec = self.record
        cfg = _cfg(self.root)
        desk = warehouse_root(cfg, rec.sport, rec.season)
        readme = desk / "README.md"
        return {
            **rec.as_dict(),
            "tables": self.list_tables(),
            "unavailable_sources": self.unavailable_sources(),
            "readme": readme.read_text(encoding="utf-8") if readme.is_file() else None,
            "live_execution": LIVE_EXECUTION,
        }

    def unavailable_sources(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "orderbook",
                "status": "SOURCE_UNAVAILABLE",
                "capability": CapabilityName.ORDERBOOK.value,
                "rows": 0,
                "note": "Do not emit a fake observations table. Historical L2 is DATA_REQUIRED.",
            },
            {
                "name": "ticks",
                "status": "SOURCE_UNAVAILABLE",
                "capability": CapabilityName.TICK.value,
                "rows": 0,
                "note": "Historical ticks are DATA_REQUIRED.",
            },
            {
                "name": "pbp_candle_pit_alignment",
                "status": "OPERATION_REQUIRED",
                "capability": CapabilityName.PBP_MARKET_PIT_ALIGNMENT.value,
                "note": "PBP available_at is not aligned to candle PIT.",
            },
        ]

    def list_tables(self) -> list[dict[str, Any]]:
        out = []
        for name in LOGICAL_TABLES:
            spec = table_spec(self.record, name, root=self.root)
            path = spec["path"]
            present = path.is_file() if not spec["partitioned"] else bool(list_month_parquets(path))
            out.append(
                {
                    "name": spec["name"],
                    "logical_name": spec["logical_name"],
                    "kind": spec["kind"],
                    "status": "AVAILABLE" if present else "UNAVAILABLE",
                    "row_count": spec["row_count"] if present else 0,
                    "partitioned": spec["partitioned"],
                    "pit_field": spec.get("pit_field"),
                    "pit_status": spec.get("pit_status"),
                    "used_by": spec.get("used_by") or [],
                    "sort": spec.get("sort") or [],
                }
            )
        return out

    def describe_table(self, table: str) -> dict[str, Any]:
        spec = table_spec(self.record, table, root=self.root)
        path = spec["path"]
        cols = _column_types(path)
        names = [c["name"] for c in cols] or _schema_names(path)
        return {
            "warehouse_id": self.record.id,
            "name": spec["name"],
            "logical_name": spec["logical_name"],
            "kind": spec["kind"],
            "status": "AVAILABLE" if names else "UNAVAILABLE",
            "row_count": spec["row_count"],
            "partitioned": spec["partitioned"],
            "months": spec.get("months") or [],
            "pit_field": spec.get("pit_field"),
            "pit_status": spec.get("pit_status"),
            "observation_basis": spec.get("observation_basis"),
            "observation_resolution": spec.get("observation_resolution"),
            "pbp_pit_aligned_to_candles": spec.get("pbp_pit_aligned_to_candles"),
            "used_by": spec.get("used_by") or [],
            "sort": spec.get("sort") or [],
            "declared_columns": spec.get("declared_columns") or [],
            "columns": cols or [{"name": n, "type": "UNKNOWN", "nullable": True, "description": "Unavailable"} for n in names],
            "source_uri": self.record.source_uri,
            "live_execution": LIVE_EXECUTION,
        }

    def columns(self, table: str) -> list[dict[str, Any]]:
        return self.describe_table(table)["columns"]

    def preview_rows(
        self,
        table: str,
        *,
        columns: list[str] | None = None,
        limit: int = DEFAULT_LIMIT,
        page: int = 1,
        sort: str | None = None,
        order: str = "asc",
        filters: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        spec = table_spec(self.record, table, root=self.root)
        table_name = spec["name"]
        schema_cols = [c["name"] for c in _column_types(spec["path"])] or _schema_names(spec["path"])
        if not schema_cols:
            raise JumpError("WAREHOUSE_UNAVAILABLE", f"{table_name} has no parquet files")
        if columns:
            proj = [_ident(c, what="column") for c in columns if str(c).strip()]
            missing = [c for c in proj if c not in schema_cols]
            if missing:
                raise JumpError("QUERY_REJECTED", f"unknown columns {missing}")
        else:
            proj = list(schema_cols)
        if not proj:
            raise JumpError("QUERY_REJECTED", "column projection required")
        cap = _limit(limit)
        page_n = _page(page)
        offset = (page_n - 1) * cap
        sort_col = _ident(sort, what="sort") if sort else None
        if sort_col and sort_col not in schema_cols:
            raise JumpError("QUERY_REJECTED", f"unknown sort column {sort_col}")
        direction = "DESC" if str(order).lower() == "desc" else "ASC"
        where_sql, params = _where(filters or [], schema_cols)
        select = ", ".join(proj)
        order_sql = f" ORDER BY {sort_col} {direction}" if sort_col else ""
        if not sort_col and spec.get("sort"):
            keys = [c for c in spec["sort"] if c in schema_cols]
            if keys:
                order_sql = " ORDER BY " + ", ".join(f"{c} ASC" for c in keys)
        con = self._con()
        if where_sql:
            count_sql = f"SELECT COUNT(*) FROM {table_name}{where_sql}"
            filtered_n = int(con.execute(count_sql, params).fetchone()[0])
        else:
            filtered_n = int(spec["row_count"])
        sql = (
            f"SELECT {select} FROM {table_name}{where_sql}{order_sql} LIMIT {cap} OFFSET {offset}"
        )
        rows = con.execute(sql, params).fetchall()
        out_rows = [{proj[i]: _cell(val) for i, val in enumerate(row)} for row in rows]
        return {
            "warehouse_id": self.record.id,
            "table": table_name,
            "columns": proj,
            "rows": out_rows,
            "limit": cap,
            "page": page_n,
            "offset": offset,
            "returned": len(out_rows),
            "filtered_row_count": filtered_n,
            "table_row_count": spec["row_count"],
            "sort": sort_col,
            "order": direction.lower(),
            "filters": filters or [],
            "nulls_preserved": True,
            "live_execution": LIVE_EXECUTION,
        }

    def stats(self, table: str, *, compute: bool = False) -> dict[str, Any]:
        spec = table_spec(self.record, table, root=self.root)
        path = spec["path"]
        files = [path] if path.is_file() else list_month_parquets(path)
        footers = [inspect_parquet_file(p) for p in files if p.is_file()]
        body: dict[str, Any] = {
            "warehouse_id": self.record.id,
            "table": spec["name"],
            "source": "parquet_footer",
            "exact": True,
            "sampled": False,
            "row_count": spec["row_count"],
            "file_count": len(footers),
            "bytes": sum(int(f.get("bytes") or 0) for f in footers),
            "row_groups": sum(int(f.get("row_groups") or 0) for f in footers),
            "compression": sorted({c for f in footers for c in (f.get("compression") or [])}),
            "compute": bool(compute),
            "live_execution": LIVE_EXECUTION,
        }
        if not compute:
            body["note"] = "Footer metadata only. Pass compute=1 for per-column null counts."
            return body
        con = self._con()
        cols = [c["name"] for c in _column_types(path)] or _schema_names(path)
        col_stats = []
        for col in cols:
            ident = _ident(col)
            row = con.execute(
                f"SELECT COUNT({ident}), COUNT(*) - COUNT({ident}) FROM {spec['name']}"
            ).fetchone()
            col_stats.append(
                {
                    "name": col,
                    "non_null": int(row[0] or 0),
                    "nulls": int(row[1] or 0),
                    "exact": True,
                    "sampled": False,
                }
            )
        body["source"] = "duckdb_count"
        body["columns"] = col_stats
        return body

    def lineage(self, table: str) -> dict[str, Any]:
        spec = table_spec(self.record, table, root=self.root)
        return {
            "warehouse_id": self.record.id,
            "table": spec["name"],
            "logical_name": spec["logical_name"],
            "source_system": "ROLLER",
            "source_uri": self.record.source_uri,
            "storage_type": "PARQUET_DIRECTORY",
            "confirm_and_run": "canonical CSV, not this parquet desk",
            "used_by": spec.get("used_by") or [],
            "pit_field": spec.get("pit_field") or "UNKNOWN",
            "pit_status": spec.get("pit_status") or "UNKNOWN",
            "writable_rows": False,
            "live_execution": LIVE_EXECUTION,
        }

    def physical_files(self) -> dict[str, Any]:
        cfg = _cfg(self.root)
        rec = self.record
        desk = warehouse_root(cfg, rec.sport, rec.season)
        parquet: list[dict[str, Any]] = []
        for name in LOGICAL_TABLES:
            spec = table_spec(rec, name, root=self.root)
            if spec["partitioned"]:
                for month in spec.get("months") or []:
                    parquet.append(
                        {
                            "table": name,
                            "layer": "phase8_parquet",
                            "path": f"{rec.source_uri}/{name}/{month['path']}",
                            "rows": month["rows"],
                            "bytes": month["bytes"],
                        }
                    )
            else:
                info = inspect_parquet_file(spec["path"])
                parquet.append(
                    {
                        "table": name,
                        "layer": "phase8_parquet",
                        "path": f"{rec.source_uri}/{spec['path'].relative_to(desk).as_posix() if spec['path'].exists() else spec['path'].name}",
                        "rows": info.get("rows") or 0,
                        "bytes": info.get("bytes") or 0,
                        "exists": bool(info.get("exists")),
                    }
                )
        canonical = cfg.root / "data" / rec.sport.lower() / rec.season.replace("-", "_") / "canonical"
        csv_layer = []
        if canonical.is_dir():
            csv_layer.append(
                {
                    "layer": "confirm_and_run_csv",
                    "path": str(canonical.relative_to(self.root)),
                    "note": "Confirm & Run still reads this CSV tree. Not the workbench database.",
                }
            )
        return {
            "warehouse_id": rec.id,
            "phase8_root": rec.source_uri,
            "parquet": parquet,
            "confirm_and_run_csv": csv_layer,
            "unavailable": self.unavailable_sources(),
            "live_execution": LIVE_EXECUTION,
        }

    def dictionary(self) -> dict[str, Any]:
        tables = []
        for name in LOGICAL_TABLES:
            desc = self.describe_table(name)
            tables.append(
                {
                    "name": desc["name"],
                    "logical_name": desc["logical_name"],
                    "kind": desc["kind"],
                    "row_count": desc["row_count"],
                    "pit_field": desc.get("pit_field"),
                    "pit_status": desc.get("pit_status"),
                    "used_by": desc.get("used_by") or [],
                    "columns": desc["columns"],
                }
            )
        return {
            "warehouse_id": self.record.id,
            "source_uri": self.record.source_uri,
            "observation_basis": OBS_BASIS,
            "observation_resolution": OBS_RESOLUTION,
            "pit_field": PIT_FIELD,
            "pbp_pit_aligned_to_candles": False,
            "orderbook": "SOURCE_UNAVAILABLE",
            "ticks": "SOURCE_UNAVAILABLE",
            "data_required": sorted(c.value for c in DATA_REQUIRED_CAPABILITIES),
            "operation_required": sorted(c.value for c in OPERATION_REQUIRED_CAPABILITIES),
            "tables": tables,
            "unknown_policy": "Unavailable / UNKNOWN. No invented semantics.",
            "live_execution": LIVE_EXECUTION,
        }

    def query(self, sql: str, *, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
        stmt = assert_readonly_sql(sql)
        cap = _limit(limit)
        guarded = _wrap_limit(stmt, cap)
        con = self._con()
        try:
            result = con.execute(guarded)
        except Exception as exc:
            raise JumpError("QUERY_FAILED", str(exc)) from exc
        columns = [c[0] for c in (result.description or [])]
        rows = result.fetchall()
        return {
            "warehouse_id": self.record.id,
            "sql": stmt,
            "executed_sql": guarded,
            "columns": columns,
            "rows": [{columns[i]: _cell(val) for i, val in enumerate(row)} for row in rows],
            "returned": len(rows),
            "limit": cap,
            "read_only": True,
            "live_execution": LIVE_EXECUTION,
        }

    def refresh_metadata(self) -> dict[str, Any]:
        reset_connections()
        rec = require_available(self.warehouse_id, root=self.root)
        self.record = rec
        return {"status": "ok", "warehouse_id": rec.id, "tables": self.list_tables(), "live_execution": LIVE_EXECUTION}

    def validate(self) -> dict[str, Any]:
        rec = get_warehouse(self.warehouse_id, root=self.root)
        cfg = _cfg(self.root)
        desk = warehouse_root(cfg, rec.sport, rec.season)
        games = games_path(cfg, rec.sport, rec.season)
        manifest = desk / "manifest.json"
        ok = rec.status == "AVAILABLE" and games.is_file() and manifest.is_file()
        return {
            "warehouse_id": rec.id,
            "status": "ok" if ok else "WAREHOUSE_UNAVAILABLE",
            "source_uri": rec.source_uri,
            "games_present": games.is_file(),
            "manifest_present": manifest.is_file(),
            "reason": None if ok else rec.unavailable_reason,
            "live_execution": LIVE_EXECUTION,
        }


def adapter_for(warehouse_id: str, *, root: Path | None = None) -> ParquetDeskAdapter:
    return ParquetDeskAdapter(warehouse_id, root=root)
