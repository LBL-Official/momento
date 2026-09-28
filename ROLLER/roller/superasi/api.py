"""SuperASI HTTP handlers. Mounted on the ROLLER terminal API."""

from __future__ import annotations

from typing import Any

from roller.superasi.decompose import decompose
from roller.superasi.import_source import import_from_roller
from roller.superasi.library import list_packages, load_package
from roller.superasi.models import SuperasiError
from roller.superasi.seed import SEED_ID, build_seed
from roller.superasi.versions import (
    DEFAULT_ADVERSE_P,
    DEFAULT_FEE,
    DEFAULT_FILL,
)


def handle_import(body: dict[str, Any]) -> dict[str, Any]:
    return import_from_roller(body)


def handle_list(*, root=None) -> dict[str, Any]:
    items = list_packages(root=root)
    return {"packages": items, "n": len(items)}


def handle_get(package_id: str, *, root=None) -> dict[str, Any]:
    loaded = load_package(package_id, root=root)
    pkg = loaded["package"]
    return {
        "package": pkg,
        "population_n": pkg.get("population_n"),
        "trades_n": len(loaded["trades"]),
        "path_windows_n": len(loaded["path_windows"]),
        "decomp": loaded["decomp"],
        "trades": loaded["trades"],
        "path_windows": loaded["path_windows"],
        "sample_trades": loaded["trades"][:25],
        "path_window_offsets": _offset_preview(loaded["path_windows"]),
    }


def handle_decompose(package_id: str, body: dict[str, Any] | None = None, *, root=None) -> dict[str, Any]:
    body = body or {}
    return decompose(
        package_id,
        fill_algorithm=str(body.get("fill_algorithm") or DEFAULT_FILL),
        fee_scenario=str(body.get("fee_scenario") or DEFAULT_FEE),
        adverse_p=str(body.get("adverse_p") or DEFAULT_ADVERSE_P),
        root=root,
    )


def handle_seed(*, root=None) -> dict[str, Any]:
    written = build_seed(root=root)
    loaded = load_package(SEED_ID, root=root)
    return {
        "package_id": SEED_ID,
        "source": "seed_asked_six",
        "population_n": loaded["package"]["population_n"],
        "locks": written.get("locks"),
        "message": "ASKED-SIX SEED MATERIALIZED",
        "path": written.get("path"),
    }


def error_payload(exc: SuperasiError, status_code: int = 400) -> tuple[int, dict[str, Any]]:
    return status_code, exc.as_dict()


def _offset_preview(windows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for w in windows:
        key = str(w.get("offset"))
        counts[key] = counts.get(key, 0) + 1
    return counts
