"""Disk library. Server-authoritative. Versions are immutable."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from roller.stax.models import StaxError, next_numeric_id, utc_now
from roller.stax.versions import DEFAULT_SCHEDULE, DEFAULT_TIMEZONE, LIVE_EXECUTION, STAX_SCHEMA


_ENV = "STAX_LIBRARY_ROOT"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_library_root() -> Path:
    env = os.environ.get(_ENV)
    if env:
        return Path(env)
    return repo_root() / "research" / "stax" / "library"


def stax_dir(stax_id: str, root: Path | None = None) -> Path:
    return (root or default_library_root()) / stax_id


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def list_stax_ids(root: Path | None = None) -> list[str]:
    base = root or default_library_root()
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if p.is_dir() and (p / "stax.json").is_file())


def next_stax_id(root: Path | None = None) -> str:
    return next_numeric_id("STAX", list_stax_ids(root))


def load_head(stax_id: str, *, root: Path | None = None) -> dict[str, Any]:
    path = stax_dir(stax_id, root) / "stax.json"
    if not path.is_file():
        raise StaxError("STAX_NOT_FOUND", f"unknown STAX {stax_id}")
    rec = _read_json(path)
    if not isinstance(rec, dict):
        raise StaxError("STAX_SCHEMA_INVALID", f"corrupt head {stax_id}")
    return rec


def write_head(head: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    dest = stax_dir(str(head["stax_id"]), root)
    dest.mkdir(parents=True, exist_ok=True)
    _write_json(dest / "stax.json", head)
    return head


def new_head(
    *,
    name: str,
    description: str = "",
    timezone: str = DEFAULT_TIMEZONE,
    root: Path | None = None,
) -> dict[str, Any]:
    stax_id = next_stax_id(root)
    now = utc_now()
    return {
        "stax_id": stax_id,
        "schema_version": STAX_SCHEMA,
        "name": name,
        "description": description,
        "created_at": now,
        "updated_at": now,
        "universe": None,
        "timezone": timezone or DEFAULT_TIMEZONE,
        "automation_enabled": False,
        "automation_schedule": DEFAULT_SCHEDULE,
        "latest_version": None,
        "latest_status": "PENDING",
        "last_run_at": None,
        "next_run_at": None,
        "working_members": [],
        "member_seq": 0,
        "live_execution": LIVE_EXECUTION,
    }


def version_dir(stax_id: str, version: str, *, root: Path | None = None) -> Path:
    return stax_dir(stax_id, root) / "versions" / f"v{version.lstrip('v')}"


def write_version(
    stax_id: str,
    record: dict[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    version = str(record["version"])
    dest = version_dir(stax_id, version, root=root)
    if dest.exists():
        raise StaxError("STAX_VERSION_IMMUTABLE", f"version v{version} already exists")
    dest.mkdir(parents=True, exist_ok=False)
    members = list(record.get("members") or [])
    results = list(record.get("results") or [])
    by_member = {r.get("member_id"): r for r in results}
    _write_json(dest / "version.json", {k: v for k, v in record.items() if k not in {"results", "members"}})
    _write_json(dest / "members.json", members)
    _write_json(dest / "overlap.json", record.get("overlap") or {})
    _write_json(dest / "provenance.json", record.get("provenance") or {})
    _write_json(dest / "execution.json", record.get("execution") or {})
    for member in members:
        mid = str(member["member_id"])
        slot = dest / "strategies" / mid
        slot.mkdir(parents=True, exist_ok=True)
        _write_json(slot / "member.json", member)
        result = by_member.get(mid) or {}
        _write_json(slot / "result.json", result)
    return record


def load_version(stax_id: str, version: str, *, root: Path | None = None) -> dict[str, Any]:
    dest = version_dir(stax_id, version, root=root)
    if not dest.is_dir():
        raise StaxError("STAX_VERSION_NOT_FOUND", f"unknown version v{version}")
    rec = _read_json(dest / "version.json")
    rec["members"] = _read_json(dest / "members.json")
    rec["overlap"] = _read_json(dest / "overlap.json") if (dest / "overlap.json").is_file() else {}
    rec["provenance"] = _read_json(dest / "provenance.json") if (dest / "provenance.json").is_file() else {}
    rec["execution"] = _read_json(dest / "execution.json") if (dest / "execution.json").is_file() else {}
    results = []
    for member in rec["members"]:
        path = dest / "strategies" / str(member["member_id"]) / "result.json"
        if path.is_file():
            results.append(_read_json(path))
    rec["results"] = results
    return rec


def list_versions(stax_id: str, *, root: Path | None = None) -> list[dict[str, Any]]:
    base = stax_dir(stax_id, root) / "versions"
    if not base.is_dir():
        return []
    items = []
    for child in sorted(base.iterdir()):
        if not child.is_dir() or not (child / "version.json").is_file():
            continue
        rec = _read_json(child / "version.json")
        items.append(
            {
                "version": rec.get("version"),
                "kind": rec.get("kind"),
                "created_at": rec.get("created_at"),
                "status": rec.get("status"),
                "strategy_count": rec.get("strategy_count"),
                "parent_version": rec.get("parent_version"),
            }
        )
    return items


def write_run(stax_id: str, run: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    dest = stax_dir(stax_id, root) / "runs" / f"{run['execution_id']}.json"
    _write_json(dest, run)
    return run


def list_stax(*, root: Path | None = None) -> list[dict[str, Any]]:
    items = []
    for stax_id in list_stax_ids(root):
        try:
            head = load_head(stax_id, root=root)
        except StaxError:
            continue
        uni = head.get("universe") if isinstance(head.get("universe"), dict) else {}
        items.append(
            {
                "stax_id": stax_id,
                "name": head.get("name"),
                "sport": uni.get("sport_family"),
                "league_set": uni.get("league_set"),
                "seasons": uni.get("seasons"),
                "date_from": uni.get("date_from"),
                "date_to": uni.get("date_to"),
                "strategies": len(head.get("working_members") or []),
                "latest_version": head.get("latest_version"),
                "automation": "ACTIVE" if head.get("automation_enabled") else "OFF",
                "last_run": head.get("last_run_at"),
                "status": head.get("latest_status"),
            }
        )
    return items
