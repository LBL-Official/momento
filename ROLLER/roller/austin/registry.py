"""Load research/austin/features/registry.yaml. No PyYAML dependency."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from roller.austin.errors import AustinError
from roller.austin.paths import features_registry_path


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    description: str
    source: str
    unit: str
    availability: str
    transform: str
    normalization: str
    used_in_pca: bool
    used_in_knn: bool
    outcome_derived: bool


def _parse_scalar(raw: str) -> Any:
    text = raw.strip()
    if text.startswith('"') and text.endswith('"'):
        return text[1:-1]
    if text in {"true", "false"}:
        return text == "true"
    if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
        return int(text)
    return text


def load_registry(path: Path | None = None) -> dict[str, Any]:
    src = path or features_registry_path()
    if not src.is_file():
        raise AustinError("REGISTRY_REQUIRED", f"missing {src}")
    features: list[FeatureSpec] = []
    version: int | None = None
    schema = ""
    default_knn: list[str] = []
    current: dict[str, Any] | None = None
    in_knn = False
    for raw_line in src.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line.startswith("version:"):
            version = int(line.split(":", 1)[1].strip())
            in_knn = False
            continue
        if line.startswith("feature_schema_version:"):
            schema = str(_parse_scalar(line.split(":", 1)[1]))
            continue
        if line.strip() == "default_knn:":
            in_knn = True
            continue
        if in_knn and line.strip().startswith("- "):
            default_knn.append(str(_parse_scalar(line.strip()[2:])))
            continue
        if line.strip() == "features:":
            in_knn = False
            continue
        if line.startswith("  - "):
            if current:
                features.append(_spec_from_map(current))
            key, val = line[4:].split(":", 1)
            current = {key.strip(): _parse_scalar(val)}
            continue
        if line.startswith("    ") and current is not None and ":" in line:
            key, val = line.strip().split(":", 1)
            current[key.strip()] = _parse_scalar(val)
    if current:
        features.append(_spec_from_map(current))
    if version != 1:
        raise AustinError("REGISTRY_INVALID", f"unsupported version {version}")
    names = [f.name for f in features]
    if len(names) != len(set(names)):
        raise AustinError("REGISTRY_INVALID", "duplicate feature name")
    leaked = [f.name for f in features if f.outcome_derived and (f.used_in_pca or f.used_in_knn)]
    if leaked:
        raise AustinError("REGISTRY_INVALID", f"outcome leaked into PCA/KNN: {leaked}")
    by_name = {f.name: f for f in features}
    missing = [n for n in default_knn if n not in by_name]
    if missing:
        raise AustinError("REGISTRY_INVALID", f"default_knn missing {missing}")
    for name in default_knn:
        spec = by_name[name]
        if spec.outcome_derived:
            raise AustinError("REGISTRY_INVALID", f"default_knn outcome {name}")
    return {
        "version": version,
        "feature_schema_version": schema,
        "features": features,
        "by_name": by_name,
        "default_knn": list(default_knn),
        "pca_names": [f.name for f in features if f.used_in_pca and not f.outcome_derived],
        "knn_names": [f.name for f in features if f.used_in_knn and not f.outcome_derived],
    }


def _spec_from_map(row: dict[str, Any]) -> FeatureSpec:
    required = (
        "name",
        "description",
        "source",
        "unit",
        "availability",
        "transform",
        "normalization",
        "used_in_pca",
        "used_in_knn",
        "outcome_derived",
    )
    missing = [k for k in required if k not in row]
    if missing:
        raise AustinError("REGISTRY_INVALID", f"feature missing {missing}")
    return FeatureSpec(
        name=str(row["name"]),
        description=str(row["description"]),
        source=str(row["source"]),
        unit=str(row["unit"]),
        availability=str(row["availability"]),
        transform=str(row["transform"]),
        normalization=str(row["normalization"]),
        used_in_pca=bool(row["used_in_pca"]),
        used_in_knn=bool(row["used_in_knn"]),
        outcome_derived=bool(row["outcome_derived"]),
    )
