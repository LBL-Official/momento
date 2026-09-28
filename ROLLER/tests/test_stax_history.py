"""Historical STAX versions load persisted bytes. They must not re-execute."""

from __future__ import annotations

from roller.stax.api import handle_create, handle_export, handle_version
from roller.stax.runner import persist_run
from tests.stax_fixtures import envelope, source


def test_historical_version_read_does_not_execute(tmp_path, monkeypatch):
    created = handle_create(
        {"name": "NBA PATH RESEARCH", "members": [source(name="A"), source(name="B", question_hash="b")]},
        root=tmp_path,
    )
    stax_id = created["stax"]["stax_id"]

    def execute_question(_payload):
        return envelope(games=["G1", "G2"], dataset_version="ds-hist")

    persist_run(stax_id, created["members"], root=tmp_path, execute_question=execute_question)

    def boom(*_a, **_k):
        raise AssertionError("historical version must not execute")

    monkeypatch.setattr("roller.research_query.execute.execute_question", boom)
    monkeypatch.setattr(
        "roller.dashboard_adapter.research_executor.execute_research_object",
        boom,
    )
    rec = handle_version(stax_id, "1.0.0", root=tmp_path)
    assert rec["version"] == "1.0.0"
    assert rec["results"]
    assert rec["members"]
    pkg = handle_export(stax_id, "1.0.0", root=tmp_path)
    assert pkg["live_execution"] is False
    assert pkg["aggregation_method"] == "NONE"
    assert pkg["stax_version"] == "1.0.0"
