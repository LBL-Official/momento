"""Persist the 78/67 Austin artifacts."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd

from roller.austin.errors import AustinError
from roller.austin_first78.paths import model_dir, snapshots_path, summary_path, trades_path


def write_json(path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=_json) + "\n", encoding="utf-8")


def _json(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    raise TypeError(type(value))


def save_pca_model(model: dict[str, Any]) -> None:
    model_dir().mkdir(parents=True, exist_ok=True)
    np.savez(model_dir() / "pca.npz", components=np.asarray(model["components"]))
    write_json(
        model_dir() / "pca.json",
        {
            "names": model["names"],
            "mu": model["mu"],
            "sd": model["sd"],
            "explained": model["explained"],
            "cumulative": model["cumulative"],
            "loadings": model["loadings"],
            "n": model["n"],
            "k": model["k"],
            "pca_version": model["pca_version"],
            "feature_schema_version": model["feature_schema_version"],
        },
    )


def load_json(path, *, required: bool = True) -> dict[str, Any] | None:
    if not path.is_file():
        if required:
            raise AustinError("DATA_REQUIRED", f"missing {path}")
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_pca_model() -> dict[str, Any]:
    meta = model_dir() / "pca.json"
    arr = model_dir() / "pca.npz"
    if not meta.is_file() or not arr.is_file():
        raise AustinError("DATA_REQUIRED", "78/67 PCA artifacts missing")
    payload = json.loads(meta.read_text(encoding="utf-8"))
    payload["components"] = np.load(arr)["components"]
    return payload


def load_snapshots() -> pd.DataFrame:
    if not snapshots_path().is_file():
        raise AustinError("DATA_REQUIRED", "78/67 snapshots missing")
    return pd.read_parquet(snapshots_path())


def load_trades_frame() -> pd.DataFrame:
    if not trades_path().is_file():
        raise AustinError("DATA_REQUIRED", "78/67 trades missing")
    return pd.read_parquet(trades_path())


def artifacts_present() -> bool:
    return summary_path().is_file() and (model_dir() / "pca.json").is_file()
