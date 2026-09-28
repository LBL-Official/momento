"""Load a persisted ResearchQuestion from a SuperASI Final Result. Fail closed."""

from __future__ import annotations

import csv
import io
from typing import Any

from roller.config import RollerConfig
from roller.jump.errors import JumpError
from roller.labs.store import get_lab, get_lab_csv_bytes
from roller.superasi.debase.store import get_debase_result


def _usable_question(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    entries = raw.get("entry_conditions")
    if not isinstance(entries, list) or not entries:
        return None
    if all(e.get("price_e4") is None for e in entries if isinstance(e, dict)):
        return None
    return raw


def load_source(*, debase_result_id: str, cfg: RollerConfig | None = None) -> dict[str, Any]:
    rec = get_debase_result(debase_result_id, cfg)
    if rec is None:
        raise JumpError("RESULT_NOT_FOUND", f"SuperASI Final Result not found: {debase_result_id}")
    question = _usable_question(rec.get("question"))
    lab_id = str(rec.get("source_lab_id") or "")
    lab = get_lab(lab_id, cfg) if lab_id else None
    if question is None and isinstance(lab, dict):
        question = _usable_question(lab.get("question"))
    if question is None:
        raise JumpError(
            "DATA_REQUIRED",
            "persisted ResearchQuestion is missing; ITI does not reconstruct from Roller CSV columns",
        )
    out = {
        "debase": rec,
        "lab": lab,
        "question": question,
        "strategy_name": str(rec.get("strategy_name") or "Untitled"),
        "source_folder": str(rec.get("folder") or rec.get("result_id") or debase_result_id),
        "source_lab_id": lab_id,
        "debase_result_id": str(rec.get("result_id") or debase_result_id),
    }
    out["snapshot"] = source_snapshot(out, cfg=cfg)
    return out


def _summary_field(raw: bytes, field: str) -> str | None:
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8")))
    fallback: str | None = None
    for row in reader:
        value = row.get(field)
        if value in (None, ""):
            continue
        kind = str(row.get("record_type") or "").strip().upper()
        if kind in {"SUMMARY", "RISK", "META"}:
            return str(value)
        if fallback is None:
            fallback = str(value)
    return fallback


def source_snapshot(source: dict[str, Any], *, cfg: RollerConfig | None = None) -> dict[str, Any]:
    from roller.superasi.iti.catalog import question_sha256

    debase = source.get("debase") if isinstance(source.get("debase"), dict) else {}
    lab_id = str(source.get("source_lab_id") or debase.get("source_lab_id") or "")
    population = debase.get("population")
    result_hash = str(debase.get("result_hash") or "") or None
    if lab_id:
        found = get_lab_csv_bytes(lab_id, cfg)
        if found is not None:
            if population is None:
                raw_pop = _summary_field(found[1], "population")
                if raw_pop is not None:
                    population = int(raw_pop)
            if not result_hash:
                result_hash = _summary_field(found[1], "result_hash")
    return {
        "lab_id": lab_id or None,
        "phase_a_result_id": debase.get("phase_a_result_id"),
        "phase_b_result_id": debase.get("result_id") or source.get("debase_result_id"),
        "BASE_GRADE": debase.get("BASE_GRADE"),
        "DEBASE_GRADE": debase.get("DEBASE_GRADE"),
        "result_hash": result_hash,
        "population": int(population) if population is not None else None,
        "question_sha256": question_sha256(source["question"]),
    }
