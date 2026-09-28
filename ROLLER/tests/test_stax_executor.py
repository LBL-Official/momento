"""Independent envelopes. PARTIAL keeps failed members."""

from __future__ import annotations

from roller.stax.executor import execute_stack
from roller.stax.membership import add_member
from roller.stax.overlap import INDEPENDENCE_NOTE
from tests.stax_fixtures import envelope, source


def test_three_independent_envelopes():
    members = []
    for i, name in enumerate(("A", "B", "C"), start=1):
        members = add_member(members, source(name=name, question_hash=name), stax_id="STAX-0001", member_seq=i)

    def execute_question(payload):
        qh = payload["question"]["universe"]["date_from"]
        return envelope(games=[f"{qh}-{payload['question']['terminal']}"], dataset_version="ds-1")

    out = execute_stack(members, execute_question=execute_question)
    assert out["strategy_count"] == 3
    assert len(out["results"]) == 3
    ids = [id(r["envelope"]) for r in out["results"]]
    assert len(set(ids)) == 3
    assert out["aggregation_method"] == "NONE"
    assert out["sum_of_strategy_n_label"] == "SUM OF PER-STRATEGY N"


def test_one_failure_is_partial_and_visible():
    members = []
    for i, name in enumerate(("A", "B", "C"), start=1):
        members = add_member(members, source(name=name, question_hash=name), stax_id="STAX-0001", member_seq=i)

    def execute_question(payload):
        if members[1]["question"] is payload.get("question") or payload["question"] == members[1]["question"]:
            raise RuntimeError("DATA_REQUIRED: object unavailable")
        return envelope(games=["G1"], dataset_version="ds-1")

    # Identify second member by mutating a sentinel on the question
    members[1]["question"] = {**members[1]["question"], "terminal": "YES"}

    def execute_question(payload):
        if payload.get("question", {}).get("terminal") == "YES":
            raise RuntimeError("DATA_REQUIRED: object unavailable")
        return envelope(games=["G1"], dataset_version="ds-1")

    out = execute_stack(members, execute_question=execute_question)
    assert out["status"] == "PARTIAL"
    assert out["failed_count"] == 1
    assert out["completed_count"] == 2
    failed = [r for r in out["results"] if r["status"] != "COMPLETE"]
    assert failed[0]["member_id"] == members[1]["member_id"]
    assert failed[0]["status"] in {"FAILED", "DATA_REQUIRED"}
    assert failed[0]["summary"]["n"] is None


def test_overlap_shared_game():
    members = []
    members = add_member(members, source(name="A"), stax_id="STAX-0001", member_seq=1)
    members = add_member(members, source(name="B", question_hash="b"), stax_id="STAX-0001", member_seq=2)
    n = {"n": 0}

    def execute_question(_payload):
        n["n"] += 1
        games = ["GAME-SHARED", f"GAME-{n['n']}"]
        return envelope(games=games, dataset_version="ds-1")

    out = execute_stack(members, execute_question=execute_question)
    overlap = out["overlap"]
    assert overlap["overlap_method"] == "INTERNAL_GAME_ID"
    assert overlap["independence_claim"] is False
    assert INDEPENDENCE_NOTE in overlap["note"]
    assert overlap["shared_game_count"] == 1
    assert overlap["pairwise"][0]["shared_game_count"] == 1


def test_n_comes_from_population_count_not_preview():
    members = add_member([], source(name="A"), stax_id="STAX-0001", member_seq=1)

    def execute_question(_payload):
        env = envelope(games=[f"G{i}" for i in range(384)], dataset_version="ds-1")
        env["population"]["rows"] = env["population"]["trades"][:200]
        env["population"]["rows_truncated"] = True
        env["summary"]["population_n"] = 384
        return env

    out = execute_stack(members, execute_question=execute_question)
    assert out["results"][0]["status"] == "COMPLETE"
    assert out["results"][0]["summary"]["n"] == 384
    assert len(out["results"][0]["envelope"]["population"]["rows"]) == 200


def test_truncated_rows_without_count_are_data_required():
    members = add_member([], source(name="A"), stax_id="STAX-0001", member_seq=1)

    def execute_question(_payload):
        rows = [{"internal_game_id": f"G{i}"} for i in range(200)]
        return {
            "execution_status": "COMPLETE",
            "summary": {},
            "population": {"rows": rows, "rows_truncated": True},
            "dataset_version": "ds-1",
            "hashes": {},
            "measurements": [],
            "analysis": {},
        }

    out = execute_stack(members, execute_question=execute_question)
    assert out["results"][0]["status"] == "DATA_REQUIRED"
    assert out["results"][0]["summary"]["n"] is None


def test_preview_mismatch_makes_overlap_unavailable():
    members = add_member([], source(name="A"), stax_id="STAX-0001", member_seq=1)
    members = add_member(members, source(name="B", question_hash="b"), stax_id="STAX-0001", member_seq=2)

    def execute_question(_payload):
        env = envelope(games=["G1", "G2"], dataset_version="ds-1")
        env["population"]["count"] = 2
        env["population"]["trades"] = env["population"]["trades"][:1]
        return env

    out = execute_stack(members, execute_question=execute_question)
    assert out["overlap"]["overlap_method"] == "UNAVAILABLE"
    assert out["overlap"]["independence_claim"] is False
