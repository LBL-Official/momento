"""Gates A/B — PADE and DRE V2 integrity. Read only."""

from __future__ import annotations

from pathlib import Path

from . import config as C


def _check(root: Path, required: tuple, hashes: dict, gate: str) -> dict:
    missing = []
    mismatch = []
    files = []
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
    status = "PASS" if not missing and not mismatch else "FAIL"
    return {
        "gate": gate,
        "status": status,
        "root": str(root),
        "missing": missing,
        "hash_mismatch": mismatch,
        "files": files,
        "note": "Read-only. DRE V3 does not write to this tree.",
    }


def gate_a_pade() -> dict:
    return _check(C.PADE_OUT, C.PADE_REQUIRED, C.PADE_SHA256_PREFIX, "A")


def gate_b_v2() -> dict:
    return _check(C.V2_OUT, C.V2_REQUIRED, C.V2_SHA256_PREFIX, "B")


def assert_untouched(before: dict) -> dict:
    changed = []
    for rec in before.get("files") or []:
        if not rec.get("exists"):
            continue
        now = C.sha256_prefix(Path(rec["path"]))
        if now != rec.get("sha256_16"):
            changed.append({"name": rec["name"], "before": rec.get("sha256_16"), "after": now})
    return {"ok": not changed, "changed": changed, "status": "PASS" if not changed else "FAIL"}
