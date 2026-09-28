"""Immutable versions. definition_hash vs dataset fingerprint."""

from __future__ import annotations

from roller.stax.api import handle_create, handle_validate
from roller.stax.library import load_version
from roller.stax.runner import persist_run
from roller.stax.versioning import classify_bump, compare_versions
from tests.stax_fixtures import envelope, source


def test_classify_bump_rules():
    parent = {"definition_hash": "ABC", "dataset_fingerprint": "X", "version": "1.0.0"}
    assert classify_bump(parent, definition_hash_value="ABC", dataset_fingerprint="Y") == "PATCH"
    assert classify_bump(parent, definition_hash_value="DEF", dataset_fingerprint="Z") == "MINOR"
    assert classify_bump(parent, definition_hash_value="ABC", dataset_fingerprint="X") is None


def test_versions_immutable_and_compare(tmp_path):
    created = handle_create(
        {"name": "NBA PATH RESEARCH", "members": [source(name="A"), source(name="B", question_hash="b")]},
        root=tmp_path,
    )
    stax_id = created["stax"]["stax_id"]

    def exec_ds(ds: str, extra_game: str = "G1"):
        def execute_question(_payload):
            return envelope(games=["GAME-SHARED", extra_game], dataset_version=ds)

        return execute_question

    v1 = persist_run(stax_id, created["members"], root=tmp_path, execute_question=exec_ds("ds-x"))
    assert v1["version"] == "1.0.0"
    assert v1["kind"] == "MINOR"
    raw_v1 = (tmp_path / stax_id / "versions" / "v1.0.0" / "version.json").read_text()

    v1b = persist_run(stax_id, created["members"], root=tmp_path, execute_question=exec_ds("ds-y"))
    assert v1b["version"] == "1.0.1"
    assert v1b["kind"] == "PATCH"
    assert v1b["definition_hash"] == v1["definition_hash"]
    assert (tmp_path / stax_id / "versions" / "v1.0.0" / "version.json").read_text() == raw_v1

    handle_validate(
        stax_id,
        {"add": source(name="C", question_hash="c")},
        root=tmp_path,
    )
    from roller.stax.library import load_head

    members = load_head(stax_id, root=tmp_path)["working_members"]
    v2 = persist_run(stax_id, members, root=tmp_path, execute_question=exec_ds("ds-y", "G3"))
    assert v2["version"] == "1.1.0"
    assert v2["kind"] == "MINOR"
    older = load_version(stax_id, "1.0.1", root=tmp_path)
    newer = load_version(stax_id, "1.1.0", root=tmp_path)
    diff = compare_versions(older, newer)
    assert diff["added"][0]["member_id"]
    assert not diff["removed"]
    assert (tmp_path / stax_id / "versions" / "v1.0.0" / "version.json").read_text() == raw_v1


def _version_bytes(root, stax_id: str, version: str) -> bytes:
    dest = root / stax_id / "versions" / f"v{version}"
    parts = []
    for path in sorted(dest.rglob("*")):
        if path.is_file():
            parts.append(path.relative_to(dest).as_posix().encode())
            parts.append(path.read_bytes())
    return b"\n".join(parts)


def test_same_definition_same_dataset_mints_no_version(tmp_path):
    created = handle_create(
        {"name": "NBA PATH RESEARCH", "members": [source(name="A"), source(name="B", question_hash="b")]},
        root=tmp_path,
    )
    stax_id = created["stax"]["stax_id"]

    def execute_question(_payload):
        return envelope(games=["GAME-SHARED", "G1"], dataset_version="ds-x")

    persist_run(stax_id, created["members"], root=tmp_path, execute_question=execute_question)
    raw = _version_bytes(tmp_path, stax_id, "1.0.0")
    again = persist_run(stax_id, created["members"], root=tmp_path, execute_question=execute_question)
    assert again.get("unchanged") is True
    assert again["version"] == "1.0.0"
    assert _version_bytes(tmp_path, stax_id, "1.0.0") == raw
    assert not (tmp_path / stax_id / "versions" / "v1.0.1").exists()


def test_reorder_is_minor_and_keeps_member_id(tmp_path):
    created = handle_create(
        {"name": "NBA PATH RESEARCH", "members": [source(name="A"), source(name="B", question_hash="b")]},
        root=tmp_path,
    )
    stax_id = created["stax"]["stax_id"]

    def execute_question(_payload):
        return envelope(games=["G1"], dataset_version="ds-x")

    persist_run(stax_id, created["members"], root=tmp_path, execute_question=execute_question)
    raw = _version_bytes(tmp_path, stax_id, "1.0.0")
    first_id = created["members"][0]["member_id"]
    handle_validate(stax_id, {"order": [created["members"][1]["member_id"], first_id]}, root=tmp_path)
    from roller.stax.library import load_head

    members = load_head(stax_id, root=tmp_path)["working_members"]
    v2 = persist_run(stax_id, members, root=tmp_path, execute_question=execute_question)
    assert v2["version"] == "1.1.0"
    assert v2["kind"] == "MINOR"
    by_id = {m["member_id"]: m for m in v2["members"]}
    assert by_id[first_id]["position"] == 2
    assert _version_bytes(tmp_path, stax_id, "1.0.0") == raw
