"""Immutable artifacts. Rerun creates a new file."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from roller.systimo.errors import SystimoError
from roller.systimo.models import now_iso
from roller.systimo.paths import artifacts_dir
from roller.systimo.query.executor import get_answer
from roller.systimo.store import CsvStore


def save_artifact(
    query_id: str,
    store: CsvStore | None = None,
    *,
    kind: str = "json",
    rerun_of: str = "",
) -> dict[str, Any]:
    csv = store or CsvStore()
    answer = get_answer(query_id, csv)
    if not answer.get("answer_id"):
        raise SystimoError("NO_ANSWER", f"query {query_id} has no answer")
    fmt = "md" if str(kind).lower() == "md" else "json"
    artifact_id = uuid.uuid4().hex[:16]
    created = now_iso()
    body = {
        "artifact_id": artifact_id,
        "query_id": query_id,
        "answer_id": answer["answer_id"],
        "created_at": created,
        "query": {"query_id": query_id, "query_type": answer["query_type"]},
        "answer": answer["result"],
        "sources": answer["sources"],
        "provenance": {"schema": answer["schema"], "completed_at": answer["completed_at"]},
        "rerun_of": rerun_of,
        "live_execution": False,
    }
    folder = artifacts_dir(csv.root)
    folder.mkdir(parents=True, exist_ok=True)
    if fmt == "md":
        raw = (
            f"# Systimo artifact `{artifact_id}`\n\n"
            f"query_id: `{query_id}`  \n"
            f"rerun_of: `{rerun_of or ''}`  \n\n"
            "```json\n"
            + json.dumps(body, indent=2, sort_keys=True)
            + "\n```\n"
        )
        rel = f"{artifact_id}.md"
    else:
        raw = json.dumps(body, indent=2, sort_keys=True) + "\n"
        rel = f"{artifact_id}.json"
    checksum = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    path = folder / rel
    path.write_text(raw, encoding="utf-8")
    csv.append(
        "artifacts_index",
        {
            "artifact_id": artifact_id,
            "query_id": query_id,
            "answer_id": answer["answer_id"],
            "created_at": created,
            "path": rel,
            "checksum": checksum,
            "format": fmt,
            "supersedes": "",
            "rerun_of": rerun_of,
            "status": "SAVED",
        },
    )
    answers = csv.read("answers")
    for row in answers:
        if row["answer_id"] == answer["answer_id"]:
            row["artifact_id"] = artifact_id
    csv.write("answers", answers)
    return {
        "artifact_id": artifact_id,
        "path": str(path),
        "checksum": checksum,
        "query_id": query_id,
        "format": fmt,
        "rerun_of": rerun_of or None,
    }


def list_artifacts(store: CsvStore | None = None) -> list[dict[str, str]]:
    return (store or CsvStore()).read("artifacts_index")
