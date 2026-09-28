"""Vital disk library. Pointers, fingerprints, append-only events."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from roller.vital.errors import VitalError
from roller.vital.models import mlb_001_identity, unread_runtime, utc_now
from roller.vital.versions import BOT_ID

_ENV = "VITAL_ROOT"

TREE_DIRS = (
    "metadata",
    "source",
    "config",
    "deployment",
    "runtime",
    "logs",
    "events",
    "execution",
    "docs",
    "pointers",
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_vital_root() -> Path:
    env = os.environ.get(_ENV)
    if env:
        return Path(env)
    return repo_root() / "research" / "vital"


def bots_root(*, root: Path | None = None) -> Path:
    return (root or default_vital_root()) / "bots"


def commands_root(*, root: Path | None = None) -> Path:
    return (root or default_vital_root()) / "commands"


def bot_dir(bot_id: str, *, root: Path | None = None) -> Path:
    return bots_root(root=root) / bot_id


def _write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n"
    tmp_dir = Path(tempfile.mkdtemp(prefix="vital_", dir=str(path.parent)))
    tmp = tmp_dir / "payload.json"
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)
    tmp_dir.rmdir()


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def write_json(path: Path, obj: dict[str, Any]) -> dict[str, Any]:
    _write_json(path, obj)
    return obj


def ensure_bot_tree(bot_id: str, *, root: Path | None = None) -> Path:
    dest = bot_dir(bot_id, root=root)
    for name in TREE_DIRS:
        (dest / name).mkdir(parents=True, exist_ok=True)
    commands_root(root=root).mkdir(parents=True, exist_ok=True)
    return dest


def metadata_path(bot_id: str, *, root: Path | None = None) -> Path:
    return bot_dir(bot_id, root=root) / "metadata" / "bot.json"


def events_path(bot_id: str, *, root: Path | None = None) -> Path:
    return bot_dir(bot_id, root=root) / "events" / "events.jsonl"


def runtime_path(bot_id: str, which: str, *, root: Path | None = None) -> Path:
    return bot_dir(bot_id, root=root) / "runtime" / f"{which}.json"


def fingerprints_path(bot_id: str, *, root: Path | None = None) -> Path:
    return bot_dir(bot_id, root=root) / "source" / "fingerprints.json"


def config_identity_path(bot_id: str, *, root: Path | None = None) -> Path:
    return bot_dir(bot_id, root=root) / "config" / "identity.json"


def allocation_path(bot_id: str, *, root: Path | None = None) -> Path:
    return bot_dir(bot_id, root=root) / "config" / "allocation.json"


def allocation_history_path(bot_id: str, *, root: Path | None = None) -> Path:
    return bot_dir(bot_id, root=root) / "config" / "allocation.jsonl"


def limits_path(bot_id: str, *, root: Path | None = None) -> Path:
    return bot_dir(bot_id, root=root) / "config" / "limits.json"


def limits_history_path(bot_id: str, *, root: Path | None = None) -> Path:
    return bot_dir(bot_id, root=root) / "config" / "limits.jsonl"


def deployment_identity_path(bot_id: str, *, root: Path | None = None) -> Path:
    return bot_dir(bot_id, root=root) / "deployment" / "identity.json"


def execution_dir(bot_id: str, *, root: Path | None = None) -> Path:
    return bot_dir(bot_id, root=root) / "execution"


def pointers_path(bot_id: str, *, root: Path | None = None) -> Path:
    return bot_dir(bot_id, root=root) / "pointers" / "boundary.json"


def write_mlb_001_boundary(*, root: Path | None = None) -> dict[str, Any]:
    from roller.vital.mlb_001.boundary import TREE_OWNED, boundary_record

    ensure_bot_tree(BOT_ID, root=root)
    dest = bot_dir(BOT_ID, root=root)
    for name in TREE_OWNED:
        (dest / name).mkdir(parents=True, exist_ok=True)
    return write_json(pointers_path(BOT_ID, root=root), boundary_record())


def execution_fills_path(bot_id: str, *, root: Path | None = None) -> Path:
    return execution_dir(bot_id, root=root) / "fills.jsonl"


def execution_trades_path(bot_id: str, *, root: Path | None = None) -> Path:
    return execution_dir(bot_id, root=root) / "trades.jsonl"


def execution_observed_path(bot_id: str, *, root: Path | None = None) -> Path:
    return execution_dir(bot_id, root=root) / "observed.json"


def execution_settlements_path(bot_id: str, *, root: Path | None = None) -> Path:
    return execution_dir(bot_id, root=root) / "settlements.json"


def append_jsonl(path: Path, row: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(row)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, default=str) + "\n")
    return payload


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _fold_latest(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        token = str(row.get(key) or "").strip()
        if not token:
            continue
        prev = latest.get(token)
        if prev is None or int(row.get("rev") or 0) >= int(prev.get("rev") or 0):
            latest[token] = row
    return list(latest.values())


def load_execution_fills(bot_id: str, *, root: Path | None = None) -> list[dict[str, Any]]:
    return _fold_latest(load_jsonl(execution_fills_path(bot_id, root=root)), "fill_id")


def load_execution_trades(bot_id: str, *, root: Path | None = None) -> list[dict[str, Any]]:
    return _fold_latest(load_jsonl(execution_trades_path(bot_id, root=root)), "trade_id")


def ledger_exists(bot_id: str, *, root: Path | None = None) -> bool:
    fills = execution_fills_path(bot_id, root=root)
    trades = execution_trades_path(bot_id, root=root)
    return (fills.is_file() and fills.stat().st_size > 0) or (trades.is_file() and trades.stat().st_size > 0)


def append_event(bot_id: str, event: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    path = events_path(bot_id, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": utc_now(), **event}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")
    return row


def list_events(bot_id: str, *, root: Path | None = None, limit: int = 200) -> list[dict[str, Any]]:
    path = events_path(bot_id, root=root)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows[-limit:]


def load_bot(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    path = metadata_path(bot_id, root=root)
    payload = read_json(path)
    if payload is None:
        raise VitalError("BOT_NOT_FOUND", f"bot not found: {bot_id}")
    return payload


def save_bot(bot: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    bot_id = str(bot["bot_id"])
    bot["updated_at"] = utc_now()
    ensure_bot_tree(bot_id, root=root)
    write_json(metadata_path(bot_id, root=root), bot)
    return bot


def list_bot_ids(*, root: Path | None = None) -> list[str]:
    base = bots_root(root=root)
    if not base.is_dir():
        return []
    out: list[str] = []
    for child in sorted(base.iterdir()):
        if child.name.startswith("."):
            continue
        if child.is_dir() and (child / "metadata" / "bot.json").is_file():
            out.append(child.name)
    return out


def seed_mlb_001(*, root: Path | None = None) -> dict[str, Any]:
    path = metadata_path(BOT_ID, root=root)
    if path.is_file():
        rec = load_bot(BOT_ID, root=root)
        rec["bot_id"] = BOT_ID
        rec["kind"] = "grandfathered"
        rec["environment"] = "PRODUCTION"
        rec["engine_pointer"] = rec.get("engine_pointer") or "apps/trading-engine"
        rec["strategy_pointer"] = rec.get("strategy_pointer") or "strategies/mlb"
        write_mlb_001_boundary(root=root)
        return rec
    rec = mlb_001_identity()
    rec["created_at"] = "2026-08-01T00:00:00Z"
    rec["updated_at"] = utc_now()
    rec["status"] = "OBSERVATION_UNAVAILABLE"
    rec["health"] = "UNKNOWN"
    save_bot(rec, root=root)
    write_json(runtime_path(BOT_ID, "desired", root=root), unread_runtime()["desired"])
    write_json(runtime_path(BOT_ID, "observed", root=root), {"status": "OBSERVATION_UNAVAILABLE"})
    write_json(runtime_path(BOT_ID, "confirmed", root=root), {"status": "OBSERVATION_UNAVAILABLE"})
    append_event(
        BOT_ID,
        {"kind": "seeded", "status": rec["status"], "owner": "vital"},
        root=root,
    )
    write_mlb_001_boundary(root=root)
    return rec
