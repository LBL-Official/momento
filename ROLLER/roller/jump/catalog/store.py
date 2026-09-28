"""Append-only catalog on disk. Not inside job.json."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roller.jump.library import repo_root

_ENV = "JUMP_CATALOG_ROOT"


def default_catalog_root() -> Path:
    env = os.environ.get(_ENV)
    if env:
        return Path(env)
    return repo_root() / "research" / "jump" / "catalog"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def origin_path(*, root: Path | None = None) -> Path:
    return (root or default_catalog_root()) / "origin.json"


def trades_path(*, root: Path | None = None) -> Path:
    return (root or default_catalog_root()) / "trades.jsonl"


def analysis_path(*, root: Path | None = None) -> Path:
    return (root or default_catalog_root()) / "analysis.json"


def bankroll_path(*, root: Path | None = None) -> Path:
    return (root or default_catalog_root()) / "bankroll.json"


def kalshi_book_path(*, root: Path | None = None) -> Path:
    return (root or default_catalog_root()) / "kalshi_book.json"


def bankroll_history_path(*, root: Path | None = None) -> Path:
    return (root or default_catalog_root()) / "bankroll_history.jsonl"


def chart_path(jump_trade_id: str, *, root: Path | None = None) -> Path:
    return (root or default_catalog_root()) / "charts" / f"{jump_trade_id}.svg"


def load_origin(*, root: Path | None = None) -> dict[str, Any] | None:
    path = origin_path(root=root)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def persist_origin(origin: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    path = origin_path(root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_origin(root=root)
    if existing and existing.get("bot_one_first_fill_ts"):
        stored = str(existing["bot_one_first_fill_ts"])
        incoming = str(origin.get("bot_one_first_fill_ts") or "")
        if incoming and incoming < stored:
            existing = dict(existing)
            existing["bot_one_first_fill_ts"] = incoming
            existing["updated_at"] = _utc_now()
            path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return existing
        return existing
    row = dict(origin)
    row.setdefault("set_at", _utc_now())
    path.write_text(json.dumps(row, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return row


def load_trades(*, root: Path | None = None) -> list[dict[str, Any]]:
    path = trades_path(root=root)
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("jump_trade_id"):
            out.append(row)
    return out


def existing_ids(*, root: Path | None = None) -> set[str]:
    return {str(row["jump_trade_id"]) for row in load_trades(root=root)}


def append_trades(rows: list[dict[str, Any]], *, root: Path | None = None) -> int:
    if not rows:
        return 0
    path = trades_path(root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    known = existing_ids(root=root)
    added = 0
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            tid = str(row.get("jump_trade_id") or "")
            if not tid or tid in known:
                continue
            handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")
            known.add(tid)
            added += 1
    return added


def load_bankroll(*, root: Path | None = None) -> dict[str, Any] | None:
    path = bankroll_path(root=root)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def persist_bankroll(payload: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    path = bankroll_path(root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_bankroll(root=root) or {}
    merged = dict(existing)
    incoming_books = payload.get("books") if isinstance(payload.get("books"), dict) else {}
    books = dict(existing.get("books") or {}) if isinstance(existing.get("books"), dict) else {}
    for key, value in incoming_books.items():
        if isinstance(value, dict):
            books[str(key).upper()] = value
    for key, value in payload.items():
        if key == "books":
            continue
        merged[key] = value
    merged["books"] = books
    merged["updated_at"] = _utc_now()
    path.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return merged


def write_analysis(payload: dict[str, Any], *, root: Path | None = None) -> None:
    path = analysis_path(root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def load_analysis(*, root: Path | None = None) -> dict[str, Any] | None:
    path = analysis_path(root=root)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def write_chart(jump_trade_id: str, svg: str, *, root: Path | None = None) -> None:
    path = chart_path(jump_trade_id, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg, encoding="utf-8")


def load_kalshi_book(*, root: Path | None = None) -> dict[str, Any] | None:
    path = kalshi_book_path(root=root)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def persist_kalshi_book(payload: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    path = kalshi_book_path(root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_kalshi_book(root=root) or {}
    merged = dict(existing)
    incoming_books = payload.get("books") if isinstance(payload.get("books"), dict) else {}
    books = dict(existing.get("books") or {}) if isinstance(existing.get("books"), dict) else {}
    for key, value in incoming_books.items():
        if isinstance(value, dict):
            books[str(key).upper()] = value
    for key, value in payload.items():
        if key == "books":
            continue
        merged[key] = value
    merged["books"] = books
    merged["updated_at"] = _utc_now()
    path.write_text(json.dumps(merged, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return merged


def load_bankroll_history(*, root: Path | None = None) -> list[dict[str, Any]]:
    path = bankroll_history_path(root=root)
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def append_bankroll_history(row: dict[str, Any], *, root: Path | None = None) -> None:
    path = bankroll_history_path(root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_bankroll_history(root=root)
    if existing:
        last = existing[-1]
        if (
            last.get("environment") == row.get("environment")
            and last.get("current_cents") == row.get("current_cents")
            and last.get("observed_at") == row.get("observed_at")
        ):
            return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def load_chart(jump_trade_id: str, *, root: Path | None = None) -> str | None:
    path = chart_path(jump_trade_id, root=root)
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return text if text.strip().startswith("<svg") else None
