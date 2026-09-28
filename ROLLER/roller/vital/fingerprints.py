"""Source fingerprints. Pointers only. No crate move."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from roller.vital.models import utc_now
from roller.vital.store import (
    append_event,
    config_identity_path,
    deployment_identity_path,
    fingerprints_path,
    read_json,
    repo_root,
    write_json,
)
from roller.vital.versions import (
    BOT_ID,
    CONFIG_POINTER,
    ENGINE_POINTER,
    FACTORY,
    HOST_BINARY,
    HOST_CONFIG,
    SECRET_FETCH_POINTER,
    SERVICE_NAME,
    STRATEGY_POINTER,
    UNIT_POINTER,
)

FINGERPRINT_TARGETS = (
    ENGINE_POINTER,
    STRATEGY_POINTER,
    CONFIG_POINTER,
    UNIT_POINTER,
    SECRET_FETCH_POINTER,
)

SKIP_DIR_NAMES = {
    "__pycache__",
    ".git",
    "target",
    "node_modules",
    ".pytest_cache",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def fingerprint_path(rel: str, *, repo: Path | None = None) -> dict[str, Any]:
    root = repo or repo_root()
    path = root / rel
    if path.is_file():
        return {
            "path": rel,
            "kind": "file",
            "exists": True,
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
    if path.is_dir():
        files: list[dict[str, Any]] = []
        digest = hashlib.sha256()
        total = 0
        for child in sorted(path.rglob("*")):
            if not child.is_file():
                continue
            if any(part in SKIP_DIR_NAMES for part in child.parts):
                continue
            if child.suffix in {".pyc", ".rs.bk"}:
                continue
            rel_child = child.relative_to(root).as_posix()
            raw = child.read_bytes()
            digest.update(rel_child.encode("utf-8"))
            digest.update(b"\0")
            digest.update(raw)
            digest.update(b"\0")
            files.append({"path": rel_child, "sha256": sha256_bytes(raw), "bytes": len(raw)})
            total += len(raw)
        return {
            "path": rel,
            "kind": "tree",
            "exists": True,
            "sha256": digest.hexdigest(),
            "file_n": len(files),
            "bytes": total,
            "files": files,
        }
    return {"path": rel, "kind": "missing", "exists": False, "sha256": None}


def build_fingerprints(*, repo: Path | None = None) -> dict[str, Any]:
    targets = [fingerprint_path(rel, repo=repo) for rel in FINGERPRINT_TARGETS]
    return {
        "bot_id": BOT_ID,
        "recorded_at": utc_now(),
        "moved": False,
        "targets": targets,
        "pointers": {
            "engine": ENGINE_POINTER,
            "strategy": STRATEGY_POINTER,
            "config": CONFIG_POINTER,
            "unit": UNIT_POINTER,
            "secret_fetch": SECRET_FETCH_POINTER,
        },
    }


def config_identity() -> dict[str, Any]:
    return {
        "bot_id": BOT_ID,
        "pointer": CONFIG_POINTER,
        "host_path": HOST_CONFIG,
        "factory": dict(FACTORY),
        "live_gates": {
            "mode": "live",
            "live.enabled": True,
            "confirmation": "ENABLE_LIVE_TRADING",
            "note": "Triple gate stays in crates/core. Vital start does not arm live.",
        },
        "recorded_at": utc_now(),
    }


def deployment_identity() -> dict[str, Any]:
    return {
        "bot_id": BOT_ID,
        "unit": SERVICE_NAME,
        "pointer": UNIT_POINTER,
        "secret_fetch": SECRET_FETCH_POINTER,
        "host_binary": HOST_BINARY,
        "host_config": HOST_CONFIG,
        "recorded_at": utc_now(),
        "note": "Existing AWS unit. Vital does not invent a second engine.",
    }


def record_ownership(*, root: Path | None = None, repo: Path | None = None) -> dict[str, Any]:
    prints = build_fingerprints(repo=repo)
    existing = read_json(fingerprints_path(BOT_ID, root=root))
    if existing and existing.get("targets") == prints.get("targets"):
        return existing
    if existing and existing.get("targets") != prints.get("targets"):
        append_event(
            BOT_ID,
            {
                "kind": "fingerprint_recorded",
                "detail": "fingerprint mutation requires a new event; previous hashes retained in history",
                "previous_recorded_at": existing.get("recorded_at"),
            },
            root=root,
        )
    write_json(fingerprints_path(BOT_ID, root=root), prints)
    write_json(config_identity_path(BOT_ID, root=root), config_identity())
    write_json(deployment_identity_path(BOT_ID, root=root), deployment_identity())
    append_event(BOT_ID, {"kind": "fingerprint_recorded", "moved": False}, root=root)
    return prints


def load_fingerprints(*, root: Path | None = None) -> dict[str, Any] | None:
    return read_json(fingerprints_path(BOT_ID, root=root))
