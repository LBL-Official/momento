"""Versioned derived-tree manifest. Stale/corrupt → DATA_REQUIRED."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roller.base_terminal_efficiency.models import DATA_REQUIRED
from roller.base_terminal_efficiency.versions import CODE_VERSION, SCHEMA_VERSION, SEMANTICS_VERSION
from roller.io_csv import sha256_file


MANIFEST_NAME = "manifest.json"


@dataclass
class BaseTeManifest:
    schema_version: str
    semantics_version: str
    code_version: str
    dataset_version: str
    git_sha: str | None
    build_timestamp_utc: str
    league: str
    season: str
    source_paths: list[str]
    source_checksums: dict[str, str]
    observation_count: int
    game_count: int
    ticker_count: int
    coverage_start: str | None
    coverage_end: str | None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def checksum_paths(paths: list[Path]) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in paths:
        if p.is_file():
            out[str(p)] = sha256_file(p)
        elif p.is_dir():
            for child in sorted(p.rglob("*")):
                if child.is_file():
                    out[str(child)] = sha256_file(child)
        else:
            out[str(p)] = "missing"
    return out


def write_manifest(path: Path, man: BaseTeManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(man.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_manifest(path: Path) -> BaseTeManifest | str:
    if not path.is_file():
        return DATA_REQUIRED
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return DATA_REQUIRED
    try:
        return BaseTeManifest(
            schema_version=str(raw["schema_version"]),
            semantics_version=str(raw["semantics_version"]),
            code_version=str(raw["code_version"]),
            dataset_version=str(raw["dataset_version"]),
            git_sha=raw.get("git_sha"),
            build_timestamp_utc=str(raw["build_timestamp_utc"]),
            league=str(raw["league"]),
            season=str(raw["season"]),
            source_paths=list(raw["source_paths"]),
            source_checksums=dict(raw["source_checksums"]),
            observation_count=int(raw["observation_count"]),
            game_count=int(raw["game_count"]),
            ticker_count=int(raw["ticker_count"]),
            coverage_start=raw.get("coverage_start"),
            coverage_end=raw.get("coverage_end"),
            extra=dict(raw.get("extra") or {}),
        )
    except (KeyError, TypeError, ValueError):
        return DATA_REQUIRED


def validate_against_sources(man: BaseTeManifest, current: dict[str, str]) -> str | None:
    if man.semantics_version != SEMANTICS_VERSION or man.code_version != CODE_VERSION:
        return DATA_REQUIRED
    if man.schema_version != SCHEMA_VERSION:
        return DATA_REQUIRED
    if man.source_checksums != current:
        return DATA_REQUIRED
    return None
