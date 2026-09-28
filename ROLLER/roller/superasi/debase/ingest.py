"""Read a Phase A folder. Fail closed on missing files or hash mismatch."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from typing import Any

from roller.config import RollerConfig
from roller.labs.store import get_lab
from roller.superasi.base.ingest import parse_labs_csv
from roller.superasi.base import store as base_store
from roller.superasi.models import SuperasiError


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_abase_csv(text: str | bytes) -> dict[str, Any]:
    raw = text.decode("utf-8") if isinstance(text, bytes) else text
    reader = csv.DictReader(io.StringIO(raw))
    if reader.fieldnames is None:
        raise SuperasiError("ABASE_CSV_INVALID", "SuperasiABase CSV has no header")
    rows = [{k: (v if v is not None else "") for k, v in rec.items()} for rec in reader]
    by_metric: dict[str, list[dict[str, str]]] = {}
    for rec in rows:
        key = str(rec.get("metric") or "").strip()
        if key:
            by_metric.setdefault(key, []).append(rec)
    grades = {row["metric"]: row.get("value") for row in rows if row.get("record_type") == "grading"}
    return {
        "header": list(reader.fieldnames),
        "rows": rows,
        "by_metric": by_metric,
        "grades": grades,
    }


def _metric_value(parsed: dict[str, Any], metric: str) -> str:
    rows = parsed.get("by_metric", {}).get(metric) or []
    if not rows:
        return ""
    return str(rows[0].get("value") or "")


def extract_entry(parsed_roller: dict[str, Any]) -> float | None:
    from roller.superasi.debase.rr import plan_prices

    prices = plan_prices(parsed_roller)
    if prices.get("entry") is not None:
        return float(prices["entry"])
    trades = list(parsed_roller.get("trade_rows") or [])
    for row in trades:
        text = str(row.get("entry_value") or "").strip()
        if not text:
            continue
        try:
            value = float(text)
        except ValueError:
            continue
        if value != 0:
            return value
    return None


def load_phase_a_folder(result_id: str, *, cfg: RollerConfig | None = None) -> dict[str, Any]:
    rec = base_store.get_base_result(result_id, cfg)
    if rec is None:
        raise SuperasiError("RESULT_NOT_FOUND", f"Phase A result not found: {result_id}")
    root = base_store.phase_a_root(cfg)
    dest = root / result_id
    roller_name = str(rec.get("roller_filename") or "")
    abase_name = str(rec.get("abase_filename") or "")
    roller_path = dest / roller_name
    abase_path = dest / abase_name
    if not roller_path.is_file() or not abase_path.is_file():
        raise SuperasiError("PHASE_A_INCOMPLETE", "Phase A folder is missing Roller or SuperasiABase CSV")
    roller_bytes = roller_path.read_bytes()
    abase_bytes = abase_path.read_bytes()
    roller_hash = _sha256(roller_bytes)
    abase_hash = _sha256(abase_bytes)
    expected_roller = str(rec.get("source_csv_sha256") or "")
    expected_abase = str(rec.get("abase_sha256") or "")
    if not expected_roller or expected_roller != roller_hash:
        raise SuperasiError("HASH_MISMATCH", "Phase A Roller CSV hash does not match metadata")
    if not expected_abase or expected_abase != abase_hash:
        raise SuperasiError("HASH_MISMATCH", "Phase A SuperasiABase CSV hash does not match metadata")
    parsed_roller = parse_labs_csv(roller_bytes)
    parsed_abase = parse_abase_csv(abase_bytes)
    base_grade = str(rec.get("BASE_GRADE") or parsed_abase.get("grades", {}).get("BASE_GRADE") or "")
    if not base_grade:
        raise SuperasiError("PHASE_A_INCOMPLETE", "Phase A BASE_GRADE is missing")
    lab_id = str(rec.get("source_lab_id") or "")
    lab = get_lab(lab_id, cfg) if lab_id else None
    question = lab.get("question") if isinstance(lab, dict) and isinstance(lab.get("question"), dict) else None
    question_blob = json.dumps(question, sort_keys=True, separators=(",", ":"), default=str) if question else ""
    question_sha = _sha256(question_blob.encode("utf-8")) if question_blob else ""
    return {
        "phase_a": rec,
        "result_id": result_id,
        "strategy_name": str(rec.get("strategy_name") or parsed_roller["meta"].get("strategy_name") or "Untitled"),
        "source_lab_id": lab_id,
        "roller_filename": roller_name,
        "abase_filename": abase_name,
        "roller_bytes": roller_bytes,
        "abase_bytes": abase_bytes,
        "source_csv_sha256": roller_hash,
        "abase_sha256": abase_hash,
        "parsed_roller": parsed_roller,
        "parsed_abase": parsed_abase,
        "BASE_GRADE": base_grade,
        "phase_a_components": rec.get("components") if isinstance(rec.get("components"), dict) else {},
        "question": question,
        "question_status": "PRESENT" if question else "UNAVAILABLE",
        "question_sha256": question_sha,
        "desk_break_even": _metric_value(parsed_abase, "break_even_probability"),
        "desk_trade_ev": _metric_value(parsed_abase, "trade_ev"),
        "desk_weekly_ev": _metric_value(parsed_abase, "weekly_ev"),
    }
