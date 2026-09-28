"""HTTP facades for SuperASI Phase A."""

from __future__ import annotations

from typing import Any

from roller.config import RollerConfig
from roller.labs.store import get_lab, list_labs
from roller.superasi.base.pipeline import run_base
from roller.superasi.base.store import get_base_csv_bytes, list_base_results, load_base_inspect
from roller.superasi.base.versions import DESK_PATHS, SUPERASI_BASE_VERSION
from roller.superasi.models import SuperasiError


def handle_sources(*, folder: str | None = None, cfg: RollerConfig | None = None) -> dict[str, Any]:
    items = list_labs(cfg, folder=folder)
    folders = sorted({str(i.get("folder") or "") for i in items if i.get("folder")})
    return {
        "labs": items,
        "n": len(items),
        "folders": folders,
        "superasi_version": SUPERASI_BASE_VERSION,
    }


def handle_source(lab_id: str, *, cfg: RollerConfig | None = None) -> dict[str, Any]:
    rec = get_lab(lab_id, cfg)
    if rec is None:
        raise SuperasiError("LAB_NOT_FOUND", f"Labs CSV not found: {lab_id}")
    return rec


def handle_run(body: dict[str, Any] | None = None, *, cfg: RollerConfig | None = None) -> dict[str, Any]:
    body = body or {}
    lab_id = str(body.get("lab_id") or "").strip()
    if not lab_id:
        raise SuperasiError("LAB_NOT_FOUND", "lab_id is required")
    paths = body.get("monte_carlo_paths")
    saved = run_base(
        lab_id=lab_id,
        cfg=cfg,
        monte_carlo_paths=int(paths) if paths else DESK_PATHS,
    )
    return saved["inspect"]


def handle_results(*, cfg: RollerConfig | None = None) -> dict[str, Any]:
    items = list_base_results(cfg)
    return {"results": items, "n": len(items), "phase": "A"}


def handle_result(result_id: str, *, cfg: RollerConfig | None = None) -> dict[str, Any]:
    rec = load_base_inspect(result_id, cfg)
    if rec is None:
        raise SuperasiError("RESULT_NOT_FOUND", f"Phase A result not found: {result_id}")
    return rec


def handle_result_csv(
    result_id: str,
    *,
    which: str = "base",
    cfg: RollerConfig | None = None,
) -> tuple[str, bytes]:
    found = get_base_csv_bytes(result_id, which=which, cfg=cfg)
    if found is None:
        raise SuperasiError("RESULT_NOT_FOUND", f"Phase A CSV not found: {result_id}")
    return found
