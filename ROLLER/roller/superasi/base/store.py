"""Phase A results disk store. Sibling of ROLLER/labs. Not the warehouse."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roller import desk_settings
from roller.config import RollerConfig
from roller.labs.schema import sanitize_name
from roller.labs.store import roller_csv_population
from roller.superasi.base.export_csv import csv_filename, render_csv
from roller.superasi.base.ingest import parse_labs_csv
from roller.superasi.base.observed import summarize_observed
from roller.superasi.base.roller_desk import (
    DATA_REQUIRED,
    ROLLER_MC_NOTE,
    ROLLER_NOTE,
    blank_risk_inspect,
    compute_roller_desk,
    inspect_risk_profile_from_desk,
    instrument_from_composition,
    risk_inspect_from_stored,
)
from roller.superasi.base.versions import GRADE_CONFIG_VERSION, SUPERASI_BASE_VERSION
from roller.superasi.models import SuperasiError


def phase_a_root(cfg: RollerConfig | None = None) -> Path:
    cfg = cfg or RollerConfig()
    return Path(cfg.root) / "superasi_labs" / "phase_a"


def _folder_for(name: str, lab_id: str, root: Path) -> str:
    base = sanitize_name(name)
    dest = root / base
    if not dest.is_dir():
        return base
    meta_path = dest / "metadata.json"
    if meta_path.is_file():
        rec = json.loads(meta_path.read_text(encoding="utf-8"))
        if str(rec.get("source_lab_id") or "") in {"", lab_id}:
            return base
    return f"{base}__{lab_id[:8]}"


def save_base_result(
    *,
    payload: dict[str, Any],
    roller_bytes: bytes,
    roller_filename: str,
    cfg: RollerConfig | None = None,
) -> dict[str, Any]:
    cfg = cfg or RollerConfig()
    root = phase_a_root(cfg)
    root.mkdir(parents=True, exist_ok=True)
    lab_id = str(payload.get("source_lab_id") or "")
    strategy = sanitize_name(str(payload.get("strategy_name") or "Untitled"))
    folder = _folder_for(strategy, lab_id, root)
    dest = root / folder
    dest.mkdir(parents=True, exist_ok=True)
    created_at = str(payload.get("created_at") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    body = dict(payload)
    body["created_at"] = created_at
    draft = render_csv(body, abase_hash="")
    digest = hashlib.sha256(draft.encode("utf-8")).hexdigest()
    csv_text = render_csv(body, abase_hash=digest)
    stored_hash = hashlib.sha256(csv_text.encode("utf-8")).hexdigest()
    base_name = csv_filename(strategy)
    (dest / roller_filename).write_bytes(roller_bytes)
    (dest / base_name).write_text(csv_text, encoding="utf-8", newline="\n")
    grading = body.get("grading") if isinstance(body.get("grading"), dict) else {}
    metadata = {
        "result_id": folder,
        "folder": folder,
        "strategy_name": strategy,
        "source_lab_id": lab_id,
        "created_at": created_at,
        "roller_filename": roller_filename,
        "abase_filename": base_name,
        "source_csv_sha256": body.get("source_csv_sha256"),
        "abase_payload_sha256": digest,
        "abase_sha256": stored_hash,
        "BASE_GRADE": grading.get("BASE_GRADE"),
        "components": grading.get("components"),
        "borderline": grading.get("borderline"),
        "superasi_version": SUPERASI_BASE_VERSION,
        "grade_config_version": GRADE_CONFIG_VERSION,
        "artifact": "superasi_abase",
        "phase": "A",
        **desk_settings.stamp(cfg=cfg),
    }
    (dest / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        **metadata,
        "abase_bytes": len(csv_text.encode("utf-8")),
        "roller_bytes": len(roller_bytes),
        "csv_text": csv_text,
        "payload": body,
    }


def list_base_results(cfg: RollerConfig | None = None) -> list[dict[str, Any]]:
    root = phase_a_root(cfg)
    if not root.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        meta_path = folder / "metadata.json"
        if not meta_path.is_file():
            continue
        rec = json.loads(meta_path.read_text(encoding="utf-8"))
        rec["path_folder"] = folder.name
        rec.update(roller_csv_population(folder / str(rec.get("roller_filename") or "")))
        items.append(rec)
    items.sort(key=lambda r: (str(r.get("created_at") or ""), str(r.get("result_id") or "")), reverse=True)
    return items


def _as_number(raw: object) -> float | int | None:
    text = str(raw or "").strip()
    if text == "":
        return None
    try:
        if any(ch in text.lower() for ch in (".", "e")):
            return float(text)
        return int(text)
    except ValueError:
        return None


def inspect_from_abase(rec: dict[str, Any], dest: Path) -> dict[str, Any]:
    """Rebuild the Phase A inspect layout from SuperasiABase CSV. Facts only."""
    csv_path = dest / str(rec.get("abase_filename") or "")
    metrics: dict[tuple[str, str], str] = {}
    checks: list[dict[str, Any]] = []
    components: dict[str, str] = {}
    if csv_path.is_file():
        with csv_path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                rt = str(row.get("record_type") or "")
                metric = str(row.get("metric") or "")
                value = str(row.get("value") or "")
                if rt == "validation" and metric:
                    checks.append({"id": metric, "ok": value == "PASS", "severity": str(row.get("source") or "")})
                elif rt == "grading" and metric.endswith("_grade"):
                    components[metric[: -len("_grade")]] = value
                elif rt and metric:
                    metrics[(rt, metric)] = value

    def metric(rt: str, name: str) -> float | int | str | None:
        raw = metrics.get((rt, name), "")
        number = _as_number(raw)
        if number is not None:
            return number
        return raw or None

    stored_components = rec.get("components") if isinstance(rec.get("components"), dict) else {}
    return {
        "result_id": rec.get("result_id"),
        "strategy_name": rec.get("strategy_name"),
        "source_lab_id": rec.get("source_lab_id"),
        "created_at": rec.get("created_at"),
        "BASE_GRADE": rec.get("BASE_GRADE") or metric("grading", "BASE_GRADE"),
        "components": stored_components or components,
        "composite_score": _as_number(metric("grading", "composite_score")),
        "borderline": str(rec.get("borderline") or metric("grading", "borderline") or "").lower() == "true",
        "observed": {
            "population": metric("observed", "population"),
            "wins": metric("observed", "wins"),
            "losses": metric("observed", "losses"),
            "win_rate": metric("observed", "win_rate"),
            "gross_ev": metric("observed", "gross_ev"),
            "wilson_lower": metric("observed", "wilson_lower"),
            "wilson_upper": metric("observed", "wilson_upper"),
            "decided_rate": metric("observed", "decided_rate"),
            "bad_settle_rate": metric("observed", "bad_settle_rate"),
        },
        "desk": {
            "status": DATA_REQUIRED,
            "reason": DATA_REQUIRED,
            "break_even_probability": None,
            "trade_ev": None,
            "weekly_ev": None,
            "required_win_probability": None,
            "p_used": None,
            "source": "roller_payoff",
            "note": ROLLER_NOTE,
        },
        "instrument": {
            "mode": metric("composition", "risk_mode"),
            "seed": metric("composition", "risk_seed"),
            "break_even_probability": metric("composition", "break_even_probability"),
            "trade_ev": metric("composition", "trade_ev"),
            "weekly_ev": metric("composition", "weekly_ev"),
            "required_win_probability": metric("composition", "required_win_probability"),
            "source": "mode_a_instrument",
        },
        "risk_profile": blank_risk_inspect(),
        "checks": checks,
        "honesty": {
            "risk_not": "candle_path_not_fill",
            "live_grade": "UNAVAILABLE",
            "fees": "UNAVAILABLE",
            "fills": "UNAVAILABLE",
        },
        "files": {
            "roller_filename": rec.get("roller_filename"),
            "abase_filename": rec.get("abase_filename"),
            "abase_sha256": rec.get("abase_sha256"),
            "source_csv_sha256": rec.get("source_csv_sha256"),
        },
    }


def _stored_roller_metrics(dest: Path, rec: dict[str, Any]) -> dict[str, Any]:
    by_metric: dict[str, str] = {}
    metrics_path = dest / str(rec.get("abase_filename") or "")
    if metrics_path.is_file():
        with metrics_path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                metric = str(row.get("metric") or "")
                if metric.startswith("roller_"):
                    by_metric[metric] = str(row.get("value") or "")
    return {key: _as_number(value) for key, value in by_metric.items()}


def _overlay_roller_desk(inspect: dict[str, Any], dest: Path, rec: dict[str, Any], cfg: RollerConfig | None) -> dict[str, Any]:
    prior = inspect.get("instrument") if isinstance(inspect.get("instrument"), dict) else {}
    inspect["instrument"] = instrument_from_composition(
        {
            "mode": prior.get("mode"),
            "seed": prior.get("seed"),
            "deterministic": {
                "break_even_probability": prior.get("break_even_probability"),
                "trade_ev": prior.get("trade_ev"),
                "weekly_ev": prior.get("weekly_ev"),
                "required_win_probability": prior.get("required_win_probability"),
            },
        }
    )
    stored = _stored_roller_metrics(dest, rec)
    roller_path = dest / str(rec.get("roller_filename") or "")
    if roller_path.is_file():
        try:
            parsed = parse_labs_csv(roller_path.read_bytes())
            observed = summarize_observed(parsed)
            inspect["desk"] = compute_roller_desk(parsed, observed, cfg=cfg)
            if stored.get("roller_P_min_bankroll_le_floor") is not None or stored.get("roller_mean_terminal_bankroll") is not None:
                inspect["risk_profile"] = risk_inspect_from_stored(stored)
            else:
                inspect["risk_profile"] = inspect_risk_profile_from_desk(
                    inspect["desk"],
                    research_result_hash=str(observed.get("result_hash") or ""),
                    cfg=cfg,
                )
            return inspect
        except SuperasiError:
            pass
    if stored.get("roller_break_even_probability") is not None:
        inspect["desk"] = {
            "status": "CONFIRMED",
            "break_even_probability": stored.get("roller_break_even_probability"),
            "trade_ev": stored.get("roller_trade_ev"),
            "weekly_ev": stored.get("roller_weekly_ev"),
            "required_win_probability": stored.get("roller_required_win_probability"),
            "p_used": stored.get("roller_p_used"),
            "source": "roller_payoff",
            "note": ROLLER_NOTE,
        }
        inspect["risk_profile"] = risk_inspect_from_stored(stored)
        return inspect
    inspect["desk"] = {
        "status": DATA_REQUIRED,
        "reason": DATA_REQUIRED,
        "break_even_probability": None,
        "trade_ev": None,
        "weekly_ev": None,
        "required_win_probability": None,
        "p_used": None,
        "source": "roller_payoff",
        "note": ROLLER_NOTE,
    }
    inspect["risk_profile"] = blank_risk_inspect()
    inspect["risk_profile"]["note"] = ROLLER_MC_NOTE
    return inspect


def load_base_inspect(result_id: str, cfg: RollerConfig | None = None) -> dict[str, Any] | None:
    rec = get_base_result(result_id, cfg)
    if rec is None:
        return None
    dest = phase_a_root(cfg) / result_id
    inspect = {**rec, **inspect_from_abase(rec, dest)}
    return _overlay_roller_desk(inspect, dest, rec, cfg)


def get_base_result(result_id: str, cfg: RollerConfig | None = None) -> dict[str, Any] | None:
    root = phase_a_root(cfg)
    dest = root / result_id
    meta_path = dest / "metadata.json"
    if not meta_path.is_file():
        return None
    rec = json.loads(meta_path.read_text(encoding="utf-8"))
    rec["has_abase_csv"] = (dest / str(rec.get("abase_filename") or "")).is_file()
    rec["has_roller_csv"] = (dest / str(rec.get("roller_filename") or "")).is_file()
    return rec


def get_base_csv_bytes(
    result_id: str,
    *,
    which: str = "base",
    cfg: RollerConfig | None = None,
) -> tuple[str, bytes] | None:
    rec = get_base_result(result_id, cfg)
    if rec is None:
        return None
    root = phase_a_root(cfg)
    dest = root / result_id
    if which == "roller":
        name = str(rec.get("roller_filename") or "")
    elif which == "base":
        name = str(rec.get("abase_filename") or "")
    else:
        raise SuperasiError("INVALID_CSV_WHICH", "which must be base or roller")
    path = dest / name
    if not path.is_file():
        return None
    return name, path.read_bytes()
