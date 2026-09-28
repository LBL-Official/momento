"""Atomic CSV store. CSV is SSOT. Crashed writes must not corrupt."""

from __future__ import annotations

import csv
import hashlib
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from roller.systimo.errors import SystimoError
from roller.systimo.paths import library_root
from roller.systimo.store.schema import (
    APPEND_ONLY,
    ENUMS,
    FOREIGN_KEYS,
    PRIMARY_KEYS,
    TABLE_FILES,
    TABLES,
)


class CsvStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else library_root()
        self._lock_depth = 0
        self._lock_fh = None
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        for folder in ("registry", "state", "queries", "artifacts", "actions", "agents", "generated", "transitions"):
            (self.root / folder).mkdir(parents=True, exist_ok=True)

    def path_for(self, table: str) -> Path:
        if table not in TABLE_FILES:
            raise SystimoError("UNKNOWN_TABLE", f"unknown table {table}")
        folder, name = TABLE_FILES[table]
        return self.root / folder / name

    def lock_path(self) -> Path:
        return self.root / ".systimo.lock"

    @contextmanager
    def exclusive(self) -> Iterator[None]:
        if self._lock_depth > 0:
            self._lock_depth += 1
            try:
                yield
            finally:
                self._lock_depth -= 1
            return
        path = self.lock_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = path.open("a+")
        try:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            self._lock_depth = 1
            self._lock_fh = fh
            yield
        finally:
            import fcntl

            self._lock_depth = 0
            self._lock_fh = None
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            fh.close()

    def checksum(self, table: str) -> str:
        path = self.path_for(table)
        if not path.is_file():
            return hashlib.sha256(b"").hexdigest()
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def read(self, table: str) -> list[dict[str, str]]:
        path = self.path_for(table)
        columns = TABLES[table]
        if not path.is_file():
            return []
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None:
                raise SystimoError("SCHEMA_INVALID", f"{table} has no header")
            if tuple(reader.fieldnames) != columns:
                raise SystimoError(
                    "SCHEMA_INVALID",
                    f"{table} columns {list(reader.fieldnames)} != {list(columns)}",
                )
            rows = []
            for raw in reader:
                rows.append({key: (raw.get(key) or "") for key in columns})
        return rows

    def write(self, table: str, rows: list[dict[str, str]]) -> None:
        if table in APPEND_ONLY:
            raise SystimoError("APPEND_ONLY", f"{table} is append-only")
        with self.exclusive():
            self._atomic_write(table, rows)

    def append(self, table: str, row: dict[str, str]) -> None:
        with self.exclusive():
            existing = self.read(table)
            existing.append(_normalize(table, row))
            self._validate(table, existing)
            self._atomic_write_unlocked(table, existing)

    def upsert(self, table: str, row: dict[str, str], *, key: str | None = None) -> None:
        pk = key or PRIMARY_KEYS[table]
        body = _normalize(table, row)
        with self.exclusive():
            rows = self.read(table)
            found = False
            out = []
            for item in rows:
                if item[pk] == body[pk]:
                    out.append(body)
                    found = True
                else:
                    out.append(item)
            if not found:
                out.append(body)
            self._validate(table, out)
            self._atomic_write_unlocked(table, out)

    def _atomic_write(self, table: str, rows: list[dict[str, str]]) -> None:
        normalized = [_normalize(table, row) for row in rows]
        self._validate(table, normalized)
        self._atomic_write_unlocked(table, normalized)

    def _atomic_write_unlocked(self, table: str, rows: list[dict[str, str]]) -> None:
        path = self.path_for(table)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{table}.", suffix=".tmp", dir=str(path.parent))
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=list(TABLES[table]), extrasaction="ignore")
                writer.writeheader()
                for row in rows:
                    writer.writerow({key: row.get(key, "") for key in TABLES[table]})
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
        except Exception:
            if tmp.exists():
                tmp.unlink()
            raise

    def _validate(self, table: str, rows: list[dict[str, str]]) -> None:
        columns = TABLES[table]
        pk = PRIMARY_KEYS[table]
        seen: set[str] = set()
        for row in rows:
            missing = [col for col in columns if col not in row]
            if missing:
                raise SystimoError("SCHEMA_INVALID", f"{table} missing {missing}")
            key = row[pk]
            if not key:
                raise SystimoError("PK_MISSING", f"{table}.{pk} empty")
            if key in seen:
                raise SystimoError("DUPLICATE_PK", f"{table}.{pk}={key}")
            seen.add(key)
            for (tbl, col), allowed in ENUMS.items():
                if tbl == table and row.get(col) and row[col] not in allowed:
                    raise SystimoError("BAD_ENUM", f"{table}.{col}={row[col]!r} not in {sorted(allowed)}")
        self._check_fk(table, rows)

    def _check_fk(self, table: str, rows: list[dict[str, str]]) -> None:
        for child, column, parent in FOREIGN_KEYS:
            if child != table:
                continue
            parent_rows = self.read(parent) if parent != table else rows
            parent_pk = PRIMARY_KEYS[parent]
            ids = {item[parent_pk] for item in parent_rows}
            for row in rows:
                value = row.get(column, "")
                if value and value not in ids:
                    raise SystimoError("BROKEN_FK", f"{table}.{column}={value} not in {parent}")

    def validate_all(self) -> None:
        for table in TABLES:
            self._validate(table, self.read(table))


def _normalize(table: str, row: dict[str, Any]) -> dict[str, str]:
    return {key: "" if row.get(key) is None else str(row.get(key, "")) for key in TABLES[table]}
