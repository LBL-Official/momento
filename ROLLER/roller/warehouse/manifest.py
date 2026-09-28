"""Sidecar manifest for a dual-written parquet partition. Not an rq_index."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roller.warehouse.hashing import file_sha256
from roller.warehouse import CONTRACT_VERSION, SCHEMA_VERSION

MANIFEST_NAME = "parquet_manifest.json"


@dataclass
class PartitionManifest:
    contract_version: str
    schema_version: str
    dataset_name: str
    observation_basis: str | None
    sport: str
    league: str
    season: str
    month: str
    csv_path: str
    parquet_path: str
    csv_sha256: str
    parquet_sha256: str
    row_count: int
    built_at_utc: str
    source_revision: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> PartitionManifest:
        return cls(**{k: raw[k] for k in cls.__dataclass_fields__})  # type: ignore[arg-type]


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_partition_manifest(path: Path, manifest: PartitionManifest) -> None:
    path.write_text(json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_partition_manifest(path: Path) -> PartitionManifest:
    return PartitionManifest.from_dict(json.loads(path.read_text(encoding="utf-8")))


def manifest_for_pair(
    *,
    dataset_name: str,
    observation_basis: str | None,
    sport: str,
    league: str,
    season: str,
    month: str,
    csv_path: Path,
    parquet_path: Path,
    row_count: int,
    source_revision: str | None = None,
) -> PartitionManifest:
    return PartitionManifest(
        contract_version=CONTRACT_VERSION,
        schema_version=SCHEMA_VERSION,
        dataset_name=dataset_name,
        observation_basis=observation_basis,
        sport=sport,
        league=league,
        season=season,
        month=month,
        csv_path=str(csv_path),
        parquet_path=str(parquet_path),
        csv_sha256=file_sha256(csv_path),
        parquet_sha256=file_sha256(parquet_path),
        row_count=row_count,
        built_at_utc=now_utc(),
        source_revision=source_revision,
    )
