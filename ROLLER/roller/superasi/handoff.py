"""Warehouse lab → SuperASI A → SuperASI B. Reuse existing results. Not ITI."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roller.config import RollerConfig
from roller.labs.store import get_lab
from roller.superasi.base.pipeline import run_base
from roller.superasi.base.store import list_base_results
from roller.superasi.base.versions import DESK_PATHS
from roller.superasi.debase.pipeline import run_debase
from roller.superasi.debase.store import list_debase_results, load_debase_inspect
from roller.superasi.library import repo_root
from roller.superasi.models import SuperasiError

_ENV = "SUPERASI_HANDOFF_ROOT"
_RESUME = frozenset({"PENDING", "RUNNING", "FAILED"})
_ACTIVE_LABS: set[str] = set()
_ACTIVE_LOCK = threading.Lock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def handoff_root(_cfg: RollerConfig | None = None) -> Path:
    env = os.environ.get(_ENV)
    if env:
        return Path(env)
    return repo_root() / "research" / "superasi" / "handoff"


def _newest(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    rows = sorted(
        rows,
        key=lambda row: (str(row.get("created_at") or ""), str(row.get("result_id") or "")),
        reverse=True,
    )
    return rows[0]


def latest_base_for_lab(lab_id: str, *, cfg: RollerConfig | None = None) -> dict[str, Any] | None:
    wanted = str(lab_id or "").strip()
    if not wanted:
        return None
    hits = [row for row in list_base_results(cfg) if str(row.get("source_lab_id") or "") == wanted]
    return _newest(hits)


def latest_debase_for_lab(lab_id: str, *, cfg: RollerConfig | None = None) -> dict[str, Any] | None:
    wanted = str(lab_id or "").strip()
    if not wanted:
        return None
    hits = [row for row in list_debase_results(cfg) if str(row.get("source_lab_id") or "") == wanted]
    return _newest(hits)


def _write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="sa_handoff_", dir=str(path.parent))) / "job.json"
    tmp.write_text(json.dumps(obj, indent=2, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    tmp.parent.rmdir()


def save_handoff(job: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    handoff_id = str(job["handoff_id"])
    job["updated_at"] = _utc_now()
    dest = (root or handoff_root()) / handoff_id / "job.json"
    _write_json(dest, job)
    return job


def load_handoff(handoff_id: str, *, root: Path | None = None) -> dict[str, Any]:
    wanted = str(handoff_id or "").strip()
    path = (root or handoff_root()) / wanted / "job.json"
    if not path.is_file():
        raise SuperasiError("HANDOFF_NOT_FOUND", f"handoff not found: {wanted}")
    return json.loads(path.read_text(encoding="utf-8"))


def list_handoffs(*, lab_id: str | None = None, root: Path | None = None) -> list[dict[str, Any]]:
    base = root or handoff_root()
    if not base.is_dir():
        return []
    items: list[dict[str, Any]] = []
    wanted = str(lab_id or "").strip()
    for path in base.glob("*/job.json"):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if wanted and str(rec.get("lab_id") or "") != wanted:
            continue
        items.append(rec)
    items.sort(key=lambda row: (str(row.get("updated_at") or ""), str(row.get("handoff_id") or "")), reverse=True)
    return items


def latest_handoff_for_lab(lab_id: str, *, root: Path | None = None) -> dict[str, Any] | None:
    items = list_handoffs(lab_id=lab_id, root=root)
    return items[0] if items else None


def _complete_reuse(
    *,
    lab_id: str,
    strategy_name: str | None,
    inspect: dict[str, Any],
    reused_base: bool,
    reused_debase: bool,
    ran_base: bool,
    ran_debase: bool,
    handoff_id: str | None = None,
) -> dict[str, Any]:
    return {
        "handoff_id": handoff_id,
        "lab_id": lab_id,
        "status": "COMPLETE",
        "phase": "final",
        "result_id": inspect.get("result_id"),
        "phase_a_result_id": inspect.get("phase_a_result_id"),
        "strategy_name": inspect.get("strategy_name") or strategy_name,
        "reused_base": reused_base,
        "reused_debase": reused_debase,
        "ran_base": ran_base,
        "ran_debase": ran_debase,
        "inspect": inspect,
        "error": None,
        "error_code": None,
    }


def public_handoff(job: dict[str, Any], *, cfg: RollerConfig | None = None) -> dict[str, Any]:
    result_id = str(job.get("result_id") or "")
    inspect = None
    if job.get("status") == "COMPLETE" and result_id:
        inspect = load_debase_inspect(result_id, cfg)
    return {
        "handoff_id": job.get("handoff_id"),
        "lab_id": job.get("lab_id"),
        "status": job.get("status"),
        "phase": job.get("phase") or "A",
        "result_id": result_id or None,
        "phase_a_result_id": job.get("phase_a_result_id"),
        "strategy_name": job.get("strategy_name"),
        "reused_base": bool(job.get("reused_base")),
        "reused_debase": bool(job.get("reused_debase")),
        "ran_base": bool(job.get("ran_base")),
        "ran_debase": bool(job.get("ran_debase")),
        "inspect": inspect,
        "error": job.get("error"),
        "error_code": job.get("error_code"),
    }


def advance_lab_to_final(
    lab_id: str,
    *,
    cfg: RollerConfig | None = None,
    reuse: bool = True,
    monte_carlo_paths: int | None = None,
    on_phase=None,
) -> dict[str, Any]:
    """Land a Labs CSV on SuperASI Final Results. Does not start ITI."""
    wanted = str(lab_id or "").strip()
    if not wanted:
        raise SuperasiError("LAB_NOT_FOUND", "lab_id is required")
    rec = get_lab(wanted, cfg)
    if rec is None:
        raise SuperasiError("LAB_NOT_FOUND", f"Labs CSV not found: {wanted}")
    paths = int(monte_carlo_paths) if monte_carlo_paths is not None else DESK_PATHS
    ran_base = False
    ran_debase = False
    reused_base = False
    reused_debase = False
    phase_a_id = ""

    if reuse:
        existing_b = latest_debase_for_lab(wanted, cfg=cfg)
        if existing_b and existing_b.get("result_id"):
            inspect = load_debase_inspect(str(existing_b["result_id"]), cfg)
            if inspect is not None:
                if on_phase:
                    on_phase("final")
                return _complete_reuse(
                    lab_id=wanted,
                    strategy_name=rec.get("strategy_name"),
                    inspect=inspect,
                    reused_base=True,
                    reused_debase=True,
                    ran_base=False,
                    ran_debase=False,
                )
        existing_a = latest_base_for_lab(wanted, cfg=cfg)
        if existing_a and existing_a.get("result_id"):
            phase_a_id = str(existing_a["result_id"])
            reused_base = True

    if not phase_a_id:
        if on_phase:
            on_phase("A")
        saved_a = run_base(lab_id=wanted, cfg=cfg, monte_carlo_paths=paths)
        inspect_a = saved_a.get("inspect") if isinstance(saved_a.get("inspect"), dict) else saved_a
        phase_a_id = str(inspect_a.get("result_id") or saved_a.get("result_id") or "")
        if not phase_a_id:
            raise SuperasiError("RESULT_NOT_FOUND", "SuperASI A did not return a result_id")
        ran_base = True

    if on_phase:
        on_phase("B")
    saved_b = run_debase(result_id=phase_a_id, cfg=cfg, monte_carlo_paths=paths)
    inspect_b = saved_b.get("inspect") if isinstance(saved_b.get("inspect"), dict) else saved_b
    result_id = str(inspect_b.get("result_id") or saved_b.get("result_id") or "")
    if not result_id:
        raise SuperasiError("RESULT_NOT_FOUND", "SuperASI B did not return a result_id")
    ran_debase = True
    inspect = load_debase_inspect(result_id, cfg) or inspect_b
    return _complete_reuse(
        lab_id=wanted,
        strategy_name=rec.get("strategy_name"),
        inspect=inspect,
        reused_base=reused_base,
        reused_debase=reused_debase,
        ran_base=ran_base,
        ran_debase=ran_debase,
    )


def _run_job(
    handoff_id: str,
    *,
    root: Path | None,
    cfg: RollerConfig | None,
    reuse: bool,
    monte_carlo_paths: int | None,
) -> dict[str, Any]:
    job = load_handoff(handoff_id, root=root)
    job["status"] = "RUNNING"
    save_handoff(job, root=root)

    def on_phase(phase: str) -> None:
        latest = load_handoff(handoff_id, root=root)
        latest["phase"] = phase
        latest["status"] = "RUNNING"
        save_handoff(latest, root=root)

    try:
        out = advance_lab_to_final(
            str(job["lab_id"]),
            cfg=cfg,
            reuse=reuse,
            monte_carlo_paths=monte_carlo_paths,
            on_phase=on_phase,
        )
        latest = load_handoff(handoff_id, root=root)
        latest.update(
            {
                "status": "COMPLETE",
                "phase": "final",
                "result_id": out.get("result_id"),
                "phase_a_result_id": out.get("phase_a_result_id"),
                "strategy_name": out.get("strategy_name") or latest.get("strategy_name"),
                "reused_base": out.get("reused_base"),
                "reused_debase": out.get("reused_debase"),
                "ran_base": out.get("ran_base"),
                "ran_debase": out.get("ran_debase"),
                "error": None,
                "error_code": None,
            }
        )
        save_handoff(latest, root=root)
        return public_handoff(latest, cfg=cfg)
    except SuperasiError as exc:
        latest = load_handoff(handoff_id, root=root)
        latest["status"] = "FAILED"
        latest["error"] = exc.message
        latest["error_code"] = exc.code
        save_handoff(latest, root=root)
        raise
    except Exception as exc:
        latest = load_handoff(handoff_id, root=root)
        latest["status"] = "FAILED"
        latest["error"] = str(exc)
        latest["error_code"] = "HANDOFF_FAILED"
        save_handoff(latest, root=root)
        raise SuperasiError("HANDOFF_FAILED", str(exc)) from exc


def start_handoff(
    lab_id: str,
    *,
    cfg: RollerConfig | None = None,
    reuse: bool = True,
    background: bool = True,
    monte_carlo_paths: int | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    wanted = str(lab_id or "").strip()
    if not wanted:
        raise SuperasiError("LAB_NOT_FOUND", "lab_id is required")
    rec = get_lab(wanted, cfg)
    if rec is None:
        raise SuperasiError("LAB_NOT_FOUND", f"Labs CSV not found: {wanted}")
    dest = root or handoff_root()
    if reuse:
        existing_b = latest_debase_for_lab(wanted, cfg=cfg)
        if existing_b and existing_b.get("result_id"):
            inspect = load_debase_inspect(str(existing_b["result_id"]), cfg)
            if inspect is not None:
                return _complete_reuse(
                    lab_id=wanted,
                    strategy_name=rec.get("strategy_name"),
                    inspect=inspect,
                    reused_base=True,
                    reused_debase=True,
                    ran_base=False,
                    ran_debase=False,
                )

    with _ACTIVE_LOCK:
        latest = latest_handoff_for_lab(wanted, root=dest)
        if wanted in _ACTIVE_LABS and latest:
            return public_handoff(latest, cfg=cfg)
        if latest and str(latest.get("status") or "") in _RESUME:
            job = load_handoff(str(latest["handoff_id"]), root=dest)
            job["status"] = "PENDING" if job.get("status") == "FAILED" else job.get("status")
            job["error"] = None
            job["error_code"] = None
            save_handoff(job, root=dest)
        else:
            job = {
                "handoff_id": uuid.uuid4().hex,
                "lab_id": wanted,
                "status": "PENDING",
                "phase": "A" if latest_base_for_lab(wanted, cfg=cfg) is None else "B",
                "result_id": None,
                "phase_a_result_id": None,
                "strategy_name": rec.get("strategy_name"),
                "reused_base": False,
                "reused_debase": False,
                "ran_base": False,
                "ran_debase": False,
                "error": None,
                "error_code": None,
                "created_at": _utc_now(),
            }
            save_handoff(job, root=dest)
        _ACTIVE_LABS.add(wanted)
        handoff_id = str(job["handoff_id"])

    kwargs = {
        "handoff_id": handoff_id,
        "root": dest,
        "cfg": cfg,
        "reuse": reuse,
        "monte_carlo_paths": monte_carlo_paths,
    }

    def _guarded(**kw: Any) -> dict[str, Any]:
        try:
            return _run_job(**kw)
        except SuperasiError:
            return public_handoff(load_handoff(str(kw["handoff_id"]), root=kw.get("root")), cfg=kw.get("cfg"))
        finally:
            with _ACTIVE_LOCK:
                _ACTIVE_LABS.discard(wanted)

    if background:
        thread = threading.Thread(
            target=_guarded,
            kwargs=kwargs,
            daemon=True,
            name=f"superasi-handoff-{handoff_id[:8]}",
        )
        thread.start()
        return public_handoff(load_handoff(handoff_id, root=dest), cfg=cfg)
    try:
        return _guarded(**kwargs)
    except SuperasiError:
        return public_handoff(load_handoff(handoff_id, root=dest), cfg=cfg)


def handle_handoff(body: dict[str, Any] | None = None, *, cfg: RollerConfig | None = None) -> dict[str, Any]:
    body = body or {}
    lab_id = str(body.get("lab_id") or "").strip()
    reuse = True if body.get("reuse") is None else bool(body.get("reuse"))
    paths = body.get("monte_carlo_paths")
    wait = bool(body.get("wait"))
    return start_handoff(
        lab_id,
        cfg=cfg,
        reuse=reuse,
        background=not wait,
        monte_carlo_paths=int(paths) if paths else None,
    )


def handle_get_handoff(handoff_id: str, *, cfg: RollerConfig | None = None) -> dict[str, Any]:
    return public_handoff(load_handoff(handoff_id), cfg=cfg)


def handle_latest_handoff(lab_id: str, *, cfg: RollerConfig | None = None) -> dict[str, Any]:
    wanted = str(lab_id or "").strip()
    if not wanted:
        raise SuperasiError("LAB_NOT_FOUND", "lab_id is required")
    if latest_debase_for_lab(wanted, cfg=cfg):
        return start_handoff(wanted, cfg=cfg, reuse=True, background=True)
    latest = latest_handoff_for_lab(wanted)
    if latest is None:
        raise SuperasiError("HANDOFF_NOT_FOUND", f"no handoff for lab {wanted}")
    return public_handoff(latest, cfg=cfg)
