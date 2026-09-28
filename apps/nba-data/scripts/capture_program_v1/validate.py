#!/usr/bin/env python3
"""Validate Engine B episodes. No status upgrades. No jsonschema dependency."""

from __future__ import annotations

import json
import shutil
import sys
from collections import defaultdict

from common import (
    ALLOWED_STATUS,
    EPISODES,
    OUT,
    SCHEMA_DIR,
    STATUS_RANK,
    load_json,
    utc_now,
    write_json,
)

EVENT_TYPES = {
    "MARKET_BEFORE_ENTRY",
    "ORDER_SUBMITTED",
    "ORDER_ACKNOWLEDGED",
    "BOOK_DURING_REST",
    "FILL",
    "NO_FILL",
    "POST_ENTRY_PATH_SAMPLE",
    "STOP_TOUCH",
    "STOP_FILL",
    "NO_STOP",
    "EXIT_EXECUTION",
    "SETTLEMENT",
    "NET_REALIZED_PNL",
    "CONNECTION",
    "ERROR",
}
INTENTS = {"ENTER", "SKIP", "UNAVAILABLE"}


def money_ok(obj, path, errors):
    if obj is None:
        return
    if not isinstance(obj, dict):
        errors.append(f"{path}: money must be object or null")
        return
    st = obj.get("status")
    if st not in ALLOWED_STATUS:
        errors.append(f"{path}.status invalid: {st}")
    if obj.get("amount") is not None and st == "UNAVAILABLE":
        errors.append(f"{path}: UNAVAILABLE money must not carry an amount")


def collect_statuses(episode):
    found = []
    for i, ev in enumerate(episode.get("events") or []):
        found.append((f"events[{i}]", ev.get("status")))
        for key in ("fee", "cash", "path_label_R"):
            blob = ev.get(key)
            if isinstance(blob, dict) and "status" in blob:
                found.append((f"events[{i}].{key}", blob.get("status")))
    return found


def validate_episode(episode, prior_status_by_path=None):
    errors = []
    if not isinstance(episode, dict):
        return ["episode is not an object"]
    if episode.get("schema_version") != "MOMENTO_NBA_CAPTURE_PROGRAM_V1":
        errors.append("schema_version must be MOMENTO_NBA_CAPTURE_PROGRAM_V1")
    if not episode.get("episode_id"):
        errors.append("episode_id required")
    if episode.get("engine_a_intent") not in INTENTS:
        errors.append("engine_a_intent invalid")
    if episode.get("live_armed") is not False:
        errors.append("live_armed must be false in this milestone")
    events = episode.get("events")
    if not isinstance(events, list):
        errors.append("events must be an array")
        return errors
    seen_idx = set()
    last_ts = None
    for i, ev in enumerate(events):
        if not isinstance(ev, dict):
            errors.append(f"events[{i}] not an object")
            continue
        et = ev.get("event_type")
        if et not in EVENT_TYPES:
            errors.append(f"events[{i}].event_type invalid: {et}")
        if ev.get("status") not in ALLOWED_STATUS:
            errors.append(f"events[{i}].status invalid")
        idx = ev.get("event_index")
        if not isinstance(idx, int) or idx < 0:
            errors.append(f"events[{i}].event_index invalid")
        elif idx in seen_idx:
            errors.append(f"duplicate event_index {idx}")
        else:
            seen_idx.add(idx)
        ts = ev.get("timestamp_unix")
        if ts is not None:
            if last_ts is not None and int(ts) < int(last_ts):
                errors.append(f"events[{i}] timestamp_unix went backwards")
            last_ts = ts
        for key in ("fee", "cash", "path_label_R"):
            money_ok(ev.get(key), f"events[{i}].{key}", errors)
        if et == "NET_REALIZED_PNL":
            cash = ev.get("cash")
            if isinstance(cash, dict) and cash.get("label") != "EV_realized":
                errors.append(f"events[{i}] NET_REALIZED_PNL cash.label must be EV_realized")
            path_r = ev.get("path_label_R")
            if isinstance(path_r, dict) and path_r.get("status") == "OBSERVED":
                errors.append(
                    f"events[{i}] path_label_R cannot be OBSERVED; it is a research path label"
                )
    if prior_status_by_path:
        for path, st in collect_statuses(episode):
            old = prior_status_by_path.get(path)
            if old is None or st not in ALLOWED_STATUS:
                continue
            if STATUS_RANK[st] > STATUS_RANK[old]:
                errors.append(f"status upgrade forbidden: {path} {old} -> {st}")
    return errors


def main() -> int:
    EPISODES.mkdir(parents=True, exist_ok=True)
    schema_out = OUT / "schema"
    schema_out.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SCHEMA_DIR / "episode.schema.json", schema_out / "episode.schema.json")
    shutil.copyfile(SCHEMA_DIR / "episode_template.json", schema_out / "episode_template.json")
    template_dest = EPISODES / "_template.json"
    if not template_dest.exists():
        shutil.copyfile(SCHEMA_DIR / "episode_template.json", template_dest)

    files = sorted(p for p in EPISODES.glob("*.json") if p.name != ".gitkeep")
    prior_path = OUT / "status_snapshot.json"
    prior = load_json(prior_path) if prior_path.exists() else {}
    n_ok = 0
    failures = []
    snapshot = {}
    for path in files:
        ep = load_json(path)
        eid = ep.get("episode_id") or path.stem
        errs = validate_episode(ep, prior.get(eid))
        snap = {k: v for k, v in collect_statuses(ep)}
        snapshot[eid] = snap
        if errs:
            failures.append({"file": str(path), "errors": errs})
        else:
            n_ok += 1
    write_json(prior_path, snapshot)
    report = {
        "written_utc": utc_now(),
        "n_files": len(files),
        "n_ok": n_ok,
        "n_fail": len(failures),
        "failures": failures,
        "rule": "UNAVAILABLE must not become ESTIMATED or OBSERVED; ESTIMATED must not become OBSERVED",
        "live_armed": False,
    }
    write_json(OUT / "validation.json", report)
    if failures:
        print(json.dumps(failures, indent=2), file=sys.stderr)
        print(f"VALIDATE FAIL files={len(failures)}", file=sys.stderr)
        return 1
    print(f"validate OK episodes={n_ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
