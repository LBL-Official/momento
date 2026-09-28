"""In-process semantic cache. Invalidates on dataset_version change.

Never claims warehouse_frozen_v1. Never serves a hash after version change.
"""

from __future__ import annotations

from typing import Any

_warehouse: dict[tuple[str, str], tuple[Any, Any, Any, Any]] = {}
_index: dict[tuple[str, str], Any] = {}
_entry: dict[tuple[str, str], dict[str, Any]] = {}
_path: dict[tuple[str, str, str], list[dict[str, Any]]] = {}


def clear() -> None:
    _warehouse.clear()
    _index.clear()
    _entry.clear()
    _path.clear()


def warehouse_key(universe_hash: str, dataset_version: str) -> tuple[str, str]:
    return (universe_hash, dataset_version)


def get_warehouse(universe_hash: str, dataset_version: str):
    return _warehouse.get(warehouse_key(universe_hash, dataset_version))


def put_warehouse(universe_hash: str, dataset_version: str, payload: tuple) -> None:
    _warehouse[warehouse_key(universe_hash, dataset_version)] = payload


def get_index(universe_hash: str, dataset_version: str):
    return _index.get(warehouse_key(universe_hash, dataset_version))


def put_index(universe_hash: str, dataset_version: str, index) -> None:
    _index[warehouse_key(universe_hash, dataset_version)] = index


def get_entry(entry_hash: str, dataset_version: str) -> dict[str, Any] | None:
    return _entry.get((entry_hash, dataset_version))


def put_entry(entry_hash: str, dataset_version: str, value: dict[str, Any]) -> None:
    _entry[(entry_hash, dataset_version)] = value


def get_path_rows(entry_hash: str, path_hash: str, dataset_version: str):
    return _path.get((entry_hash, path_hash, dataset_version))


def put_path_rows(
    entry_hash: str,
    path_hash: str,
    dataset_version: str,
    rows: list[dict[str, Any]],
) -> None:
    _path[(entry_hash, path_hash, dataset_version)] = rows
