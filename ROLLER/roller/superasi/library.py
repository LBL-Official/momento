"""Disk library. Not localStorage. Atomic writes."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from roller.superasi.models import SuperasiError
from roller.superasi.package import sha256_hex
from roller.superasi.validation import validate_package
from roller.superasi.versions import PACKAGE_SCHEMA

_ENV = "SUPERASI_LIBRARY_ROOT"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_library_root() -> Path:
    env = os.environ.get(_ENV)
    if env:
        return Path(env)
    return repo_root() / "research" / "superasi" / "library"


def package_dir(package_id: str, root: Path | None = None) -> Path:
    return (root or default_library_root()) / package_id


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n", encoding="utf-8")


def write_package(
    pkg: dict[str, Any],
    trades: list[dict[str, Any]],
    windows: list[dict[str, Any]] | None = None,
    decomp: dict[str, Any] | None = None,
    *,
    root: Path | None = None,
    replace: bool = False,
) -> dict[str, Any]:
    validate_package(pkg, trades)
    dest = package_dir(str(pkg["package_id"]), root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    windows = list(windows or [])
    pkg = dict(pkg)
    pkg["checksums"] = dict(pkg.get("checksums") or {})
    pkg["checksums"]["trades"] = sha256_hex(trades)
    pkg["checksums"]["path_windows"] = sha256_hex(windows)
    if decomp is not None:
        pkg["checksums"]["decomp"] = sha256_hex(decomp)
    tmp = Path(tempfile.mkdtemp(prefix="superasi_", dir=str(dest.parent)))
    try:
        _write_json(tmp / "package.json", pkg)
        _write_json(tmp / "trades.json", trades)
        _write_json(tmp / "path_windows.json", windows)
        if decomp is not None:
            _write_json(tmp / "decomp.json", decomp)
        validate_package(json.loads((tmp / "package.json").read_text()), trades)
        if dest.exists():
            if not replace:
                raise SuperasiError("PACKAGE_SCHEMA_INVALID", f"package already exists: {dest}")
            bak = dest.with_name(dest.name + ".bak")
            if bak.exists():
                for child in bak.iterdir():
                    child.unlink()
                bak.rmdir()
            os.replace(dest, bak)
            os.replace(tmp, dest)
            for child in bak.iterdir():
                child.unlink()
            bak.rmdir()
        else:
            os.replace(tmp, dest)
    except Exception:
        if tmp.exists() and tmp.is_dir() and not dest.exists():
            for child in tmp.iterdir():
                child.unlink(missing_ok=True)
            tmp.rmdir()
        raise
    return {"package_id": pkg["package_id"], "path": str(dest), "schema_version": PACKAGE_SCHEMA}


def write_decomp(package_id: str, decomp: dict[str, Any], *, root: Path | None = None) -> None:
    dest = package_dir(package_id, root)
    if not dest.is_dir():
        raise SuperasiError("PACKAGE_SCHEMA_INVALID", f"unknown package {package_id}")
    pkg = json.loads((dest / "package.json").read_text(encoding="utf-8"))
    trades = json.loads((dest / "trades.json").read_text(encoding="utf-8"))
    validate_package(pkg, trades)
    tmp = dest / "decomp.json.tmp"
    tmp.write_text(json.dumps(decomp, indent=2, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, dest / "decomp.json")
    pkg["checksums"] = dict(pkg.get("checksums") or {})
    pkg["checksums"]["decomp"] = sha256_hex(decomp)
    (dest / "package.json").write_text(json.dumps(pkg, indent=2, default=str) + "\n", encoding="utf-8")


def load_package(package_id: str, *, root: Path | None = None) -> dict[str, Any]:
    dest = package_dir(package_id, root)
    if not dest.is_dir():
        raise SuperasiError("PACKAGE_SCHEMA_INVALID", f"unknown package {package_id}")
    pkg = json.loads((dest / "package.json").read_text(encoding="utf-8"))
    trades = json.loads((dest / "trades.json").read_text(encoding="utf-8"))
    windows: list[dict[str, Any]] = []
    if (dest / "path_windows.json").is_file():
        windows = json.loads((dest / "path_windows.json").read_text(encoding="utf-8"))
    decomp = None
    if (dest / "decomp.json").is_file():
        decomp = json.loads((dest / "decomp.json").read_text(encoding="utf-8"))
    validate_package(pkg, trades)
    return {"package": pkg, "trades": trades, "path_windows": windows, "decomp": decomp}


def list_packages(*, root: Path | None = None) -> list[dict[str, Any]]:
    base = root or default_library_root()
    if not base.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for child in sorted(base.iterdir()):
        if not child.is_dir() or not (child / "package.json").is_file():
            continue
        try:
            loaded = load_package(child.name, root=base)
        except SuperasiError:
            continue
        pkg = loaded["package"]
        spec = pkg.get("research_spec") if isinstance(pkg.get("research_spec"), dict) else {}
        identity = spec.get("identity") if isinstance(spec.get("identity"), dict) else {}
        handoff = pkg.get("roller_handoff") if isinstance(pkg.get("roller_handoff"), dict) else {}
        name = (
            (str(pkg.get("name") or "").strip() or None)
            or (str(identity.get("name") or "").strip() or None)
            or pkg.get("research_object_id")
        )
        out.append(
            {
                "package_id": pkg["package_id"],
                "source": pkg.get("source"),
                "population_n": pkg.get("population_n"),
                "imported_at": pkg.get("imported_at"),
                "schema_version": pkg.get("schema_version"),
                "name": name,
                "research_object_id": pkg.get("research_object_id"),
                "question_hash": pkg.get("question_hash"),
                "dataset_version": pkg.get("dataset_version"),
                "trade_origin": pkg.get("trade_origin"),
                "sport": _sport(loaded["trades"]),
                "decomposition_status": "PRESENT" if loaded["decomp"] is not None else "ABSENT",
                "code_version": pkg.get("code_version"),
                "semantics_version": pkg.get("semantics_version"),
                "workflow_draft": handoff.get("workflow_draft"),
            }
        )
    return out


def _sport(trades: list[dict[str, Any]]) -> str | None:
    sports = {t.get("sport") for t in trades if t.get("sport")}
    if len(sports) == 1:
        return next(iter(sports))
    if not sports:
        return None
    return "MIXED"
