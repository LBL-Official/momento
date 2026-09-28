"""Daily re-execution of the fixed saved spec. No date expansion."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from roller.stax.api import handle_automation, handle_create
from roller.stax.automation import arm_automation, next_run_at, run_due
from roller.stax.library import load_head, load_version
from roller.stax.runner import persist_run
from tests.stax_fixtures import envelope, source


def test_schedule_timezone_and_no_window_expansion(tmp_path):
    created = handle_create(
        {
            "name": "NBA PATH RESEARCH",
            "timezone": "America/Los_Angeles",
            "members": [source(name="A", date_from="2025-10-10", date_to="2026-06-13")],
        },
        root=tmp_path,
    )
    stax_id = created["stax"]["stax_id"]
    members = created["members"]
    assert members[0]["universe"]["date_to"] == "2026-06-13"

    def execute_question(payload):
        uni = payload["question"]["universe"]
        assert uni["date_from"] == "2025-10-10"
        assert uni["date_to"] == "2026-06-13"
        env = envelope(games=["G1"], dataset_version="ds-auto-1")
        env["compile"] = {"question": {"universe": uni}}
        return env

    persist_run(stax_id, members, root=tmp_path, execute_question=execute_question)
    armed = handle_automation(
        stax_id,
        {"enabled": True, "timezone": "America/Los_Angeles", "schedule": "00:00"},
        root=tmp_path,
    )
    assert armed["automation_enabled"] is True
    assert armed["timezone"] == "America/Los_Angeles"
    assert armed["schedule"] == "00:00"
    assert armed["live_execution"] is False
    assert "NOT EXECUTION" in armed["message"]
    head = load_head(stax_id, root=tmp_path)
    after = datetime(2026, 9, 11, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
    nxt = next_run_at("America/Los_Angeles", "00:00", after=after)
    assert nxt.tzinfo is not None
    assert str(nxt.tzinfo) == "America/Los_Angeles"
    assert nxt.hour == 0 and nxt.minute == 0
    raw_v1 = (tmp_path / stax_id / "versions" / "v1.0.0" / "version.json").read_text()

    def execute_question2(payload):
        uni = payload["question"]["universe"]
        assert uni["date_to"] == "2026-06-13"
        env = envelope(games=["G1", "G2"], dataset_version="ds-auto-2")
        env["compile"] = {"question": {"universe": uni}}
        return env

    out = run_due(stax_id, root=tmp_path, now=after, run_stack=lambda ms: __import__("roller.stax.executor", fromlist=["execute_stack"]).execute_stack(ms, execute_question=execute_question2))
    assert out["version"] == "1.0.1"
    assert out["kind"] == "PATCH"
    assert load_version(stax_id, "1.0.0", root=tmp_path)["members"][0]["universe"]["date_to"] == "2026-06-13"
    assert (tmp_path / stax_id / "versions" / "v1.0.0" / "version.json").read_text() == raw_v1
    assert head["working_members"][0]["universe"]["date_to"] == "2026-06-13"


def test_automation_same_dataset_writes_run_without_empty_version(tmp_path):
    created = handle_create(
        {
            "name": "NBA PATH RESEARCH",
            "timezone": "America/Los_Angeles",
            "members": [source(name="A", date_from="2025-10-10", date_to="2026-06-13")],
        },
        root=tmp_path,
    )
    stax_id = created["stax"]["stax_id"]

    def execute_question(payload):
        uni = payload["question"]["universe"]
        assert uni["date_from"] == "2025-10-10"
        assert uni["date_to"] == "2026-06-13"
        env = envelope(games=["G1"], dataset_version="ds-same")
        env["compile"] = {"question": {"universe": uni}}
        return env

    persist_run(stax_id, created["members"], root=tmp_path, execute_question=execute_question)
    handle_automation(stax_id, {"enabled": True, "timezone": "America/Los_Angeles", "schedule": "00:00"}, root=tmp_path)
    raw = (tmp_path / stax_id / "versions" / "v1.0.0" / "version.json").read_bytes()
    after = datetime(2026, 9, 12, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
    out = run_due(
        stax_id,
        root=tmp_path,
        now=after,
        run_stack=lambda ms: __import__("roller.stax.executor", fromlist=["execute_stack"]).execute_stack(
            ms, execute_question=execute_question
        ),
    )
    assert out.get("unchanged") is True
    assert out["version"] == "1.0.0"
    assert (tmp_path / stax_id / "versions" / "v1.0.0" / "version.json").read_bytes() == raw
    assert not (tmp_path / stax_id / "versions" / "v1.0.1").exists()
    assert out["run"]["execution_id"]
    assert out["run"]["timezone"] == "America/Los_Angeles"
    assert (tmp_path / stax_id / "runs" / f"{out['run']['execution_id']}.json").is_file()


def test_arm_sets_next_run():
    head = {
        "stax_id": "STAX-0001",
        "automation_enabled": False,
        "timezone": "America/Los_Angeles",
        "automation_schedule": "00:00",
    }
    now = datetime(2026, 9, 11, 8, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
    armed = arm_automation(head, enabled=True, now=now)
    assert armed["next_run_at"]
    assert armed["automation_enabled"] is True
