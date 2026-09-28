"""Optional read-only Kalshi observe for MLB 001. Never submits. Never reads live tmpfs."""

from __future__ import annotations

import os
from typing import Any

from roller.vital.honesty import observation_unavailable

SKIP_ENV = "JUMP_SKIP_KALSHI"


def kalshi_observe_skipped() -> bool:
    return (os.environ.get(SKIP_ENV) or "").strip().lower() in {"1", "true", "yes"}


def kalshi_status() -> dict[str, Any]:
    """Disk book only. Does not call Kalshi."""
    if kalshi_observe_skipped():
        return {
            "layer": "kalshi_observe",
            "read_only": True,
            "submits": False,
            "status": "OBSERVATION_UNAVAILABLE",
            "detail": "Kalshi pull skipped",
            "observed_at": None,
            "post": "POST /vital/bots/{id}/kalshi/observe",
        }
    try:
        from roller.jump.catalog.store import load_kalshi_book
    except Exception:
        return {
            "layer": "kalshi_observe",
            "read_only": True,
            "submits": False,
            "status": "OBSERVATION_UNAVAILABLE",
            "detail": "kalshi book unread",
            "observed_at": None,
            "post": "POST /vital/bots/{id}/kalshi/observe",
        }
    book = load_kalshi_book()
    books = (book or {}).get("books") if isinstance(book, dict) else {}
    env_book = books.get("PRODUCTION") if isinstance(books, dict) else None
    demo_book = books.get("DEMO") if isinstance(books, dict) else None
    if not isinstance(env_book, dict) or not env_book.get("ok"):
        return {
            "layer": "kalshi_observe",
            "read_only": True,
            "submits": False,
            "status": "OBSERVATION_UNAVAILABLE",
            "detail": (env_book or {}).get("detail") if isinstance(env_book, dict) else "kalshi book unread",
            "observed_at": None,
            "post": "POST /vital/bots/{id}/kalshi/observe",
        }
    return {
        "layer": "kalshi_observe",
        "read_only": True,
        "submits": False,
        "status": "CONFIRMED",
        "detail": None,
        "observed_at": env_book.get("observed_at"),
        "fill_n": env_book.get("fill_n"),
        "position_n": env_book.get("position_n"),
        "source": env_book.get("source") or "kalshi_book",
        "demo_book": (
            "CONFIRMED"
            if isinstance(demo_book, dict) and demo_book.get("ok")
            else "OBSERVATION_UNAVAILABLE"
        ),
        "post": "POST /vital/bots/{id}/kalshi/observe",
    }


def kalshi_demo_status() -> dict[str, Any]:
    """Disk DEMO book only. Does not call Kalshi. Does not submit."""
    if kalshi_observe_skipped():
        return {
            "layer": "kalshi_observe",
            "read_only": True,
            "submits": False,
            "environment": "DEMO",
            "status": "OBSERVATION_UNAVAILABLE",
            "detail": "Kalshi pull skipped",
            "observed_at": None,
            "post": "POST /vital/bots/{id}/kalshi/observe",
        }
    try:
        from roller.jump.catalog.store import load_kalshi_book
    except Exception:
        return {
            "layer": "kalshi_observe",
            "read_only": True,
            "submits": False,
            "environment": "DEMO",
            "status": "OBSERVATION_UNAVAILABLE",
            "detail": "kalshi book unread",
            "observed_at": None,
            "post": "POST /vital/bots/{id}/kalshi/observe",
        }
    book = load_kalshi_book()
    books = (book or {}).get("books") if isinstance(book, dict) else {}
    demo_book = books.get("DEMO") if isinstance(books, dict) else None
    if not isinstance(demo_book, dict) or not demo_book.get("ok"):
        return {
            "layer": "kalshi_observe",
            "read_only": True,
            "submits": False,
            "environment": "DEMO",
            "status": "OBSERVATION_UNAVAILABLE",
            "detail": (demo_book or {}).get("detail") if isinstance(demo_book, dict) else "Kalshi Demo book unread",
            "observed_at": None,
            "post": "POST /vital/bots/{id}/kalshi/observe",
        }
    return {
        "layer": "kalshi_observe",
        "read_only": True,
        "submits": False,
        "environment": "DEMO",
        "status": "CONFIRMED",
        "detail": None,
        "observed_at": demo_book.get("observed_at"),
        "fill_n": demo_book.get("fill_n"),
        "position_n": demo_book.get("position_n"),
        "balance_cents": demo_book.get("current_cents"),
        "mlb_shard_cents": demo_book.get("mlb_shard_cents"),
        "exchange_index": demo_book.get("exchange_index"),
        "balance_breakdown": demo_book.get("balance_breakdown"),
        "source": demo_book.get("source") or "kalshi_book",
        "post": "POST /vital/bots/{id}/kalshi/observe",
    }


def observe_kalshi(*, environment: str = "PRODUCTION") -> dict[str, Any]:
    """Read-only Jump sync for one book. HTTP 200 is not a fill and not RUNNING."""
    env = str(environment or "PRODUCTION").strip().upper()
    if env not in {"DEMO", "PRODUCTION"}:
        return {
            "ok": False,
            "status": "OBSERVATION_UNAVAILABLE",
            "read_only": True,
            "submits": False,
            "environment": env,
            "detail": "environment must be DEMO or PRODUCTION",
            "http_200_not_running": True,
        }
    if kalshi_observe_skipped():
        return {
            "ok": False,
            "status": "OBSERVATION_UNAVAILABLE",
            "read_only": True,
            "submits": False,
            "environment": env,
            "detail": "Kalshi pull skipped",
            "http_200_not_running": True,
        }
    try:
        from roller.jump.catalog.connection import sync_kalshi
    except Exception:
        return {
            "ok": False,
            "status": "OBSERVATION_UNAVAILABLE",
            "read_only": True,
            "submits": False,
            "environment": env,
            "detail": "kalshi observe adapter unread",
            "http_200_not_running": True,
        }
    try:
        body = sync_kalshi(environments=(env,))
    except Exception:
        return {
            "ok": False,
            "status": "OBSERVATION_UNAVAILABLE",
            "read_only": True,
            "submits": False,
            "environment": env,
            "detail": "kalshi observe unread",
            "http_200_not_running": True,
            "live_execution": False,
        }
    env_detail = ((body.get("books") or {}).get(env) or {}) if isinstance(body.get("books"), dict) else {}
    return {
        "ok": bool(body.get("ok")),
        "status": body.get("status") or "OBSERVATION_UNAVAILABLE",
        "read_only": True,
        "submits": False,
        "mutating_sent": False,
        "environment": env,
        "added": body.get("added"),
        "books": body.get("books"),
        "detail": None if body.get("ok") else env_detail.get("detail") or body.get("detail") or "kalshi observe unread",
        "http_200_not_running": True,
        "live_execution": False,
    }


def observation_unavailable_kalshi(reason: str) -> dict[str, Any]:
    return observation_unavailable(reason)
