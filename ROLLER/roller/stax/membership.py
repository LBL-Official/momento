"""STAX membership. member_id is durable. position is order only."""

from __future__ import annotations

from typing import Any

from roller.research_query.hashing import dumps_canon, question_hash, sha256_hex
from roller.research_query.models import ResearchQuestion
from roller.stax.compatibility import (
    CanonicalUniverse,
    assert_compatible,
    canonicalize_universe,
    universe_from_source,
)
from roller.stax.models import ConstraintViolation, StaxError, next_numeric_id
from roller.stax.validation import reject_rolling_fields, strip_client_overrides


def _stax_ordinal(stax_id: str) -> str:
    tail = str(stax_id or "").split("-")[-1]
    if tail.isdigit():
        return str(int(tail)).zfill(2) if int(tail) < 100 else tail
    return "01"


def display_id(stax_id: str, position: int) -> str:
    return f"STX{_stax_ordinal(stax_id)}-S{str(position).zfill(2)}"


def next_member_id(members: list[dict[str, Any]], seq: int | None = None) -> str:
    existing = [str(m.get("member_id") or "") for m in members]
    if seq is not None:
        candidate = f"STXM-{str(seq).zfill(4)}"
        if candidate not in existing:
            return candidate
    return next_numeric_id("STXM", existing)


def _question_from_source(source: dict[str, Any]) -> dict[str, Any] | None:
    if isinstance(source.get("question"), dict):
        return source["question"]
    compile_block = source.get("compile")
    if isinstance(compile_block, dict) and isinstance(compile_block.get("question"), dict):
        return compile_block["question"]
    result = source.get("result")
    if isinstance(result, dict):
        return _question_from_source(result)
    return None


def _hashes_from_source(source: dict[str, Any]) -> dict[str, Any]:
    hashes = source.get("hashes") if isinstance(source.get("hashes"), dict) else {}
    result = source.get("result") if isinstance(source.get("result"), dict) else {}
    result_hashes = result.get("hashes") if isinstance(result.get("hashes"), dict) else {}
    merged = {**result_hashes, **hashes}
    question = _question_from_source(source)
    if question and not merged.get("question_hash"):
        try:
            merged["question_hash"] = question_hash(ResearchQuestion.from_dict(question))
        except Exception:
            merged["question_hash"] = sha256_hex(dumps_canon(question))
    return merged


def member_from_source(
    source: dict[str, Any],
    *,
    stax_id: str,
    members: list[dict[str, Any]],
    position: int,
    member_id: str | None = None,
    member_seq: int | None = None,
) -> dict[str, Any]:
    source = strip_client_overrides(source)
    reject_rolling_fields(source)
    reject_rolling_fields(source.get("universe") if isinstance(source.get("universe"), dict) else {})
    question = _question_from_source(source)
    draft = source.get("draft") or source.get("workflow_draft")
    if question is None and isinstance(draft, dict):
        from roller.research_query.compiler import compile_draft

        compiled = compile_draft(draft)
        question = compiled.question.to_dict()
    universe = universe_from_source(source if question is None else {**source, "question": question})
    hashes = _hashes_from_source({**source, "question": question} if question else source)
    spec = source.get("research_spec") if isinstance(source.get("research_spec"), dict) else {}
    mid = member_id or next_member_id(members, member_seq)
    label = str(source.get("name") or source.get("label") or "").strip()
    return {
        "member_id": mid,
        "position": position,
        "display_id": display_id(stax_id, position),
        "label": label,
        "save_id": source.get("save_id") or source.get("id"),
        "roller_object_id": source.get("roller_object_id") or source.get("save_id") or source.get("id"),
        "research_object_id": source.get("research_object_id")
        or (source.get("result") or {}).get("research_object_id"),
        "question": question,
        "draft": draft if isinstance(draft, dict) else None,
        "research_spec": spec,
        "question_hash": hashes.get("question_hash"),
        "query_hash": hashes.get("question_hash"),
        "universe": universe.to_dict(),
        "definition_version": source.get("definition_version") or "1.0.0",
        "status": "PENDING",
    }


def lock_universe(members: list[dict[str, Any]]) -> CanonicalUniverse | None:
    if not members:
        return None
    return canonicalize_universe(members[0]["universe"])


def add_member(
    members: list[dict[str, Any]],
    source: dict[str, Any],
    *,
    stax_id: str,
    member_seq: int | None = None,
) -> list[dict[str, Any]]:
    locked = lock_universe(members)
    candidate = member_from_source(
        source,
        stax_id=stax_id,
        members=members,
        position=len(members) + 1,
        member_seq=member_seq,
    )
    if locked is not None:
        assert_compatible(locked, candidate["universe"])
    return reindex(members + [candidate], stax_id)


def remove_member(members: list[dict[str, Any]], member_id: str, *, stax_id: str) -> list[dict[str, Any]]:
    kept = [m for m in members if m.get("member_id") != member_id]
    if len(kept) == len(members):
        raise StaxError("STAX_MEMBER_NOT_FOUND", f"unknown member {member_id}")
    return reindex(kept, stax_id)


def reorder_members(
    members: list[dict[str, Any]],
    order: list[str],
    *,
    stax_id: str,
) -> list[dict[str, Any]]:
    by_id = {str(m.get("member_id")): m for m in members}
    if set(order) != set(by_id):
        raise StaxError(
            "STAX_REORDER_INVALID",
            "reorder must include every member_id exactly once",
        )
    ordered = [dict(by_id[mid]) for mid in order]
    return reindex(ordered, stax_id)


def reindex(members: list[dict[str, Any]], stax_id: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, member in enumerate(members, start=1):
        rec = dict(member)
        rec["position"] = i
        rec["display_id"] = display_id(stax_id, i)
        out.append(rec)
    return out


def definition_payload(members: list[dict[str, Any]]) -> dict[str, Any]:
    """Canonical definition for hashing. Order of member_ids is included."""
    rows = []
    for member in sorted(members, key=lambda m: int(m.get("position") or 0)):
        rows.append(
            {
                "member_id": member.get("member_id"),
                "position": member.get("position"),
                "research_object_id": member.get("research_object_id"),
                "roller_object_id": member.get("roller_object_id"),
                "question_hash": member.get("question_hash") or member.get("query_hash"),
                "question": member.get("question"),
                "research_spec": member.get("research_spec") or {},
                "definition_version": member.get("definition_version") or "1.0.0",
            }
        )
    return {"members": rows}


def definition_hash(members: list[dict[str, Any]]) -> str:
    return sha256_hex(dumps_canon(definition_payload(members)))


def assert_members_share_universe(members: list[dict[str, Any]]) -> CanonicalUniverse:
    if not members:
        raise ConstraintViolation("STAX requires at least one strategy", {"reason": "EMPTY"})
    locked = canonicalize_universe(members[0]["universe"])
    for member in members[1:]:
        assert_compatible(locked, member["universe"])
    return locked
