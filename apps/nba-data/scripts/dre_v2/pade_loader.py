"""GATE B — load frozen PADE V1 artifacts. Read only. Never write to PADE."""

from __future__ import annotations

from pathlib import Path

from . import config as C


def pade_integrity() -> dict:
    missing = []
    files = []
    hash_mismatch = []
    for name in C.PADE_REQUIRED:
        path = C.PADE_OUT / name
        rec = {"name": name, "path": str(path), "exists": path.exists()}
        if not path.exists():
            missing.append(name)
            files.append(rec)
            continue
        rec["bytes"] = path.stat().st_size
        rec["sha256_16"] = C.sha256_prefix(path)
        expected = C.PADE_SHA256_PREFIX.get(name)
        rec["expected_sha256_16"] = expected
        if expected and rec["sha256_16"] != expected:
            hash_mismatch.append(name)
            rec["hash_match"] = False
        elif expected:
            rec["hash_match"] = True
        files.append(rec)

    panel_path = C.PADE_OUT / "05_trade_possession_panel.parquet"
    row_counts = {}
    if panel_path.exists():
        import pyarrow.parquet as pq

        for fname, key in (
            ("05_trade_possession_panel.parquet", "panel"),
            ("01_game_timeline.parquet", "timelines"),
            ("03_possessions.parquet", "possessions"),
            ("06_state_features.parquet", "state_features"),
            ("07_forward_labels.parquet", "forward_labels"),
        ):
            p = C.PADE_OUT / fname
            if p.exists():
                row_counts[key] = pq.read_table(p, columns=[]).num_rows

    status = "PASS"
    if missing:
        status = "FAIL"
    elif hash_mismatch:
        status = "FAIL"

    return {
        "gate": "B",
        "status": status,
        "pade_root": str(C.PADE_OUT),
        "missing": missing,
        "hash_mismatch": hash_mismatch,
        "files": files,
        "row_counts": row_counts,
        "note": "DRE V2 consumes PADE V1. It does not overwrite PADE outputs or logic.",
        "pade_modified": False,
    }


def load_panel() -> list[dict]:
    return C.read_parquet_rows(C.PADE_OUT / "05_trade_possession_panel.parquet")


def load_pade_summary() -> dict:
    path = C.PADE_OUT / "summary.json"
    if not path.exists():
        return {}
    import json

    return json.loads(path.read_text())


def assert_pade_untouched(before: dict) -> dict:
    """Re-hash PADE files after the DRE run. Fail if any required file changed."""
    changed = []
    for rec in before.get("files") or []:
        name = rec.get("name")
        if not name or not rec.get("exists"):
            continue
        path = Path(rec["path"])
        now = C.sha256_prefix(path)
        if now != rec.get("sha256_16"):
            changed.append({"name": name, "before": rec.get("sha256_16"), "after": now})
    return {
        "pade_files_changed": changed,
        "ok": len(changed) == 0,
        "status": "PASS" if not changed else "FAIL",
    }
