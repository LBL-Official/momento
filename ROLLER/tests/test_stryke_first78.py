"""Stryke sheet stays the 78/67 signal. Population pointers stay off Touch (N)."""

from roller.momento.execution import handle_nba_document
from roller.stryke.api import handle_folders, handle_health, handle_signal
from roller.stryke.artifact import PLACEHOLDER_LABELS, SHEET_ROWS
from roller.stryke.publish import publish


def test_sheet_matches_the_signal_and_keeps_n_apart():
    publish()
    health = handle_health()
    assert health["book"] == "FIRST78_67"
    assert health["live_execution"] is False
    assert health["execution_authorized"] is False
    body = handle_signal("FIRST78_67")
    rows = {row["label"]: row["value"] for row in body["rows"]}
    assert rows["Entry"] == "78"
    assert rows["Exit"] == "67"
    assert rows["Top Out"] == "85"
    assert rows["Touch (N)"] == "1"
    assert rows["Batch (N)"] == "10"
    assert rows["Allocation"] == "0.06"
    assert rows["Hedge"] == "Limit @ 68"
    assert rows["Hedge Path"] == "68,67,66,65,64,63,62,61,60,59,58,57,56,55"
    assert rows["Market Dump"] == "<55"
    for label in PLACEHOLDER_LABELS:
        assert rows[label] == "[Placeholder]"
    assert [tuple(item) for item in ((row["label"], row["value"]) for row in body["rows"])] == list(SHEET_ROWS)
    assert body["pointers"]["choosin"]["universe"] == "DERIVED_FOUR_FIRST78"
    assert body["pointers"]["choosin"]["n"] == 854
    assert body["pointers"]["austin"]["universe"] == "choosin_nba_2q3q_first78_67"
    assert body["pointers"]["austin"]["n"] == 569
    assert rows["Touch (N)"] not in {"854", "569", "936", "604"}


def test_jump_folder_is_the_membership_pointer():
    folders = handle_folders()["folders"]
    assert len(folders) == 1
    assert folders[0]["folder_id"] == "FIRST78_67"
    assert folders[0]["population_n"] == 936


def test_bot_reads_the_sheet_and_stays_closed(monkeypatch, tmp_path):
    fixture = tmp_path / "inspect.json"
    fixture.write_text('{"ok": true, "unit_file_exists": false, "unit": {"LoadState": "not-found"}}')
    monkeypatch.setenv("MOMENTO_NBA001_INSPECT_FIXTURE", str(fixture))
    monkeypatch.setattr(
        "roller.systimo.scope.get_session",
        lambda session_id, store=None: {"sport": "NBA", "quadrant_id": "quad-1", "session_id": session_id},
    )
    runtime = handle_nba_document("runtime", "nba")
    assert runtime["runtime"] == "NOT_DEPLOYED"
    assert runtime["execution_authorized"] is False
    assert runtime["submits"] is False
    assert runtime["listens_to"] == "signal_generation"
    rows = {row["label"]: row["value"] for row in runtime["signal"]["rows"]}
    assert rows["Entry"] == "78"
    assert rows["Exit"] == "67"
    assert rows["Touch (N)"] == "1"
