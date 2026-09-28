"""Artifact root for the 78/67 Austin fit. Not research/austin/artifacts."""

from __future__ import annotations

from pathlib import Path

from roller.austin.paths import repo_root


def library_root() -> Path:
    return repo_root() / "research" / "austin" / "first78_67"


def artifacts_dir() -> Path:
    return library_root() / "artifacts"


def dataset_dir() -> Path:
    return artifacts_dir() / "dataset"


def trades_path() -> Path:
    return dataset_dir() / "trades.parquet"


def snapshots_path() -> Path:
    return dataset_dir() / "snapshots.parquet"


def coverage_path() -> Path:
    return dataset_dir() / "coverage.json"


def model_dir() -> Path:
    return artifacts_dir() / "model"


def summary_path() -> Path:
    return artifacts_dir() / "summary.json"


def walkforward_path() -> Path:
    return artifacts_dir() / "walkforward.json"


def hedge_path() -> Path:
    return artifacts_dir() / "hedge.json"


def sizing_path() -> Path:
    return artifacts_dir() / "sizing.json"


def audit_path() -> Path:
    return artifacts_dir() / "audit.json"


def integrity_audit_path() -> Path:
    return artifacts_dir() / "integrity_audit.json"


def calibration_path() -> Path:
    return artifacts_dir() / "calibration.json"
