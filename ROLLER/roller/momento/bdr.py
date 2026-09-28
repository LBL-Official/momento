"""BDR write-up catalog. Hedging Analysis frontend. Not live."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from roller.momento.registry import LIVE_EXECUTION
from roller.paths import find_root, momento_root

SCHEMA = "bdr_catalog_v1"
SYSTEM_ID = "hedging_analysis"


class BdrError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _repo() -> Path:
    return momento_root(find_root())


def catalog_path() -> Path:
    return _repo() / "research" / "bdr" / "CATALOG.json"


def _load_catalog() -> dict[str, Any]:
    raw = json.loads(catalog_path().read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema") != SCHEMA:
        raise BdrError("BDR_CATALOG_INVALID", "BDR catalog schema mismatch")
    if raw.get("live_execution") is not False:
        raise BdrError("BDR_CATALOG_INVALID", "BDR catalog must set live_execution false")
    documents = raw.get("documents")
    if not isinstance(documents, list) or not documents:
        raise BdrError("BDR_CATALOG_INVALID", "BDR catalog has no documents")
    return raw


def _resolve_doc(rel: str) -> Path:
    if not rel or rel.startswith("/") or ".." in Path(rel).parts:
        raise BdrError("BDR_PATH_FORBIDDEN", "document path rejected")
    path = (_repo() / rel).resolve()
    try:
        path.relative_to(_repo())
    except ValueError as exc:
        raise BdrError("BDR_PATH_FORBIDDEN", "document path escaped repo") from exc
    if not path.is_file():
        raise BdrError("BDR_DOCUMENT_MISSING", f"missing {rel}")
    return path


def _document_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "slug": row["slug"],
        "number": row["number"],
        "title": row["title"],
        "kind": row["kind"],
        "path": row["path"],
        "blurb": row.get("blurb", ""),
        "url": f"/momento/bdr/{row['slug']}",
        "hash": f"#/bdr/{row['slug']}",
    }


def handle_catalog() -> dict[str, Any]:
    raw = _load_catalog()
    return {
        "schema": SCHEMA,
        "live_execution": LIVE_EXECUTION,
        "system_id": SYSTEM_ID,
        "title": raw["title"],
        "subtitle": raw.get("subtitle", ""),
        "note": raw.get("note", ""),
        "documents": [_document_card(row) for row in raw["documents"]],
        "related": list(raw.get("related") or []),
        "candle_path_not_fill": True,
    }


def handle_document(slug: str) -> dict[str, Any]:
    raw = _load_catalog()
    match = next((row for row in raw["documents"] if row.get("slug") == slug), None)
    if match is None:
        raise BdrError("UNKNOWN_DOCUMENT", f"unknown BDR document {slug}")
    text = _resolve_doc(str(match["path"])).read_text(encoding="utf-8")
    card = _document_card(match)
    return {
        "schema": SCHEMA,
        "live_execution": LIVE_EXECUTION,
        "system_id": SYSTEM_ID,
        "candle_path_not_fill": True,
        **card,
        "markdown": text,
    }
