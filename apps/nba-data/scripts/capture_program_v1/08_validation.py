#!/usr/bin/env python3
"""STEP 16 — Validate artifacts, frozen hashes, and observation-status rules."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from common import (
    ALLOWED_STATUS,
    AUDIT,
    DIR_BASELINE,
    DIR_LEDGER,
    DIR_VAL,
    EPISODES,
    FROZEN_N,
    FROZEN_SHA256,
    FROZEN_STOPS_CLOSE,
    FROZEN_SURVIVORS,
    NBA_SCRIPTS,
    OUT,
    STATUS_RANK,
    ensure_dirs,
    load_json,
    provenance,
    sha256_file,
    write_json,
)

FORBIDDEN_TOUCH = [
    NBA_SCRIPTS / "nba_80_40_execution_audit.py",
    AUDIT / "summary.json",
    AUDIT / "ledger_baseline.json",
    AUDIT / "ledger_conservative.json",
    AUDIT / "candidates.json",
    AUDIT / "rejected_conservative.json",
    AUDIT / "REPORT.md",
]


def validate_episode(episode: dict, prior_status_by_path: dict | None) -> list[str]:
    errors = []
    if episode.get("schema_version") != "MOMENTO_NBA_CAPTURE_PROGRAM_V1":
        errors.append("schema_version must be MOMENTO_NBA_CAPTURE_PROGRAM_V1")
    if episode.get("live_armed") is not False:
        errors.append("live_armed must be false in this milestone")
    events = episode.get("events")
    if not isinstance(events, list):
        errors.append("events must be an array")
        return errors
    for i, ev in enumerate(events):
        st = ev.get("status")
        if st not in ALLOWED_STATUS:
            errors.append(f"events[{i}].status invalid: {st}")
        for key in ("fee", "cash", "path_label_R"):
            blob = ev.get(key)
            if isinstance(blob, dict):
                bst = blob.get("status")
                if bst not in ALLOWED_STATUS:
                    errors.append(f"events[{i}].{key}.status invalid: {bst}")
                if bst == "UNAVAILABLE" and blob.get("amount") is not None:
                    errors.append(f"events[{i}].{key}: UNAVAILABLE must not carry amount")
                if key == "path_label_R" and bst == "OBSERVED":
                    errors.append("path_label_R cannot be OBSERVED")
    if prior_status_by_path:
        for i, ev in enumerate(events):
            path = f"events[{i}]"
            st = ev.get("status")
            old = prior_status_by_path.get(path)
            if old in STATUS_RANK and st in STATUS_RANK:
                if STATUS_RANK[st] > STATUS_RANK[old]:
                    errors.append(f"status upgrade forbidden: {path} {old} -> {st}")
    return errors


def collect_statuses(episode: dict) -> dict:
    found = {}
    for i, ev in enumerate(episode.get("events") or []):
        found[f"events[{i}]"] = ev.get("status")
        for key in ("fee", "cash", "path_label_R"):
            blob = ev.get(key)
            if isinstance(blob, dict) and "status" in blob:
                found[f"events[{i}].{key}"] = blob.get("status")
    return found


def main() -> int:
    ensure_dirs()
    failures = []

    hash_ok = True
    hash_report = {}
    mapping = {
        "nba_80_40_execution_audit.py": NBA_SCRIPTS / "nba_80_40_execution_audit.py",
        "summary.json": AUDIT / "summary.json",
        "ledger_baseline.json": AUDIT / "ledger_baseline.json",
        "ledger_conservative.json": AUDIT / "ledger_conservative.json",
        "candidates.json": AUDIT / "candidates.json",
        "rejected_conservative.json": AUDIT / "rejected_conservative.json",
        "REPORT.md": AUDIT / "REPORT.md",
    }
    for name, path in mapping.items():
        got = sha256_file(path)
        exp = FROZEN_SHA256[name]
        ok = got == exp
        hash_report[name] = {"expected": exp, "got": got, "ok": ok}
        if not ok:
            hash_ok = False
            failures.append(f"frozen hash mismatch {name}")

    base = load_json(DIR_BASELINE / "summary.json")
    reproduced = (
        base.get("universe") == FROZEN_N
        and base.get("survivors") == FROZEN_SURVIVORS
        and base.get("close_path_40") == FROZEN_STOPS_CLOSE
        and base.get("reproduced") is True
    )
    if not reproduced:
        failures.append("baseline 1230/910/320 not reproduced")

    required = [
        OUT / "historical_path_baseline.parquet",
        OUT / "execution_scenario_matrix.parquet",
        OUT / "fill_assumption_matrix.parquet",
        OUT / "stop_execution_matrix.parquet",
        OUT / "fee_model_matrix.parquet",
        OUT / "capacity_simulation.parquet",
        OUT / "portfolio_simulation.parquet",
        OUT / "live_episode_ledger.parquet",
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        failures.append(f"missing artifacts: {missing}")

    import pandas as pd

    live = pd.read_parquet(OUT / "live_episode_ledger.parquet")
    if len(live) != 0:
        failures.append(f"live ledger must be empty, got {len(live)}")

    fee = load_json(OUT / "fee_scenarios" / "summary.json")
    if fee.get("FEE_MODEL_STATUS") != "UNRESOLVED":
        failures.append("FEE_MODEL_STATUS must be UNRESOLVED")
    if fee.get("observed_production_available") is not False:
        failures.append("observed production fee model must stay unavailable")

    # Episode JSON files (template only is OK)
    files = sorted(p for p in EPISODES.glob("*.json") if p.name != ".gitkeep")
    prior_path = OUT / "status_snapshot.json"
    prior = load_json(prior_path) if prior_path.exists() else {}
    snapshot = {}
    n_ok = 0
    for path in files:
        ep = load_json(path)
        eid = ep.get("episode_id") or path.stem
        errs = validate_episode(ep, prior.get(eid))
        snapshot[eid] = collect_statuses(ep)
        if errs:
            failures.append({"file": str(path), "errors": errs})
        else:
            n_ok += 1
    write_json(prior_path, snapshot)

    # Surface rows must not claim OBSERVED fills
    surface = pd.read_parquet(OUT / "execution_scenario_matrix.parquet")
    if "label" in surface.columns:
        bad = surface[surface["label"].astype(str).str.contains("OBSERVED_FILL", na=False)]
        if len(bad):
            failures.append("execution surface contains OBSERVED_FILL labels")

    report = {
        **provenance(),
        "n_episode_files": len(files),
        "n_episode_ok": n_ok,
        "frozen_hashes": hash_report,
        "frozen_source_unmodified": hash_ok,
        "reproduced_1230_910_320": reproduced,
        "live_ledger_rows": int(len(live)),
        "fee_model_status": fee.get("FEE_MODEL_STATUS"),
        "live_execution_changed": False,
        "live_armed": False,
        "failures": failures,
        "ok": len(failures) == 0 and hash_ok and reproduced,
    }
    write_json(DIR_VAL / "validation.json", report)
    write_json(OUT / "validation.json", report)
    if not report["ok"]:
        print(json.dumps(failures, indent=2), file=sys.stderr)
        print("VALIDATE FAIL", file=sys.stderr)
        return 1
    print(
        "validate OK reproduced=1230/910/320 "
        f"hashes=ok ledger=0 FEE=UNRESOLVED LIVE_EXECUTION_CHANGED=FALSE"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
