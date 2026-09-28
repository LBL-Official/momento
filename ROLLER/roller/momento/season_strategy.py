"""Editable 2026-27 season selector. Does not rewrite the historical 80/40 book."""

from __future__ import annotations

import json
from typing import Any

from roller.paths import find_root, momento_root

SELECTOR_RELATIVE = "momento/registry/season_strategy.json"
BOOK_HASH = "4da5fdd3a48d2a5513ab6e9452657a790514fbef389a05d0385cfaba009b8cf6"
FIRST80_HASH = "ba895f677938b8e1a33c2eb5d5a9835e8312a007ad207bcfee25f3f32eecb44f"


class SeasonStrategyError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _read_json(path) -> dict[str, Any]:
    body = json.loads(path.read_text())
    if not isinstance(body, dict):
        raise SeasonStrategyError("SELECTOR_INVALID", f"{path} is not an object")
    return body


def resolve_season_strategy() -> dict[str, Any]:
    root = momento_root(find_root())
    selector_path = root / SELECTOR_RELATIVE
    selector = _read_json(selector_path)
    if selector.get("live_execution") is not False or selector.get("submits") is not False:
        raise SeasonStrategyError("LIVE_EXECUTION_FORBIDDEN", "season selector must keep live execution off")
    artifact_rel = selector.get("official_artifact")
    if not isinstance(artifact_rel, str) or not artifact_rel:
        raise SeasonStrategyError("SELECTOR_INVALID", "official_artifact is missing")
    artifact = _read_json(root / artifact_rel)
    if artifact.get("strategy_id") != selector.get("official_strategy_id"):
        raise SeasonStrategyError("SELECTOR_MISMATCH", "selector id does not match the official artifact")
    if artifact.get("live_execution") is not False or artifact.get("submits") is not False:
        raise SeasonStrategyError("LIVE_EXECUTION_FORBIDDEN", "official artifact must keep live execution off")
    if artifact.get("states", {}).get("validation") != "NOT_YET_IDENTIFIABLE":
        raise SeasonStrategyError("VALIDATION_MISMATCH", "validation status must stay the recorded audit status")
    book_rel = selector.get("historical_research_book", {}).get("path")
    if not isinstance(book_rel, str):
        raise SeasonStrategyError("SELECTOR_INVALID", "historical book path is missing")
    book = _read_json(root / book_rel)
    registered = book.get("registered") or {}
    if registered.get("status") != "RESEARCH_REGISTERED":
        raise SeasonStrategyError("BASELINE_CHANGED", "historical book registration status changed")
    if registered.get("entry_cents") != 80 or registered.get("stop_cents") != 40:
        raise SeasonStrategyError("BASELINE_CHANGED", "historical 80/40 entry or stop changed")
    labels = artifact.get("labels") or {}
    return {
        "schema_version": selector.get("schema_version"),
        "season_id": selector.get("season_id"),
        "official_strategy_id": selector["official_strategy_id"],
        "official_display_name": artifact.get("display_name"),
        "official_artifact": artifact_rel,
        "live_execution": False,
        "submits": False,
        "labels": {
            "official": labels.get("official"),
            "live_execution": labels.get("live_execution"),
            "validation": labels.get("validation"),
        },
        "validation_status": artifact["states"]["validation"],
        "validation_limitations": list(artifact.get("validation", {}).get("limitations") or []),
        "historical_research_book": {
            "role": "HISTORICAL_REGISTERED_RESEARCH_BASELINE",
            "book_id": book.get("book_id"),
            "registration_status": registered.get("status"),
            "entry_cents": registered.get("entry_cents"),
            "stop_cents": registered.get("stop_cents"),
            "title": registered.get("title"),
        },
        "unresolved_execution": artifact.get("unresolved_execution"),
    }
