"""HTTP facades for SuperASI Phase B."""

from __future__ import annotations

from typing import Any

from roller.config import RollerConfig
from roller.superasi.base.store import list_base_results
from roller.superasi.debase.pipeline import run_debase
from roller.superasi.debase.store import get_debase_csv_bytes, list_debase_results, load_debase_inspect
from roller.superasi.debase.versions import DESK_PATHS, SUPERASI_DEBASE_VERSION
from roller.superasi.models import SuperasiError


def handle_sources(*, cfg: RollerConfig | None = None) -> dict[str, Any]:
    items = list_base_results(cfg)
    return {
        "results": items,
        "n": len(items),
        "phase": "A",
        "superasi_version": SUPERASI_DEBASE_VERSION,
    }


def handle_run(body: dict[str, Any] | None = None, *, cfg: RollerConfig | None = None) -> dict[str, Any]:
    body = body or {}
    result_id = str(body.get("result_id") or "").strip()
    if not result_id:
        raise SuperasiError("RESULT_NOT_FOUND", "result_id is required")
    paths = body.get("monte_carlo_paths")
    saved = run_debase(
        result_id=result_id,
        cfg=cfg,
        monte_carlo_paths=int(paths) if paths else DESK_PATHS,
    )
    return saved["inspect"]


def handle_results(*, cfg: RollerConfig | None = None) -> dict[str, Any]:
    items = list_debase_results(cfg)
    return {"results": items, "n": len(items), "phase": "B"}


def handle_result(result_id: str, *, cfg: RollerConfig | None = None) -> dict[str, Any]:
    rec = load_debase_inspect(result_id, cfg)
    if rec is None:
        raise SuperasiError("RESULT_NOT_FOUND", f"Phase B result not found: {result_id}")
    return rec


def handle_result_csv(
    result_id: str,
    *,
    which: str = "debase",
    cfg: RollerConfig | None = None,
) -> tuple[str, bytes]:
    found = get_debase_csv_bytes(result_id, which=which, cfg=cfg)
    if found is None:
        raise SuperasiError("RESULT_NOT_FOUND", f"Phase B CSV not found: {result_id}")
    return found
