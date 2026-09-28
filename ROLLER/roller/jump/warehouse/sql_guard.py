"""Reject mutating / unsafe SQL. Canonical warehouses are SELECT-only."""

from __future__ import annotations

import re

from roller.jump.errors import JumpError

_ALLOWED_HEAD = ("SELECT", "WITH", "DESCRIBE", "DESC", "EXPLAIN", "SHOW", "FROM")
_BLOCKED = (
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "COPY",
    "ATTACH",
    "DETACH",
    "INSTALL",
    "LOAD",
    "CALL",
    "PRAGMA",
    "VACUUM",
    "MERGE",
    "REPLACE",
    "GRANT",
    "REVOKE",
    "EXPORT",
    "IMPORT",
    "PIVOT",
    "UNPIVOT",
    "SET",
    "RESET",
    "USE",
    "CHECKPOINT",
    "READ_CSV",
    "READ_JSON",
    "READ_PARQUET",
    "READ_BLOB",
    "GLOB",
)
_COMMENT = re.compile(r"/\*.*?\*/|--[^\n]*", re.DOTALL)
_WORD = re.compile(r"[A-Za-z_]+")


def _strip(sql: str) -> str:
    return _COMMENT.sub(" ", sql or "").strip()


def assert_readonly_sql(sql: str) -> str:
    text = _strip(sql)
    if not text:
        raise JumpError("QUERY_REJECTED", "empty SQL")
    statements = [part.strip() for part in text.split(";") if part.strip()]
    if len(statements) != 1:
        raise JumpError("QUERY_REJECTED", "exactly one SQL statement is allowed")
    stmt = statements[0]
    upper = stmt.upper()
    words = _WORD.findall(upper)
    if not words:
        raise JumpError("QUERY_REJECTED", "SQL has no statement keyword")
    head = words[0]
    if head == "EXPLAIN" and len(words) > 1 and words[1] in {"ANALYZE", "QUERY"}:
        rest = words[2] if len(words) > 2 and words[1] == "QUERY" else words[1]
        if rest not in {"SELECT", "WITH", "DESCRIBE", "DESC", "PLAN"}:
            raise JumpError("QUERY_REJECTED", "EXPLAIN is allowed only for SELECT")
    elif head not in _ALLOWED_HEAD:
        raise JumpError("QUERY_REJECTED", f"{head} is not allowed on a read-only warehouse")
    for token in words:
        if token in _BLOCKED:
            raise JumpError("QUERY_REJECTED", f"{token} is not allowed on a read-only warehouse")
    return stmt
