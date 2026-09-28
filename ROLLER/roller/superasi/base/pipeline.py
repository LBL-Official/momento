"""Run SuperASI A — Base against one Labs CSV."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from roller import desk_settings
from roller.config import RollerConfig
from roller.labs.schema import sanitize_name
from roller.labs.store import get_lab, get_lab_csv_bytes
from roller.superasi.base.composition import run_desk_composition, run_desk_risk_profile
from roller.superasi.base.grading import grade_strategy
from roller.superasi.base.ingest import parse_labs_csv
from roller.superasi.base.observed import summarize_observed
from roller.superasi.base.roller_desk import (
    attach_desk,
    compute_roller_desk,
    inspect_risk_profile_from_desk,
)
from roller.superasi.base.store import save_base_result
from roller.superasi.base.validation import comparison_rows, integrity_checks
from roller.superasi.base.versions import DESK_PATHS
from roller.superasi.models import SuperasiError


def run_base(
    *,
    lab_id: str,
    cfg: RollerConfig | None = None,
    monte_carlo_paths: int = DESK_PATHS,
) -> dict[str, Any]:
    rec = get_lab(lab_id, cfg)
    found = get_lab_csv_bytes(lab_id, cfg)
    if rec is None or found is None:
        raise SuperasiError("LAB_NOT_FOUND", f"Labs CSV not found: {lab_id}")
    filename, roller_bytes = found
    source_hash = hashlib.sha256(roller_bytes).hexdigest()
    if rec.get("csv_sha256") and str(rec["csv_sha256"]) != source_hash:
        raise SuperasiError("LABS_CSV_INVALID", "stored Labs CSV hash does not match bytes")
    parsed = parse_labs_csv(roller_bytes)
    observed = summarize_observed(parsed)
    checks = integrity_checks(parsed, observed)
    composition = run_desk_composition(
        research_result_hash=str(observed.get("result_hash") or ""),
        monte_carlo_paths=monte_carlo_paths,
    )
    profile = run_desk_risk_profile(
        research_result_hash=str(observed.get("result_hash") or ""),
        monte_carlo_paths=monte_carlo_paths,
    )
    grading = grade_strategy(observed, checks)
    comparison = comparison_rows(observed, composition, profile)
    roller_desk = compute_roller_desk(parsed, observed, cfg=cfg)
    strategy = sanitize_name(str(rec.get("strategy_name") or parsed["meta"].get("strategy_name") or "Untitled"))
    desk_public = desk_settings.public_settings(cfg=cfg)
    roller_risk = inspect_risk_profile_from_desk(
        roller_desk,
        research_result_hash=str(observed.get("result_hash") or ""),
        monte_carlo_paths=monte_carlo_paths,
        cfg=cfg,
        public=desk_public,
    )
    payload = {
        "strategy_name": strategy,
        "source_lab_id": lab_id,
        "source_csv_sha256": source_hash,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "meta": parsed["meta"],
        "observed": observed,
        "composition": composition,
        "roller_desk": roller_desk,
        "roller_risk_profile": roller_risk,
        "risk_profile": profile,
        "grading": grading,
        "checks": checks,
        "comparison": comparison,
        "desk_settings": desk_public,
        **desk_settings.stamp(cfg=cfg),
    }
    saved = save_base_result(
        payload=payload,
        roller_bytes=roller_bytes,
        roller_filename=filename,
        cfg=cfg,
    )
    inspect = {
        "result_id": saved["result_id"],
        "strategy_name": strategy,
        "source_lab_id": lab_id,
        "created_at": saved["created_at"],
        "BASE_GRADE": grading.get("BASE_GRADE"),
        "components": grading.get("components"),
        "composite_score": grading.get("composite_score"),
        "borderline": grading.get("borderline"),
        "observed": {
            "population": observed.get("population"),
            "wins": observed.get("wins"),
            "losses": observed.get("losses"),
            "win_rate": observed.get("win_rate"),
            "gross_ev": observed.get("gross_ev"),
            "wilson_lower": observed.get("wilson_lower"),
            "wilson_upper": observed.get("wilson_upper"),
            "decided_rate": observed.get("decided_rate"),
            "bad_settle_rate": observed.get("bad_settle_rate"),
        },
        "desk": roller_desk,
        "risk_profile": roller_risk,
        "desk_settings": payload.get("desk_settings"),
        "checks": checks,
        "honesty": {
            "risk_not": "candle_path_not_fill",
            "live_grade": "UNAVAILABLE",
            "fees": "UNAVAILABLE",
            "fills": "UNAVAILABLE",
        },
        "files": {
            "roller_filename": saved["roller_filename"],
            "abase_filename": saved["abase_filename"],
            "abase_sha256": saved["abase_sha256"],
            "source_csv_sha256": source_hash,
        },
    }
    inspect = attach_desk(inspect, composition=composition, parsed=parsed, observed=observed, cfg=cfg)
    inspect["desk"] = roller_desk
    return {**saved, "inspect": inspect}
