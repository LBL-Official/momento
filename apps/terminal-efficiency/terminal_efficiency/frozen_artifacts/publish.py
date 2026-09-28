"""One-time freeze index writer. Not imported by the consumption loader."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from terminal_efficiency.frozen_artifacts.spec import FREEZE_SPECS


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def warehouse_derived(data_root: Path, league: str, season: str) -> Path:
    sport = "nba" if league.upper() == "NBA" else "ncaab"
    return data_root / league.upper() / season / "warehouse" / "derived" / sport / "terminal_efficiency"


def build_manifest(data_root: Path, spec: dict[str, Any]) -> dict[str, Any]:
    dest = warehouse_derived(data_root, spec["league"], spec["season"])
    pred = dest / spec["prediction_file"]
    model = dest / spec["frozen_model_file"]
    if not pred.is_file():
        raise FileNotFoundError(f"frozen prediction missing: {pred}")
    if not model.is_file():
        raise FileNotFoundError(f"frozen model artifact missing: {model}")
    payload = dict(spec)
    payload["prediction_sha256"] = sha256_file(pred)
    payload["frozen_model_sha256"] = sha256_file(model)
    digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    payload["artifact_manifest_hash"] = digest
    return payload


def write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def publish(data_root: Path, package_manifest_dir: Path) -> list[dict[str, Any]]:
    out = []
    for spec in FREEZE_SPECS:
        payload = build_manifest(data_root, spec)
        name = f"{payload['league']}_{payload['season']}_{payload['model_version']}.json"
        write_manifest(package_manifest_dir / name, payload)
        dest = warehouse_derived(data_root, payload["league"], payload["season"])
        write_manifest(dest / "frozen_artifacts" / "manifests" / name, payload)
        out.append(payload)
    return out
