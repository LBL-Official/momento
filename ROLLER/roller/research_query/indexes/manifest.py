"""Index manifest. Checksums + versions. Fail closed on mismatch."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

INDEX_VERSION = "rq_index_v1.0.0"
MANIFEST_NAME = "manifest.json"


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class IndexManifest:
    index_version: str
    dataset_version: str
    code_version: str
    operation_semantics_version: str
    league: str
    season: str
    sport: str
    built_at_utc: str
    git_sha: str | None
    source_paths: list[str]
    files: dict[str, str]
    ticker_count: int
    game_count: int
    bar_rows: int
    transition_rows: int
    settlement_rows: int
    coverage: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> IndexManifest:
        return cls(
            index_version=str(raw["index_version"]),
            dataset_version=str(raw["dataset_version"]),
            code_version=str(raw["code_version"]),
            operation_semantics_version=str(raw["operation_semantics_version"]),
            league=str(raw["league"]),
            season=str(raw["season"]),
            sport=str(raw["sport"]),
            built_at_utc=str(raw["built_at_utc"]),
            git_sha=raw.get("git_sha"),
            source_paths=list(raw.get("source_paths") or []),
            files=dict(raw.get("files") or {}),
            ticker_count=int(raw.get("ticker_count") or 0),
            game_count=int(raw.get("game_count") or 0),
            bar_rows=int(raw.get("bar_rows") or 0),
            transition_rows=int(raw.get("transition_rows") or 0),
            settlement_rows=int(raw.get("settlement_rows") or 0),
            coverage=dict(raw.get("coverage") or {}),
        )


def write_manifest(path: Path, manifest: IndexManifest) -> None:
    path.write_text(json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_manifest(path: Path) -> IndexManifest:
    return IndexManifest.from_dict(json.loads(path.read_text(encoding="utf-8")))


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git_sha() -> str | None:
    import subprocess

    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[3],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None
