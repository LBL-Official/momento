"""Gates A/B/G — V5 locks, predecessor hashes, V5 tree untouched."""

from __future__ import annotations

import json
from pathlib import Path

from . import config as C


def _check_files(root: Path, hashes: dict, gate: str, note: str) -> dict:
    missing, mismatch, files = [], [], []
    for name, exp in hashes.items():
        path = root / name
        rec = {"name": name, "exists": path.exists(), "path": str(path), "expected": exp}
        if not path.exists():
            missing.append(name)
            files.append(rec)
            continue
        rec["sha256_16"] = C.sha256_prefix(path)
        rec["hash_match"] = rec["sha256_16"] == exp
        if not rec["hash_match"]:
            mismatch.append(name)
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


def gate_a_v5_locks() -> dict:
    man_p = C.V5_OUT / "13_run_manifest.json"
    verd_p = C.V5_OUT / "15_discovery_verdict.json"
    proto_p = C.V5_OUT / "OOS_REPLICATION_PROTOCOL.json"
    locks_p = C.V5_OUT / "SPECIFICATION_LOCKS.json"
    missing = [str(p) for p in (man_p, verd_p, proto_p, locks_p) if not p.exists()]
    if missing:
        return {"gate": "A", "status": "FAIL", "missing": missing}
    man = json.loads(man_p.read_text())
    verd = json.loads(verd_p.read_text())
    headline = (verd.get("verdict") or {}).get("HEADLINE") or man.get("headline")
    proto_first = bool(man.get("protocol_written_before_oos"))
    ok = headline == C.V5_PUBLISHED["headline"] and proto_first
    return {
        "gate": "A",
        "status": "PASS" if ok else "FAIL",
        "headline": headline,
        "expected_headline": C.V5_PUBLISHED["headline"],
        "protocol_written_before_oos": proto_first,
        "note": "V5 Verdict B is historical. V6 does not reopen it.",
    }


def gate_b_predecessors() -> dict:
    parts = {
        "pade": _check_files(C.PADE_OUT, C.PADE_SHA256_PREFIX, "B", "PADE read-only"),
        "v2": _check_files(C.V2_OUT, C.V2_SHA256_PREFIX, "B", "V2 read-only"),
        "v3": _check_files(C.V3_OUT, C.V3_SHA256_PREFIX, "B", "V3 read-only"),
        "v4": _check_files(C.V4_OUT, C.V4_SHA256_PREFIX, "B", "V4 read-only"),
    }
    fail = [k for k, v in parts.items() if v["status"] != "PASS"]
    return {"gate": "B", "status": "PASS" if not fail else "FAIL", "failed": fail, "parts": parts}


def snapshot_v5() -> dict:
    files = {}
    if C.V5_OUT.exists():
        for p in sorted(C.V5_OUT.rglob("*")):
            if p.is_file():
                rel = str(p.relative_to(C.V5_OUT))
                files[rel] = C.sha256_prefix(p)
    return {"root": str(C.V5_OUT), "n": len(files), "files": files}


def gate_g_v5_untouched(before: dict) -> dict:
    after = snapshot_v5()
    changed = []
    b, a = before.get("files") or {}, after.get("files") or {}
    keys = set(b) | set(a)
    for k in sorted(keys):
        if b.get(k) != a.get(k):
            changed.append({"name": k, "before": b.get(k), "after": a.get(k)})
    return {
        "gate": "G",
        "status": "PASS" if not changed else "FAIL",
        "changed": changed,
        "n_before": before.get("n"),
        "n_after": after.get("n"),
        "note": "V6 must not write into the V5 tree.",
    }
