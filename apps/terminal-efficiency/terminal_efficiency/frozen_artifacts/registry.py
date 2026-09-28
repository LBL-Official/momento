"""Load published freeze manifests. Exact identity match only. No latest/fallback."""

from __future__ import annotations

import json
from pathlib import Path

from terminal_efficiency.consumption.errors import FrozenUnavailable, VersionMismatch
from terminal_efficiency.consumption.models import FrozenIdentity

MANIFEST_DIR = Path(__file__).resolve().parent / "manifests"


def _load_all() -> list[dict]:
    if not MANIFEST_DIR.is_dir():
        return []
    rows = []
    for path in sorted(MANIFEST_DIR.glob("*.json")):
        rows.append(json.loads(path.read_text()))
    return rows


def list_published() -> list[FrozenIdentity]:
    return [_identity(row) for row in _load_all()]


def published_records() -> list[dict]:
    return list(_load_all())


def _identity(row: dict) -> FrozenIdentity:
    return FrozenIdentity(
        league=str(row["league"]),
        season=str(row["season"]),
        dataset_version=str(row["dataset_version"]),
        feature_set_version=str(row["feature_set_version"]),
        model_version=str(row["model_version"]),
        code_version=str(row["code_version"]),
        artifact_manifest_hash=str(row["artifact_manifest_hash"]),
    )


def resolve_published(
    *,
    league: str | None = None,
    season: str | None = None,
    dataset_version: str | None = None,
    feature_set_version: str | None = None,
    model_version: str | None = None,
    code_version: str | None = None,
    artifact_manifest_hash: str | None = None,
    identity: FrozenIdentity | None = None,
) -> tuple[FrozenIdentity, dict]:
    if identity is not None:
        league = identity.league
        season = identity.season
        dataset_version = identity.dataset_version
        feature_set_version = identity.feature_set_version
        model_version = identity.model_version
        code_version = identity.code_version
        artifact_manifest_hash = identity.artifact_manifest_hash or artifact_manifest_hash

    if model_version and str(model_version).lower() in {"latest", "current", "prod"}:
        raise VersionMismatch("model_version must be an explicit freeze id, not 'latest'")

    matches = []
    for row in _load_all():
        if league and str(row["league"]).upper() != str(league).upper():
            continue
        if season and str(row["season"]) != str(season):
            continue
        if dataset_version and str(row["dataset_version"]) != str(dataset_version):
            continue
        if feature_set_version and str(row["feature_set_version"]) != str(feature_set_version):
            continue
        if model_version and str(row["model_version"]) != str(model_version):
            continue
        if code_version and str(row["code_version"]) != str(code_version):
            continue
        if artifact_manifest_hash and str(row["artifact_manifest_hash"]) != str(artifact_manifest_hash):
            continue
        matches.append(row)

    if not matches:
        raise VersionMismatch("UNAVAILABLE: requested freeze identity is not published")
    if len(matches) > 1:
        raise FrozenUnavailable(
            "UNAVAILABLE: league/season is ambiguous; specify dataset/feature/model/code versions"
        )
    row = matches[0]
    return _identity(row), row
