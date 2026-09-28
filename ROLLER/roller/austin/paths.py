"""On-disk Austin library layout."""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def library_root() -> Path:
    return repo_root() / "research" / "austin"


def features_registry_path() -> Path:
    return library_root() / "features" / "registry.yaml"


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


def contract_path() -> Path:
    return artifacts_dir() / "fort_worth_contract.json"


def integrity_audit_path() -> Path:
    return artifacts_dir() / "integrity_audit.json"


def calibration_path() -> Path:
    return artifacts_dir() / "calibration.json"


def experiments_root() -> Path:
    return library_root() / "experiments"


def model_manifest_path() -> Path:
    return experiments_root() / "_model" / "MODEL_MANIFEST.json"


def suite_dir() -> Path:
    return experiments_root() / "AUSTIN_NCAAB_TRANSFER_V1"


def suite_freeze_path() -> Path:
    return suite_dir() / "POLICY_FREEZE.json"


def experiment_dir(experiment_id: str) -> Path:
    return experiments_root() / experiment_id


def persistence_audit_dir() -> Path:
    return experiments_root() / "AUSTIN_PERSISTENCE_MECHANISM_AUDIT_V1"


def persistence_phase2_dir() -> Path:
    return experiments_root() / "AUSTIN_PERSISTENCE_MECHANISM_V1"


def downfall_phase3_dir() -> Path:
    return experiments_root() / "AUSTIN_DOWNFALL_STATE_MODEL_V1"


def hazard_phase4_dir() -> Path:
    return experiments_root() / "AUSTIN_LOSS_HAZARD_RECOVERY_MODEL_V1"


def policy_phase5_dir() -> Path:
    return experiments_root() / "AUSTIN_DRE_POLICY_V2"


def confirmation_gate_dir() -> Path:
    return experiments_root() / "AUSTIN_CONFIRMATION_GATE_V1"


def prospective_phase7_dir() -> Path:
    return experiments_root() / "AUSTIN_NBA_2026_27_PROSPECTIVE_V1"
