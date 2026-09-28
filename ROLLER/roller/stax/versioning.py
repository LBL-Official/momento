"""Immutable STAX versions. Compare by member_id."""

from __future__ import annotations

from typing import Any

from roller.stax.membership import definition_hash
from roller.stax.models import KIND_MAJOR, KIND_MINOR, KIND_PATCH, bump_version


def classify_bump(
    parent: dict[str, Any] | None,
    *,
    definition_hash_value: str,
    dataset_fingerprint: str,
    schema_changed: bool = False,
) -> str | None:
    if schema_changed:
        return KIND_MAJOR
    if parent is None:
        return KIND_MINOR
    parent_def = str(parent.get("definition_hash") or "")
    parent_data = str(parent.get("dataset_fingerprint") or "")
    if definition_hash_value != parent_def:
        return KIND_MINOR
    if dataset_fingerprint != parent_data:
        return KIND_PATCH
    return None


def next_version_record(
    parent: dict[str, Any] | None,
    *,
    definition_hash_value: str,
    dataset_fingerprint: str,
    schema_changed: bool = False,
) -> dict[str, Any] | None:
    kind = classify_bump(
        parent,
        definition_hash_value=definition_hash_value,
        dataset_fingerprint=dataset_fingerprint,
        schema_changed=schema_changed,
    )
    if kind is None:
        return None
    parent_version = parent.get("version") if parent else None
    return {
        "version": bump_version(parent_version, kind=kind),
        "kind": kind,
        "parent_version": parent_version,
        "definition_hash": definition_hash_value,
        "dataset_fingerprint": dataset_fingerprint,
    }


def compare_versions(older: dict[str, Any], newer: dict[str, Any]) -> dict[str, Any]:
    old_members = {m["member_id"]: m for m in older.get("members") or []}
    new_members = {m["member_id"]: m for m in newer.get("members") or []}
    added = [new_members[i] for i in new_members if i not in old_members]
    removed = [old_members[i] for i in old_members if i not in new_members]
    changed = []
    unchanged = []
    reordered = []
    for mid, new in new_members.items():
        old = old_members.get(mid)
        if not old:
            continue
        def_changed = (old.get("question_hash") or old.get("query_hash")) != (
            new.get("question_hash") or new.get("query_hash")
        ) or (old.get("research_spec") or {}) != (new.get("research_spec") or {})
        data_changed = (old.get("dataset_hash") or old.get("dataset_version")) != (
            new.get("dataset_hash") or new.get("dataset_version")
        )
        if old.get("position") != new.get("position") and not def_changed:
            reordered.append({"member_id": mid, "from": old.get("position"), "to": new.get("position")})
        if def_changed or data_changed:
            changed.append(
                {
                    "member_id": mid,
                    "definition_changed": def_changed,
                    "dataset_changed": data_changed,
                }
            )
        else:
            unchanged.append(mid)
    return {
        "from": older.get("version"),
        "to": newer.get("version"),
        "added": [{"member_id": m.get("member_id"), "label": m.get("label")} for m in added],
        "removed": [{"member_id": m.get("member_id"), "label": m.get("label")} for m in removed],
        "changed": changed,
        "reordered": reordered,
        "unchanged": unchanged,
        "definition_hash_changed": older.get("definition_hash") != newer.get("definition_hash"),
        "dataset_fingerprint_changed": older.get("dataset_fingerprint") != newer.get("dataset_fingerprint"),
    }


def version_members_hash(members: list[dict[str, Any]]) -> str:
    return definition_hash(members)
