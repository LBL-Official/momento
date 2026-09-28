"""Jump-owned workbench catalog. Metadata only. Not warehouse rows."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roller.jump.library import repo_root
from roller.jump.warehouse import CATALOG_SCHEMA

_ENV = "JUMP_WORKBENCH_ROOT"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def catalog_root(*, root: Path | None = None) -> Path:
    env = os.environ.get(_ENV)
    if env:
        return Path(env)
    return (root or repo_root()) / "research" / "jump" / "workbench"


def _empty() -> dict[str, Any]:
    return {
        "schema_version": CATALOG_SCHEMA,
        "queries": [],
        "views": [],
        "annotations": {},
        "relationship_layouts": {},
        "stats_cache": {},
        "updated_at": None,
    }


def load_catalog(*, root: Path | None = None) -> dict[str, Any]:
    path = catalog_root(root=root) / "catalog.json"
    if not path.is_file():
        return _empty()
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty()
    if not isinstance(body, dict):
        return _empty()
    body.setdefault("queries", [])
    body.setdefault("views", [])
    body.setdefault("annotations", {})
    body.setdefault("relationship_layouts", {})
    body.setdefault("stats_cache", {})
    return body


def save_catalog(body: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    dest_dir = catalog_root(root=root)
    dest_dir.mkdir(parents=True, exist_ok=True)
    payload = dict(body)
    payload["schema_version"] = CATALOG_SCHEMA
    payload["updated_at"] = _utc()
    dest = dest_dir / "catalog.json"
    tmp = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(dest_dir), delete=False)
    try:
        json.dump(payload, tmp, indent=2, default=str)
        tmp.write("\n")
        tmp.close()
        os.replace(tmp.name, dest)
    finally:
        if os.path.exists(tmp.name):
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
    return payload
