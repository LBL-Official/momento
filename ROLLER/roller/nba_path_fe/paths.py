"""On-disk layout. Matches FEATURE_ENGINEERING_SPEC.md §11."""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def library_root() -> Path:
    return repo_root() / "research" / "nba_path_trade_fe"


def features_registry_path() -> Path:
    return library_root() / "features" / "registry.yaml"


def raw_data_dir() -> Path:
    return library_root() / "data" / "raw"


def episodes_dir() -> Path:
    return library_root() / "data" / "episodes"


def features_dir() -> Path:
    return library_root() / "data" / "features"


def labels_dir() -> Path:
    return library_root() / "data" / "labels"


def artifacts_dir() -> Path:
    return library_root() / "artifacts"


def walkforward_summary_path() -> Path:
    return artifacts_dir() / "walkforward" / "summary.json"
