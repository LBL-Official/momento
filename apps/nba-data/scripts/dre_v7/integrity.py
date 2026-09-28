"""Gates A–J. Snapshot V5 and V6 trees. Do not write into predecessors."""

from __future__ import annotations

import json
from pathlib import Path

from . import config as C

CODE_FILES = (
    C.NBA_SCRIPTS / "dre_v5" / "possession_remaining.py",
    C.NBA_SCRIPTS / "dre_v5" / "state_panel.py",
    C.NBA_SCRIPTS / "dre_v5" / "surfaces.py",
    C.NBA_SCRIPTS / "dre_v6" / "maps.py",
)


def snapshot_tree(root: Path) -> dict:
    files = {}
    if root.exists():
        for p in sorted(root.rglob("*")):
            if p.is_file():
                files[str(p.relative_to(root))] = C.sha256_prefix(p)
    return {"root": str(root), "n": len(files), "files": files}


def snapshot_code() -> dict:
    out = {}
    for p in CODE_FILES:
        out[str(p.relative_to(C.REPO))] = {
            "exists": p.exists(),
            "sha256": C.sha256_full(p) if p.exists() else None,
            "sha256_16": C.sha256_prefix(p) if p.exists() else None,
        }
    return out


def snapshot_all() -> dict:
    return {
        "v5": snapshot_tree(C.V5_OUT),
        "v6": snapshot_tree(C.V6_OUT),
        "code": snapshot_code(),
        "written_utc": C.utc_now(),
    }


def trees_unchanged(before: dict, after: dict) -> dict:
    changed = []
    for key in ("v5", "v6"):
        b = (before.get(key) or {}).get("files") or {}
        a = (after.get(key) or {}).get("files") or {}
        for name in sorted(set(b) | set(a)):
            if b.get(name) != a.get(name):
                changed.append({"tree": key, "name": name, "before": b.get(name), "after": a.get(name)})
    return {
        "gate": "G",
        "status": "PASS" if not changed else "FAIL",
        "changed": changed,
        "n_v5_before": (before.get("v5") or {}).get("n"),
        "n_v6_before": (before.get("v6") or {}).get("n"),
    }


def gate_a() -> dict:
    v5m = json.loads((C.V5_OUT / "15_discovery_verdict.json").read_text())
    v6m = json.loads((C.V6_OUT / "13_run_manifest.json").read_text())
    v6v = json.loads((C.V6_OUT / "15_discovery_verdict.json").read_text())
    h5 = (v5m.get("verdict") or {}).get("HEADLINE") or json.loads((C.V5_OUT / "13_run_manifest.json").read_text()).get("headline")
    h6 = (v6v.get("verdict") or {}).get("HEADLINE") or v6m.get("headline") or v6m.get("verdict_status")
    ok = h5 == C.V5_PUBLISHED["headline"] and h6 == C.V6_STATUS
    return {
        "gate": "A",
        "status": "PASS" if ok else "FAIL",
        "v5_headline": h5,
        "v6_status": h6,
        "note": "Predecessors are historical. V7 does not reopen them.",
    }


def gate_c_maps(maps_obj: dict) -> dict:
    ident = maps_obj.get("identity") or {}
    obs = ident.get("observed") or {}
    ok = (
        int(maps_obj.get("n_m0") or 0) == C.V5_PUBLISHED["n_m0_cells"]
        and int(maps_obj.get("n_m1") or 0) == C.V5_PUBLISHED["n_m1_cells"]
        and obs.get("n_m0_cells") == C.V5_PUBLISHED["n_m0_cells"]
        and obs.get("n_m1_cells") == C.V5_PUBLISHED["n_m1_cells"]
        and ident.get("status") == "PASS"
    )
    return {
        "gate": "C",
        "status": "PASS" if ok else "FAIL",
        "n_m0": maps_obj.get("n_m0"),
        "n_m1": maps_obj.get("n_m1"),
        "identity": obs,
        "source": maps_obj.get("source"),
        "train_only": maps_obj.get("train_only"),
    }


def gate_j_decile_edges() -> dict:
    p = C.V6_OUT / "03_train_decile_edges.json"
    if not p.exists():
        return {"gate": "J", "status": "NOT_APPLICABLE", "compatible": False, "reason": "missing V6 edges"}
    obj = json.loads(p.read_text())
    source = str(obj.get("source") or "")
    assign = str(obj.get("assignment") or "")
    outside = str(obj.get("outside_train_range") or "")
    compatible = (
        "TRAIN mean_SIR_i" in source
        and "qcut" in source
        and "CLIP_TO_TRAIN_EXTREMA" in outside
        and "include_lowest=True" in assign
        and "right=True" in assign
        and int(obj.get("n_deciles") or 0) == 10
        and isinstance(obj.get("edges"), list)
        and len(obj.get("edges") or []) == 11
    )
    return {
        "gate": "J",
        "status": "PASS" if compatible else "NOT_APPLICABLE",
        "compatible": compatible,
        "source_variable": source,
        "unit_of_observation": "trade" if "mean_SIR_i" in source else "UNKNOWN",
        "transformation": "qcut" if "qcut" in source else "UNKNOWN",
        "edge_semantics": {"outside": outside, "assignment": assign},
        "edges": obj.get("edges"),
        "v7_target": "mean_da_i (trade-level mean of da_state) — same object as V6 mean_SIR_i if compatible",
        "note": "If incompatible: do not apply. Do not convert. Do not recompute quantiles.",
    }


def gate_h(blob) -> dict:
    """Headline objects must not use execution/P&L as evidence. Prohibition lists are allowed."""

    def _strip(o):
        if isinstance(o, dict):
            return {k: _strip(v) for k, v in o.items() if k not in ("not", "forbidden", "forbidden_in", "limitations")}
        if isinstance(o, list):
            return [_strip(v) for v in o]
        return o

    text = json.dumps(_strip(blob), default=str)
    bad = []
    for tok in ("fill_status", "pi_40_framework", "realized_pnl", "fee_cents", "ENABLE_LIVE_TRADING"):
        if tok in text:
            bad.append(tok)
    return {"gate": "H", "status": "PASS" if not bad else "FAIL", "bad": bad}
