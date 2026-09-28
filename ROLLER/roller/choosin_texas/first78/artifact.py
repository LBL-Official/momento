"""Read the frozen strategy and the latest computed artifact. Never the FIRST80 universe."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from roller.choosin_texas.models import ChoosinTexasError
from roller.paths import find_root, momento_root

CONTRACT_RELATIVE = "research/first78_active_v1/strategy.json"
LATEST_RELATIVE = "research/first78_active_v1/LATEST.json"


def repo_root() -> Path:
    return momento_root(find_root())


def strategy_path() -> Path:
    return repo_root() / CONTRACT_RELATIVE


def load_strategy() -> dict[str, Any]:
    path = strategy_path()
    if not path.is_file():
        raise ChoosinTexasError("DATA_REQUIRED", f"missing {CONTRACT_RELATIVE}")
    body = json.loads(path.read_text())
    if body.get("official_strategy_id") != "FIRST78_67":
        raise ChoosinTexasError("STRATEGY_MISMATCH", "official strategy is not FIRST78_67")
    if body.get("live_execution") is not False:
        raise ChoosinTexasError("LIVE_EXECUTION_FORBIDDEN", "FIRST78 desk cannot enable live execution")
    return body


def strategy_sha256() -> str:
    return hashlib.sha256(strategy_path().read_bytes()).hexdigest()


def variant_stop(variant: str, strategy: dict[str, Any] | None = None) -> int:
    text = str(variant)
    if text.startswith("FIRST78_"):
        text = text.split("_", 1)[1]
    try:
        stop = int(text)
    except ValueError as exc:
        raise ChoosinTexasError("UNKNOWN_VARIANT", f"unknown FIRST78 variant {variant}") from exc
    allowed = {int(row["stop_cents"]) for row in (strategy or load_strategy())["variants"]}
    if stop not in allowed:
        raise ChoosinTexasError("UNKNOWN_VARIANT", f"unsupported stop {stop}")
    return stop


DERIVED_LATEST = "research/first78_derived_four_v1/LATEST.json"


def load_derived() -> dict[str, Any]:
    root = repo_root()
    pointer = root / DERIVED_LATEST
    if not pointer.is_file():
        return _derived_unavailable("ARTIFACT_UNAVAILABLE", "No derived-four FIRST78 artifact has been written.")
    latest = json.loads(pointer.read_text())
    run_rel = latest.get("summary")
    if not isinstance(run_rel, str):
        return _derived_unavailable("ARTIFACT_UNAVAILABLE", "Derived LATEST.json has no summary path.")
    summary_path = root / run_rel
    if not summary_path.is_file():
        return _derived_unavailable("ARTIFACT_UNAVAILABLE", f"Missing {run_rel}.")
    body = json.loads(summary_path.read_text())
    if body.get("strategy_sha256") != strategy_sha256():
        return _derived_unavailable("ARTIFACT_STALE", "Derived artifact was built from a different strategy contract.")
    if body.get("population_id") != "DERIVED_FOUR_FIRST78":
        return _derived_unavailable("POPULATION_MISMATCH", "Artifact population is not DERIVED_FOUR_FIRST78.")
    body["status"] = "OBSERVED"
    return body


def _derived_unavailable(code: str, message: str) -> dict[str, Any]:
    return {
        "status": code,
        "message": message,
        "official_strategy_id": "FIRST78_67",
        "population_id": "DERIVED_FOUR_FIRST78",
        "live_execution": False,
        "submits": False,
        "fallback_to_first80": False,
        "variants": [],
    }


def load_artifact() -> dict[str, Any]:
    root = repo_root()
    pointer = root / LATEST_RELATIVE
    if not pointer.is_file():
        return _unavailable("ARTIFACT_UNAVAILABLE", "No FIRST78 artifact has been written.")
    latest = json.loads(pointer.read_text())
    run_rel = latest.get("summary")
    if not isinstance(run_rel, str):
        return _unavailable("ARTIFACT_UNAVAILABLE", "LATEST.json has no summary path.")
    summary_path = root / run_rel
    if not summary_path.is_file():
        return _unavailable("ARTIFACT_UNAVAILABLE", f"Missing {run_rel}.")
    body = json.loads(summary_path.read_text())
    expected = strategy_sha256()
    if body.get("strategy_sha256") != expected:
        return _unavailable("ARTIFACT_STALE", "Artifact was built from a different strategy contract.")
    if body.get("population_id") != "PRIMARY_EX_ANTE_FIRST78":
        return _unavailable("POPULATION_MISMATCH", "Artifact population is not PRIMARY_EX_ANTE_FIRST78.")
    body["status"] = "OBSERVED"
    return body


def _unavailable(code: str, message: str) -> dict[str, Any]:
    strategy = {}
    path = strategy_path()
    if path.is_file():
        strategy = json.loads(path.read_text())
    return {
        "status": code,
        "message": message,
        "official_strategy_id": strategy.get("official_strategy_id", "FIRST78_67"),
        "population_id": "PRIMARY_EX_ANTE_FIRST78",
        "live_execution": False,
        "submits": False,
        "fallback_to_first80": False,
        "variants": [],
        "candidates": [],
        "paired": [],
    }
