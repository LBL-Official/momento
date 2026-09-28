"""Create a canonical ROLLER research object and add it as a STAX member.

STAX does not compile questions itself. It calls the existing ROLLER
compiler and save path, then the existing membership writer.

LIVE EXECUTION = FALSE
"""

from __future__ import annotations

from typing import Any

from roller.research_library.saves import write_save
from roller.research_query.compiler import compile_draft
from roller.research_query.hashing import layer_hashes
from roller.research_query.models import ResearchStatus
from roller.stax.compatibility import assert_compatible, universe_from_source
from roller.stax.library import load_head, write_head
from roller.stax.membership import add_member, assert_members_share_universe
from roller.stax.models import StaxError, utc_now
from roller.stax.validation import reject_rolling_fields, strip_client_overrides
from roller.stax.versions import LIVE_EXECUTION

DUPLICATE_MESSAGE = "DUPLICATE RESEARCH DEFINITION. This definition already exists in this STAX."


def _draft_from_body(body: dict[str, Any]) -> dict[str, Any]:
    raw = body.get("draft") if isinstance(body.get("draft"), dict) else None
    if raw is None:
        raw = body.get("workflow_draft") if isinstance(body.get("workflow_draft"), dict) else None
    if raw is None:
        raise StaxError("STAX_DRAFT_REQUIRED", "draft is required")
    draft = strip_client_overrides(dict(raw))
    reject_rolling_fields(draft)
    universe = draft.get("universe")
    if isinstance(universe, dict):
        reject_rolling_fields(universe)
        draft["universe"] = strip_client_overrides(universe)
    return draft


def _compile_status(compiled: Any) -> str:
    status = getattr(compiled, "status", None)
    if hasattr(status, "value"):
        return str(status.value)
    return str(status or "")


def _label_from_question(question: dict[str, Any]) -> str:
    entries = question.get("entry_conditions") if isinstance(question.get("entry_conditions"), list) else []
    paths = question.get("path_conditions") if isinstance(question.get("path_conditions"), list) else []
    bits: list[str] = []
    if entries and isinstance(entries[0], dict):
        entry = entries[0]
        op = entry.get("operation") or entry.get("ordinal") or "ENTRY"
        price = entry.get("price_e4")
        if price is not None:
            bits.append(f"{op} {int(price) // 100}")
        else:
            bits.append(str(op))
    if paths and isinstance(paths[0], dict):
        path = paths[0]
        price = path.get("price_e4")
        op = path.get("operation") or "PATH"
        if price is not None:
            bits.append(f"{op} {int(price) // 100}")
        else:
            bits.append(str(op))
    return " / ".join(bits) if bits else "ROLLER strategy"


def _duplicate_members(members: list[dict[str, Any]], question_hash: str | None) -> list[dict[str, Any]]:
    if not question_hash:
        return []
    return [
        m
        for m in members
        if (m.get("question_hash") or m.get("query_hash")) == question_hash
    ]


