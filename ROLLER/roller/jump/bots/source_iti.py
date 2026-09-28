"""Load committed Jump A ITI folders. Fail closed. Not a live signal."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from roller.config import RollerConfig
from roller.jump.errors import JumpError


def _phase_b_root(cfg: RollerConfig | None = None) -> Path:
    from roller.superasi.debase.store import phase_b_root

    return phase_b_root(cfg)


def _metadata_path(folder: Path) -> Path:
    return folder / "metadata.json"


def _is_iti_commit(folder: Path) -> bool:
    meta = _metadata_path(folder)
    if not meta.is_file():
        return False
    try:
        rec = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return str(rec.get("artifact") or "") == "jump_iti"


def _candidate_iti_dirs(root: Path) -> list[Path]:
    """Phase B parents and their `{name}_ITI` children. Disk only. No host observe."""
    found: list[Path] = []
    try:
        parents = sorted(p for p in root.iterdir() if p.is_dir())
    except OSError:
        return found
    for parent in parents:
        if parent.name.endswith("_ITI"):
            found.append(parent)
        try:
            children = sorted(p for p in parent.iterdir() if p.is_dir() and p.name.endswith("_ITI"))
        except OSError:
            continue
        found.extend(children)
    return found


def list_iti_commits(cfg: RollerConfig | None = None) -> list[dict[str, Any]]:
    root = _phase_b_root(cfg)
    if not root.is_dir():
        return []
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for child in _candidate_iti_dirs(root):
        if not _is_iti_commit(child):
            continue
        try:
            rel = str(child.relative_to(root))
        except ValueError:
            continue
        if rel in seen:
            continue
        try:
            rec = load_iti_commit(rel, cfg=cfg, require_engine=False)
        except (JumpError, OSError, json.JSONDecodeError, TypeError, ValueError, KeyError):
            continue
        seen.add(rel)
        items.append(rec)
    items.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    return items


def load_iti_commit(folder: str, *, cfg: RollerConfig | None = None, require_engine: bool = True) -> dict[str, Any]:
    root = _phase_b_root(cfg)
    rel = str(folder or "").strip().strip("/")
    if not rel:
        raise JumpError("DATA_REQUIRED", "ITI strategy folder is required")
    dest = (root / rel).resolve()
    try:
        dest.relative_to(root.resolve())
    except ValueError as exc:
        raise JumpError("DATA_REQUIRED", "ITI folder is outside Phase B") from exc
    meta_path = _metadata_path(dest)
    if not meta_path.is_file():
        raise JumpError("DATA_REQUIRED", f"ITI metadata missing: {rel}")
    rec = json.loads(meta_path.read_text(encoding="utf-8"))
    if str(rec.get("artifact") or "") != "jump_iti":
        raise JumpError("DATA_REQUIRED", f"folder is not a Jump A ITI commit: {rel}")
    raw = meta_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    from roller.jump.bots.engine import build_research_engine

    loaded = {
        "folder": rel,
        "path": str(dest),
        "artifact": rec.get("artifact"),
        "iti_version": rec.get("iti_version"),
        "run_id": rec.get("run_id"),
        "slot_id": rec.get("slot_id"),
        "strategy_name": rec.get("strategy_name"),
        "source_folder": rec.get("source_folder"),
        "source_debase_result_id": rec.get("source_debase_result_id"),
        "lab_id": rec.get("lab_id"),
        "phase_a_result_id": rec.get("phase_a_result_id"),
        "phase_b_result_id": rec.get("phase_b_result_id"),
        "BASE_GRADE": rec.get("BASE_GRADE"),
        "DEBASE_GRADE": rec.get("DEBASE_GRADE"),
        "population": rec.get("population"),
        "entry_cents": rec.get("entry_cents"),
        "win_cents": rec.get("win_cents"),
        "loss_cents": rec.get("loss_cents"),
        "question": rec.get("question") if isinstance(rec.get("question"), dict) else None,
        "created_at": rec.get("created_at"),
        "metadata_sha256": digest,
        "strategy_fingerprint": _fingerprint(rec, digest),
        "live_execution": False,
        "iti_is_not_live_signal": True,
    }
    if loaded["question"] is None:
        parent_meta = dest.parent / "metadata.json"
        if parent_meta.is_file():
            try:
                parent = json.loads(parent_meta.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                parent = {}
            if isinstance(parent.get("question"), dict):
                loaded["question"] = parent["question"]
    try:
        loaded["engine"] = build_research_engine(loaded)
        loaded["sport"] = loaded["engine"]["sport"]
    except JumpError:
        if require_engine:
            raise
        loaded["engine"] = None
        loaded["sport"] = None
    return loaded


def _fingerprint(rec: dict[str, Any], digest: str) -> str:
    blob = json.dumps(
        {
            "run_id": rec.get("run_id"),
            "slot_id": rec.get("slot_id"),
            "iti_version": rec.get("iti_version"),
            "metadata_sha256": digest,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
