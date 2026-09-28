"""Real ROLLER objects through STAX. No manufactured envelopes."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from roller.research_library.saves import load_save, saves_dir
from roller.research_query.compiler import compile_question
from roller.research_query.models import ResearchQuestion
from roller.stax.api import handle_create, handle_export, handle_version
from roller.stax.compatibility import canonicalize_universe
from roller.stax.library import load_head
from roller.stax.runner import persist_run


SAVE_ID = "272ce62df766409292992a6878f7e6b3"


def _real_save() -> dict | None:
    path = saves_dir() / f"{SAVE_ID}.json"
    if not path.is_file():
        return None
    return load_save(SAVE_ID)


def _compiled_question(save: dict) -> dict:
    result = save.get("result") if isinstance(save.get("result"), dict) else {}
    compile_block = result.get("compile") if isinstance(result.get("compile"), dict) else {}
    question = compile_block.get("question")
    if not isinstance(question, dict):
        raise AssertionError("saved object has no compiled question")
    return question


def test_real_saved_objects_execute_independently(tmp_path):
    save = _real_save()
    if save is None:
        pytest.skip(f"real ROLLER save {SAVE_ID} is not on disk")

    q1 = _compiled_question(save)
    q2 = copy.deepcopy(q1)
    if not q2.get("path_conditions"):
        pytest.skip("saved object has no path condition to vary")
    q2["path_conditions"][0]["price_e4"] = 3500

    c1 = compile_question(ResearchQuestion.from_dict(q1))
    c2 = compile_question(ResearchQuestion.from_dict(q2))
    u1 = canonicalize_universe(c1.question.to_dict()["universe"])
    u2 = canonicalize_universe(c2.question.to_dict()["universe"])
    assert u1 == u2
    assert c1.question.to_dict() != c2.question.to_dict()

    created = handle_create(
        {
            "name": "STAX V1 ACCEPTANCE",
            "timezone": "America/Los_Angeles",
            "members": [
                {
                    "name": "S01 reach-40",
                    "id": save.get("id"),
                    "save_id": save.get("id"),
                    "question": c1.question.to_dict(),
                    "draft": save.get("workflow_draft"),
                    "result": save.get("result"),
                    "hashes": (save.get("result") or {}).get("hashes") or save.get("hashes"),
                },
                {
                    "name": "S02 reach-35",
                    "question": c2.question.to_dict(),
                    "hashes": {},
                },
                {
                    "name": "S03 missing object",
                    "question": c1.question.to_dict(),
                },
            ],
        },
        root=tmp_path,
    )
    stax_id = created["stax"]["stax_id"]
    members = created["members"]
    assert [m["member_id"] for m in members] == ["STXM-0001", "STXM-0002", "STXM-0003"]
    members[2]["question"] = None
    members[2]["draft"] = None
    members[2]["research_spec"] = {}

    out = persist_run(stax_id, members, root=tmp_path)
    assert out["version"] == "1.0.0"
    assert out["status"] == "PARTIAL"
    assert out["aggregation_method"] == "NONE"
    assert out["live_execution"] is False

    by_id = {r["member_id"]: r for r in out["results"]}
    s01 = by_id["STXM-0001"]
    s02 = by_id["STXM-0002"]
    s03 = by_id["STXM-0003"]
    assert s01["status"] == "COMPLETE"
    assert s02["status"] == "COMPLETE"
    assert s03["status"] == "DATA_REQUIRED"
    assert s03["summary"]["n"] is None
    assert s01["envelope"] is not s02["envelope"]
    assert s01["summary"]["n"] == s01["envelope"]["population"]["count"]
    assert s02["summary"]["n"] == s02["envelope"]["population"]["count"]
    saved_n = (save.get("result") or {}).get("population", {}).get("count")
    assert s01["summary"]["n"] == saved_n
    assert s01["summary"]["n"] != len((s01["envelope"].get("population") or {}).get("rows") or [])
    assert s01["summary"]["question_hash"] != s02["summary"]["question_hash"]

    loaded = handle_version(stax_id, "1.0.0", root=tmp_path)
    assert loaded["results"][0]["member_id"] == "STXM-0001"
    pkg = handle_export(stax_id, root=tmp_path)
    assert pkg["live_execution"] is False
    assert pkg["aggregation_method"] == "NONE"
    proof = {
        "stax_id": stax_id,
        "version": out["version"],
        "definition_hash": out["definition_hash"],
        "dataset_fingerprint": out["dataset_fingerprint"],
        "universe": out["universe"],
        "members": [
            {
                "member_id": m["member_id"],
                "position": m["position"],
                "label": m.get("label"),
                "question_hash": m.get("question_hash"),
                "status": by_id[m["member_id"]]["status"],
                "n": by_id[m["member_id"]]["summary"].get("n"),
                "dataset_version": by_id[m["member_id"]]["summary"].get("dataset_version"),
                "envelope_id": id(by_id[m["member_id"]].get("envelope")),
            }
            for m in out["members"]
        ],
        "overlap": out.get("overlap"),
        "sum_of_strategy_n": out.get("sum_of_strategy_n"),
        "sum_of_strategy_n_label": out.get("sum_of_strategy_n_label"),
    }
    dest = tmp_path / "stax_e2e_proof.json"
    dest.write_text(json.dumps(proof, indent=2, default=str))
    repo_copy = Path(__file__).resolve().parents[1] / "data" / ".cache" / "stax_e2e_proof.json"
    repo_copy.parent.mkdir(parents=True, exist_ok=True)
    repo_copy.write_text(dest.read_text())
    assert load_head(stax_id, root=tmp_path)["stax_id"] == stax_id
