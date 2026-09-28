"""Gates B/C — PADE and DRE V4 integrity. Read only."""

from __future__ import annotations

from pathlib import Path

from . import config as C


def _check(root: Path, required: tuple, hashes: dict, gate: str, note: str) -> dict:
    missing, mismatch, files = [], [], []
    for name in required:
        path = root / name
        rec = {"name": name, "exists": path.exists(), "path": str(path)}
        if not path.exists():
            missing.append(name)
            files.append(rec)
            continue
        rec["bytes"] = path.stat().st_size
        rec["sha256_16"] = C.sha256_prefix(path)
        exp = hashes.get(name)
        rec["expected"] = exp
        if exp and rec["sha256_16"] != exp:
            mismatch.append(name)
            rec["hash_match"] = False
        elif exp:
            rec["hash_match"] = True
        files.append(rec)
    return {
        "gate": gate,
        "status": "PASS" if not missing and not mismatch else "FAIL",
        "root": str(root),
        "missing": missing,
        "hash_mismatch": mismatch,
        "files": files,
        "note": note,
    }


def gate_b_pade() -> dict:
    return _check(
        C.PADE_OUT,
        C.PADE_REQUIRED,
        C.PADE_SHA256_PREFIX,
        "B",
        "Read-only. DRE V5 does not write to PADE.",
    )


def gate_c_v4() -> dict:
    return _check(
        C.V4_OUT,
        C.V4_REQUIRED,
        C.V4_SHA256_PREFIX,
        "C",
        "Read-only predecessor freeze. DRE V5 does not write to DRE V4.",
    )


def assert_untouched(before: dict) -> dict:
    changed = []
    for rec in before.get("files") or []:
        if not rec.get("exists"):
            continue
        now = C.sha256_prefix(Path(rec["path"]))
        if now != rec.get("sha256_16"):
            changed.append({"name": rec["name"], "before": rec.get("sha256_16"), "after": now})
    return {"ok": not changed, "changed": changed, "status": "PASS" if not changed else "FAIL"}
