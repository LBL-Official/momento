"""Optional query-result cache. Semantic key only. Never cache['FIRST80']."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from roller.research_query.hashing import CODE_VERSION, sha256_hex
from roller.research_query.models import OPERATION_SEMANTICS_VERSION

_mem: dict[str, dict[str, Any]] = {}


def result_key(
    *,
    question_hash: str,
    dataset_version: str,
    index_version: str,
    code_version: str = CODE_VERSION,
    operation_semantics_version: str = OPERATION_SEMANTICS_VERSION,
) -> str:
    raw = "|".join(
        [
            question_hash,
            dataset_version,
            index_version,
            code_version,
            operation_semantics_version,
        ]
    )
    return sha256_hex(raw)


def enabled() -> bool:
    return os.environ.get("ROLLER_QUERY_RESULT_CACHE", "0") in {"1", "true", "True"}


def disk_dir() -> Path | None:
    raw = os.environ.get("ROLLER_QUERY_RESULT_CACHE_DIR")
    if raw:
        return Path(raw)
    return None


def get(key: str) -> dict[str, Any] | None:
    if not enabled():
        return None
    hit = _mem.get(key)
    if hit is not None:
        return hit
    root = disk_dir()
    if root is None:
        return None
    path = root / f"{key}.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    _mem[key] = payload
    return payload


def put(key: str, envelope: dict[str, Any]) -> None:
    if not enabled():
        return
    if (envelope.get("compile") or {}).get("execution_path") == "frozen_reference":
        return
    if envelope.get("provenance", {}).get("path") == "warehouse_frozen_v1":
        return
    _mem[key] = envelope
    root = disk_dir()
    if root is None:
        return
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{key}.json").write_text(json.dumps(envelope), encoding="utf-8")


def clear() -> None:
    _mem.clear()
