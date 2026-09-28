"""Load features/registry.yaml. Tiny schema parser — no PyYAML dependency."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from roller.nba_path_fe.errors import PathFeError
from roller.nba_path_fe.paths import features_registry_path


ALLOWED_USED_IN = frozenset({"enter_skip", "hedge_only", "both"})
ALLOWED_FAMILY = frozenset({"A", "B", "C", "D", "E"})


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    family: str
    kind: str
    used_in: str
    transform: str
    note: str


def _parse_scalar(raw: str) -> Any:
    text = raw.strip()
    if text.startswith('"') and text.endswith('"'):
        return text[1:-1]
    if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
        return int(text)
    return text


def load_registry(path: Path | None = None) -> dict[str, Any]:
    src = path or features_registry_path()
    if not src.is_file():
        raise PathFeError("REGISTRY_REQUIRED", f"missing {src}")
    features: list[FeatureSpec] = []
    version: int | None = None
    state_fair_version = ""
    current: dict[str, str] | None = None
    for raw_line in src.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line.startswith("version:"):
            version = int(line.split(":", 1)[1].strip())
            continue
        if line.startswith("state_fair_version:"):
            state_fair_version = line.split(":", 1)[1].strip()
            continue
        if line.strip() == "features:":
            continue
        if line.startswith("  - "):
            if current:
                features.append(_spec_from_map(current))
            key, val = line[4:].split(":", 1)
            current = {key.strip(): str(_parse_scalar(val))}
            continue
        if line.startswith("    ") and current is not None and ":" in line:
            key, val = line.strip().split(":", 1)
            current[key.strip()] = str(_parse_scalar(val))
    if current:
        features.append(_spec_from_map(current))
    if version != 1:
        raise PathFeError("REGISTRY_INVALID", f"unsupported version {version}")
    _validate(features)
    return {
        "version": version,
        "state_fair_version": state_fair_version,
        "features": features,
        "by_name": {f.name: f for f in features},
    }


def _spec_from_map(row: dict[str, str]) -> FeatureSpec:
    required = ("name", "family", "kind", "used_in", "transform", "note")
    missing = [k for k in required if k not in row]
    if missing:
        raise PathFeError("REGISTRY_INVALID", f"feature missing {missing}")
    return FeatureSpec(
        name=row["name"],
        family=row["family"],
        kind=row["kind"],
        used_in=row["used_in"],
        transform=row["transform"],
        note=row["note"],
    )


def _validate(features: list[FeatureSpec]) -> None:
    names: set[str] = set()
    for spec in features:
        if spec.name in names:
            raise PathFeError("REGISTRY_INVALID", f"duplicate {spec.name}")
        names.add(spec.name)
        if spec.family not in ALLOWED_FAMILY:
            raise PathFeError("REGISTRY_INVALID", f"family {spec.family}")
        if spec.used_in not in ALLOWED_USED_IN:
            raise PathFeError("REGISTRY_INVALID", f"used_in {spec.used_in}")
        if spec.family == "E" and spec.used_in != "hedge_only":
            raise PathFeError("REGISTRY_INVALID", f"Family E must be hedge_only: {spec.name}")
        if spec.used_in == "enter_skip" and spec.family == "E":
            raise PathFeError("REGISTRY_INVALID", f"E leaked into enter_skip: {spec.name}")
    required = {
        "impulse_x_disagreement",
        "thin_x_disagreement",
        "state_fair_price",
        "price_minus_state_fair",
        "book_features_missing",
    }
    missing = required - names
    if missing:
        raise PathFeError("REGISTRY_INVALID", f"required features missing: {sorted(missing)}")


def enter_skip_names(registry: dict[str, Any] | None = None) -> list[str]:
    reg = registry or load_registry()
    return [
        f.name
        for f in reg["features"]
        if f.used_in in {"enter_skip", "both"} and f.family != "E"
    ]


def pca_names(registry: dict[str, Any] | None = None) -> list[str]:
    reg = registry or load_registry()
    return [
        f.name
        for f in reg["features"]
        if f.family in {"A", "B", "C"} and f.used_in in {"enter_skip", "both"}
    ]


def hedge_names(registry: dict[str, Any] | None = None) -> list[str]:
    reg = registry or load_registry()
    return [f.name for f in reg["features"] if f.family == "E"]
