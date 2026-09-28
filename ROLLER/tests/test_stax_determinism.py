"""Same saved STAX + same dataset fingerprint → same hashes."""

from __future__ import annotations

from roller.stax.api import handle_create
from roller.stax.membership import definition_hash
from roller.stax.runner import persist_run
from tests.stax_fixtures import envelope, source


def test_same_definition_same_dataset_same_hashes(tmp_path):
    srcs = [source(name="A"), source(name="B", question_hash="b")]
    a = handle_create({"name": "A", "members": srcs}, root=tmp_path)
    b = handle_create({"name": "B", "members": srcs}, root=tmp_path / "other")
    assert definition_hash(a["members"]) == definition_hash(b["members"])

    def execute_question(_payload):
        return envelope(games=["G1"], dataset_version="frozen-ds")

    va = persist_run(a["stax"]["stax_id"], a["members"], root=tmp_path, execute_question=execute_question)
    vb = persist_run(b["stax"]["stax_id"], b["members"], root=tmp_path / "other", execute_question=execute_question)
    assert va["definition_hash"] == vb["definition_hash"]
    assert va["dataset_fingerprint"] == vb["dataset_fingerprint"]
    again = persist_run(a["stax"]["stax_id"], a["members"], root=tmp_path, execute_question=execute_question)
    assert again.get("unchanged") is True
