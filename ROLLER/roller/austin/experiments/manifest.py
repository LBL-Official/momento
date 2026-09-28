"""Pin and verify the frozen NBA Austin model. NCAAB never enters the fit."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roller.austin.config import DEFAULT
from roller.austin.errors import AustinError
from roller.austin.experiments.ids import BOOTSTRAP_B, BOOTSTRAP_SEED, CI_METHOD, EV_DEFINITION, OBSERVATION_SCHEDULE
from roller.austin.paths import (
    features_registry_path,
    model_dir,
    model_manifest_path,
    snapshots_path,
    trades_path,
)
from roller.austin.store import load_json, load_snapshots, load_trades_frame, write_json


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


LOCKED_HASHES = {
    "snapshots.parquet": "55b6fa791dda6dc00bc79e4f392266ce985b78581f4a4bd43b733a488aa6aac0",
    "trades.parquet": "93497e3cd7f67ba7d20c0481273c2b0c61585a530f6e377ceea40c18549d0500",
    "pca.json": "2d5fcaf80a4871769d8febebad987b87ab814da975ac3476e831e6d8c66b5225",
    "pca.npz": "d56cd7eaf7bc48134aae7121160420ccc24581ec403be51508f0c614c5e27bf9",
    "registry.yaml": "ebd49948320720f7f8acb15ae46a03d5fc703c8c0f29a6be9e52f3d4442031ab",
}
LOCKED_MANIFEST_HASH = "4a47bf9ad3a2fcd4bb092a77cf93d534e308423deec29e33b6e6bad85c76431c"


def _git_root(start: Path) -> Path | None:
    here = start.resolve()
    for path in (here, *here.parents):
        if (path / ".git").exists():
            return path
    return None


def resolve_git_commit() -> dict[str, str]:
    """Pin the experiment code commit. Never silently swallow UNAVAILABLE."""
    root = _git_root(Path(__file__).resolve())
    if root is None:
        return {
            "git_commit": "UNAVAILABLE",
            "git_commit_status": "UNAVAILABLE",
            "git_commit_reason": "not_a_git_repo",
        }
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            stderr=subprocess.STDOUT,
        )
        sha = out.decode("utf-8").strip()
        if not sha:
            return {
                "git_commit": "UNAVAILABLE",
                "git_commit_status": "UNAVAILABLE",
                "git_commit_reason": "command_failed:empty_rev_parse",
            }
        return {
            "git_commit": sha,
            "git_commit_status": "RESOLVED",
            "git_commit_reason": sha,
        }
    except FileNotFoundError:
        return {
            "git_commit": "UNAVAILABLE",
            "git_commit_status": "UNAVAILABLE",
            "git_commit_reason": "git_not_found",
        }
    except subprocess.CalledProcessError as exc:
        detail = (exc.output or b"").decode("utf-8", errors="replace").strip() or str(exc)
        return {
            "git_commit": "UNAVAILABLE",
            "git_commit_status": "UNAVAILABLE",
            "git_commit_reason": f"command_failed:{detail[:240]}",
        }
    except OSError as exc:
        return {
            "git_commit": "UNAVAILABLE",
            "git_commit_status": "UNAVAILABLE",
            "git_commit_reason": f"command_failed:{exc}",
        }


def git_commit() -> str:
    return resolve_git_commit()["git_commit"]


def build_model_manifest() -> dict[str, Any]:
    snaps = snapshots_path()
    trades = trades_path()
    pca_json = model_dir() / "pca.json"
    pca_npz = model_dir() / "pca.npz"
    registry = features_registry_path()
    missing = [str(p) for p in (snaps, trades, pca_json, pca_npz, registry) if not p.is_file()]
    if missing:
        raise AustinError("DATA_REQUIRED", f"Austin model artifacts missing: {missing}")
    snap_n = int(len(load_snapshots()))
    trade_n = int(len(load_trades_frame()))
    if trade_n != 604:
        raise AustinError("LOCK_MISMATCH", f"training N_trades={trade_n} != 604")
    payload = {
        "model_version": DEFAULT.model_version,
        "dataset_version": DEFAULT.dataset_version,
        "feature_schema_version": DEFAULT.feature_schema_version,
        "pca_version": DEFAULT.pca_version,
        "knn_k": DEFAULT.k_default,
        "distance_metric": "euclidean_pca",
        "ev_definition": EV_DEFINITION,
        "ci_method": CI_METHOD,
        "ci_seed": BOOTSTRAP_SEED,
        "ci_B": BOOTSTRAP_B,
        "observation_schedule": OBSERVATION_SCHEDULE,
        "training_n_trades": trade_n,
        "training_n_snapshots": snap_n,
        "ncaab_used_for_training": False,
        "ncaab_used_for_pca": False,
        "ncaab_used_for_scaler": False,
        "ncaab_used_for_knn": False,
        "hashes": {
            "snapshots.parquet": sha256_file(snaps),
            "trades.parquet": sha256_file(trades),
            "pca.json": sha256_file(pca_json),
            "pca.npz": sha256_file(pca_npz),
            "registry.yaml": sha256_file(registry),
        },
        **resolve_git_commit(),
        "built_at": datetime.now(timezone.utc).isoformat(),
    }
    payload["model_manifest_hash"] = hashlib.sha256(
        json.dumps(payload["hashes"], sort_keys=True).encode("utf-8")
    ).hexdigest()
    payload["feature_schema_hash"] = payload["hashes"]["registry.yaml"]
    if payload["hashes"] != LOCKED_HASHES:
        raise AustinError("LOCK_MISMATCH", "Austin model artifact hashes drifted from the experiment lock")
    if payload["model_manifest_hash"] != LOCKED_MANIFEST_HASH:
        raise AustinError("LOCK_MISMATCH", "model_manifest_hash drifted from the experiment lock")
    return payload


def persist_model_manifest() -> dict[str, Any]:
    payload = build_model_manifest()
    write_json(model_manifest_path(), payload)
    return payload


def load_model_manifest() -> dict[str, Any]:
    path = model_manifest_path()
    if not path.is_file():
        return persist_model_manifest()
    return load_json(path)


def verify_model_manifest() -> dict[str, Any]:
    current = build_model_manifest()
    stored = load_json(model_manifest_path(), required=False)
    if not stored:
        write_json(model_manifest_path(), current)
        return current
    if stored.get("hashes") != current["hashes"]:
        raise AustinError("LOCK_MISMATCH", "Austin model hash mismatch. NCAAB experiment refuses to proceed.")
    if int(current["training_n_trades"]) != 604:
        raise AustinError("LOCK_MISMATCH", "training lock N != 604")
    if int(current["training_n_snapshots"]) != 48752:
        raise AustinError("LOCK_MISMATCH", f"snapshot matrix {current['training_n_snapshots']} != 48752")
    return {**stored, "verified": True, "model_manifest_hash": current["model_manifest_hash"]}