def handle_create_strategy(stax_id: str, body: dict[str, Any] | None = None, *, root=None) -> dict[str, Any]:
    """Compile a ROLLER draft, persist a real save, then create STAX membership.

    persist=false validates only. Nothing is written.
    """
    body = strip_client_overrides(body or {})
    reject_rolling_fields(body)
    persist = True if body.get("persist") is None else bool(body.get("persist"))
    allow_duplicate = bool(body.get("allow_duplicate"))
    draft = _draft_from_body(body)

    compiled = compile_draft(draft)
    compile_dict = compiled.to_dict()
    status = _compile_status(compiled)
    question = compiled.question.to_dict()
    te_state = draft.get("teFilters") if isinstance(draft.get("teFilters"), dict) else draft.get("te_filters")
    hashes = layer_hashes(compiled.question, state=te_state if isinstance(te_state, dict) else None)
    question_hash = hashes.get("question_hash")
    name = str(body.get("name") or body.get("label") or "").strip() or _label_from_question(question)

    if status == ResearchStatus.OPERATION_REQUIRED.value:
        payload = {
            "ok": False,
            "valid": False,
            "persisted": False,
            "duplicate": False,
            "compile": compile_dict,
            "hashes": hashes,
            "name": name,
            "reasons": list(compiled.reasons or []),
            "message": "strategy does not compile",
            "live_execution": LIVE_EXECUTION,
        }
        if persist:
            raise StaxError("STAX_DRAFT_INVALID", "strategy does not compile", payload)
        return payload

    candidate_universe = universe_from_source({"question": question})
    head = load_head(stax_id, root=root)
    members = list(head.get("working_members") or [])
    locked = head.get("universe")
    if locked:
        assert_compatible(locked, candidate_universe)
    elif members:
        assert_compatible(assert_members_share_universe(members), candidate_universe)

    existing = _duplicate_members(members, question_hash)
    duplicate = bool(existing)
    preview = {
        "ok": True,
        "valid": True,
        "persisted": False,
        "duplicate": duplicate,
        "duplicate_member_ids": [m.get("member_id") for m in existing],
        "compile": compile_dict,
        "hashes": hashes,
        "universe": candidate_universe.to_dict(),
        "locked_universe": locked,
        "name": name,
        "live_execution": LIVE_EXECUTION,
    }
    if duplicate:
        preview["code"] = "STAX_DUPLICATE_DEFINITION"
        preview["message"] = DUPLICATE_MESSAGE
    if not persist:
        return preview
    if duplicate and not allow_duplicate:
        raise StaxError(
            "STAX_DUPLICATE_DEFINITION",
            DUPLICATE_MESSAGE,
            {
                "member_ids": [m.get("member_id") for m in existing],
                "question_hash": question_hash,
            },
        )

    saved = write_save(
        {
            "name": name,
            "folder": "STAX",
            "description": str(body.get("description") or ""),
            "question": name,
            "workflow_draft": draft,
            "hashes": hashes,
            "research_spec": {},
            "result": {
                "compile": compile_dict,
                "hashes": hashes,
                "research_object_id": compiled.reference_match,
            },
        }
    )

    source = strip_client_overrides(
        {
            "name": name,
            "id": saved["id"],
            "save_id": saved["id"],
            "question": question,
            "draft": draft,
            "workflow_draft": draft,
            "hashes": hashes,
            "research_object_id": compiled.reference_match,
            "result": {
                "compile": compile_dict,
                "hashes": hashes,
                "research_object_id": compiled.reference_match,
            },
        }
    )
    head["member_seq"] = int(head.get("member_seq") or 0) + 1
    members = add_member(
        members,
        source,
        stax_id=stax_id,
        member_seq=head["member_seq"],
    )
    head["universe"] = assert_members_share_universe(members).to_dict()
    head["working_members"] = members
    head["updated_at"] = utc_now()
    write_head(head, root=root)
    created = members[-1]
    return {
        "stax": {
            "stax_id": head.get("stax_id"),
            "name": head.get("name"),
            "description": head.get("description"),
            "created_at": head.get("created_at"),
            "updated_at": head.get("updated_at"),
            "universe": head.get("universe"),
            "timezone": head.get("timezone"),
            "automation_enabled": head.get("automation_enabled"),
            "latest_version": head.get("latest_version"),
            "latest_status": head.get("latest_status"),
            "strategy_count": len(members),
            "live_execution": LIVE_EXECUTION,
        },
        "members": members,
        "member": created,
        "roller": {
            "save_id": saved["id"],
            "research_object_id": created.get("research_object_id"),
            "question_hash": created.get("question_hash"),
            "question": question,
            "compile": compile_dict,
            "hashes": hashes,
        },
        "duplicate": duplicate,
        "persisted": True,
        "valid": True,
        "live_execution": LIVE_EXECUTION,
    }
