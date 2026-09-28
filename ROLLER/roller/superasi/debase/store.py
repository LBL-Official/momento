"""Phase B Final Results disk store. Sibling of phase_a. Not the warehouse."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roller import desk_settings
from roller.config import RollerConfig
from roller.labs.schema import sanitize_name
from roller.labs.store import roller_csv_population
from roller.superasi.base.ingest import parse_labs_csv
from roller.superasi.base.observed import summarize_observed
from roller.superasi.base.roller_desk import (
    DATA_REQUIRED,
    ROLLER_NOTE,
    blank_risk_inspect,
    compute_roller_desk,
    inspect_risk_profile_from_desk,
    instrument_from_composition,
    risk_inspect_from_stored,
)
from roller.superasi.debase.iqr import working_p_from_observed
from roller.superasi.debase.versions import DEBASE_DESK_NOTE, DEBASE_MC_NOTE, P_WORKING_BASIS
from roller.superasi.debase.export_csv import csv_filename, render_csv
from roller.superasi.debase.versions import GRADE_CONFIG_VERSION, SUPERASI_DEBASE_VERSION, TRADES_PER_WEEK
from roller.superasi.models import SuperasiError


def phase_b_root(cfg: RollerConfig | None = None) -> Path:
    cfg = cfg or RollerConfig()
    return Path(cfg.root) / "superasi_labs" / "phase_b"


def _folder_for(name: str, phase_a_id: str, root: Path) -> str:
    base = sanitize_name(name)
    dest = root / base
    if not dest.is_dir():
        return base
    meta_path = dest / "metadata.json"
    if meta_path.is_file():
        rec = json.loads(meta_path.read_text(encoding="utf-8"))
        if str(rec.get("phase_a_result_id") or "") in {"", phase_a_id}:
            return base
    return f"{base}__{phase_a_id[:8]}"


def save_debase_result(
    *,
    payload: dict[str, Any],
    roller_bytes: bytes,
    roller_filename: str,
    abase_bytes: bytes,
    abase_filename: str,
    cfg: RollerConfig | None = None,
) -> dict[str, Any]:
    cfg = cfg or RollerConfig()
    root = phase_b_root(cfg)
    root.mkdir(parents=True, exist_ok=True)
    phase_a_id = str(payload.get("phase_a_result_id") or "")
    strategy = sanitize_name(str(payload.get("strategy_name") or "Untitled"))
    folder = _folder_for(strategy, phase_a_id, root)
    dest = root / folder
    dest.mkdir(parents=True, exist_ok=True)
    created_at = str(payload.get("created_at") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    body = dict(payload)
    body["created_at"] = created_at
    draft = render_csv(body, debase_hash="")
    digest = hashlib.sha256(draft.encode("utf-8")).hexdigest()
    csv_text = render_csv(body, debase_hash=digest)
    stored_hash = hashlib.sha256(csv_text.encode("utf-8")).hexdigest()
    debase_name = csv_filename(strategy)
    (dest / roller_filename).write_bytes(roller_bytes)
    (dest / abase_filename).write_bytes(abase_bytes)
    (dest / debase_name).write_text(csv_text, encoding="utf-8", newline="\n")
    degrading = body.get("degrading") if isinstance(body.get("degrading"), dict) else {}
    question = body.get("question")
    metadata = {
        "result_id": folder,
        "folder": folder,
        "strategy_name": strategy,
        "source_lab_id": body.get("source_lab_id"),
        "phase_a_result_id": phase_a_id,
        "created_at": created_at,
        "roller_filename": roller_filename,
        "abase_filename": abase_filename,
        "debase_filename": debase_name,
        "source_csv_sha256": body.get("source_csv_sha256"),
        "abase_sha256": body.get("abase_sha256"),
        "debase_payload_sha256": digest,
        "debase_sha256": stored_hash,
        "BASE_GRADE": degrading.get("BASE_GRADE"),
        "DEBASE_GRADE": degrading.get("DEBASE_GRADE"),
        "components": degrading.get("components"),
        "bottleneck": degrading.get("bottleneck"),
        "superasi_version": SUPERASI_DEBASE_VERSION,
        "grade_config_version": GRADE_CONFIG_VERSION,
        "question": question,
        "question_status": body.get("question_status"),
        "question_sha256": body.get("question_sha256"),
        "plan_hash": (body.get("observed") or {}).get("plan_hash") if isinstance(body.get("observed"), dict) else "",
        "result_hash": (body.get("observed") or {}).get("result_hash") if isinstance(body.get("observed"), dict) else "",
        "artifact": "superasi_bdebase",
        "phase": "B",
        **desk_settings.stamp(cfg=cfg),
    }
    (dest / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return {
        **metadata,
        "debase_bytes": len(csv_text.encode("utf-8")),
        "roller_bytes": len(roller_bytes),
        "abase_bytes": len(abase_bytes),
        "csv_text": csv_text,
        "payload": body,
    }


def list_debase_results(cfg: RollerConfig | None = None) -> list[dict[str, Any]]:
    root = phase_b_root(cfg)
    if not root.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        meta_path = folder / "metadata.json"
        if not meta_path.is_file():
            continue
        rec = json.loads(meta_path.read_text(encoding="utf-8"))
        rec["path_folder"] = folder.name
        rec.pop("question", None)
        rec.update(roller_csv_population(folder / str(rec.get("roller_filename") or "")))
        items.append(rec)
    items.sort(key=lambda r: (str(r.get("created_at") or ""), str(r.get("result_id") or "")), reverse=True)
    return items


def get_debase_result(result_id: str, cfg: RollerConfig | None = None) -> dict[str, Any] | None:
    root = phase_b_root(cfg)
    dest = root / result_id
    meta_path = dest / "metadata.json"
    if not meta_path.is_file():
        return None
    rec = json.loads(meta_path.read_text(encoding="utf-8"))
    rec["has_debase_csv"] = (dest / str(rec.get("debase_filename") or "")).is_file()
    rec["has_abase_csv"] = (dest / str(rec.get("abase_filename") or "")).is_file()
    rec["has_roller_csv"] = (dest / str(rec.get("roller_filename") or "")).is_file()
    return rec


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


def _cents_to_dollars(raw: object) -> float | None:
    number = _as_number(raw)
    if number is None:
        return None
    return float(number) / 100.0


def inspect_from_debase(rec: dict[str, Any], dest: Path) -> dict[str, Any]:
    """Rebuild the Phase B inspect layout from SuperasiBDeBase CSV. Facts only."""
    csv_path = dest / str(rec.get("debase_filename") or "")
    metrics: dict[tuple[str, str], str] = {}
    checks: list[dict[str, Any]] = []
    components: dict[str, str] = {}
    weekly: dict[int, dict[str, Any]] = {}
    sensitivity: dict[str, dict[str, Any]] = {}
    if csv_path.is_file():
        with csv_path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                rt = str(row.get("record_type") or "")
                metric = str(row.get("metric") or "")
                value = str(row.get("value") or "")
                if rt == "devalidation" and metric:
                    checks.append({"id": metric, "ok": value == "PASS", "severity": str(row.get("source") or "")})
                elif rt == "degrading" and metric.endswith("_grade"):
                    components[metric[: -len("_grade")]] = value
                elif rt == "weekly":
                    prob = re.fullmatch(r"wins_(\d+)_probability", metric)
                    win_row = re.fullmatch(r"wins_(\d+)", metric)
                    if prob:
                        wins = int(prob.group(1))
                        weekly.setdefault(wins, {"wins": wins, "losses": TRADES_PER_WEEK - wins})
                        weekly[wins]["probability"] = _as_number(value)
                    elif win_row:
                        wins = int(win_row.group(1))
                        weekly.setdefault(wins, {"wins": wins, "losses": TRADES_PER_WEEK - wins})
                        weekly[wins]["weekly_return"] = _as_number(value)
                elif rt == "sensitivity":
                    weekly_ev = re.fullmatch(r"p_(.+)_weekly_ev", metric)
                    floor = re.fullmatch(r"p_(.+)_P_floor", metric)
                    target = re.fullmatch(r"p_(.+)_P_target", metric)
                    key = None
                    field = None
                    if weekly_ev:
                        key, field = weekly_ev.group(1), "weekly_ev"
                    elif floor:
                        key, field = floor.group(1), "P_min_bankroll_le_floor"
                    elif target:
                        key, field = target.group(1), "P_final_ge_target"
                    if key and field:
                        sensitivity.setdefault(key, {"p": _as_number(key)})
                        sensitivity[key][field] = _as_number(value)
                elif rt and metric:
                    metrics[(rt, metric)] = value

    def metric(rt: str, name: str) -> float | int | str | None:
        raw = metrics.get((rt, name), "")
        number = _as_number(raw)
        if number is not None:
            return number
        return raw or None

    stored_components = rec.get("components") if isinstance(rec.get("components"), dict) else {}
    gate_value = metric("degrading", "A_PLUS_INSTRUMENT_GATE")
    reasons_raw = str(metrics.get(("degrading", "A_PLUS_INSTRUMENT_GATE_reasons")) or "")
    bankroll_cents = rec.get("bankroll_cents") if rec.get("bankroll_cents") is not None else metric("meta", "bankroll_cents")
    allocation_bps = rec.get("allocation_bps") if rec.get("allocation_bps") is not None else metric("meta", "allocation_bps")
    floor_cents = rec.get("floor_cents") if rec.get("floor_cents") is not None else metric("meta", "floor_cents")
    target_cents = rec.get("target_cents") if rec.get("target_cents") is not None else metric("meta", "target_cents")
    disagree = metric("observed", "risk_reward_methods_disagree")
    return {
        "result_id": rec.get("result_id"),
        "strategy_name": rec.get("strategy_name"),
        "source_lab_id": rec.get("source_lab_id"),
        "phase_a_result_id": rec.get("phase_a_result_id"),
        "created_at": rec.get("created_at"),
        "BASE_GRADE": rec.get("BASE_GRADE") or metric("grading", "BASE_GRADE"),
        "DEBASE_GRADE": rec.get("DEBASE_GRADE") or metric("degrading", "DEBASE_GRADE"),
        "components": stored_components or components,
        "bottleneck": rec.get("bottleneck") or metric("degrading", "bottleneck"),
        "raise_requires": metric("degrading", "raise_requires"),
        "composite_score": _as_number(metric("degrading", "composite_score")),
        "borderline": str(rec.get("borderline") or metric("degrading", "borderline") or "").lower() == "true",
        "capped_to_base": str(metric("degrading", "capped_to_base") or "").lower() == "true",
        "DEBASE_GRADE_uncapped": metric("degrading", "DEBASE_GRADE_uncapped"),
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
        "instrument": instrument_from_composition(
            {
                "mode": "A",
                "deterministic": {
                    "break_even_probability": metric("decomposition", "desk_break_even_probability"),
                    "trade_ev": metric("decomposition", "desk_trade_ev"),
                    "weekly_ev": metric("decomposition", "desk_weekly_ev"),
                    "required_win_probability": 0.70,
                },
            }
        ),
        "p_working": metric("observed", "p_working"),
        "p_working_basis": metric("observed", "p_working_basis") or P_WORKING_BASIS,
        "p_iqr1": metric("observed", "p_iqr1"),
        "p_iqr3": metric("observed", "p_iqr3"),
        "p_be_roller": metric("observed", "p_be_roller"),
        "ev_debase": metric("observed", "ev_debase"),
        "gross_ev": metric("observed", "gross_ev"),
        "risk_reward": metric("observed", "risk_reward"),
        "risk_reward_plan": metric("observed", "risk_reward_plan"),
        "risk_reward_trade_mean": metric("observed", "risk_reward_trade_mean"),
        "risk_reward_display": metric("observed", "risk_reward_display"),
        "risk_reward_basis": metric("observed", "risk_reward_basis"),
        "risk_reward_methods_disagree": str(disagree).lower() == "true" if disagree not in (None, "") else False,
        "risk_reward_ratio_of_means": metric("decomposition", "risk_reward_ratio_of_means"),
        "desk_settings": {
            "bankroll_dollars": _cents_to_dollars(bankroll_cents),
            "allocation_pct": float(allocation_bps) / 100.0 if _as_number(allocation_bps) is not None else None,
            "floor_dollars": _cents_to_dollars(floor_cents),
            "target_dollars": _cents_to_dollars(target_cents),
        },
        "instrument_gate": {
            "value": gate_value,
            "passed": str(gate_value or "").upper() == "PASS",
            "reasons": [part for part in reasons_raw.split(",") if part],
            "note": "Valuation gate only. Not a letter. Not BASE_GRADE. Not DEBASE_GRADE.",
        },
        "observed": {
            "population": metric("observed", "population"),
            "wins": metric("observed", "wins"),
            "losses": metric("observed", "losses"),
            "win_rate": metric("observed", "win_rate"),
            "gross_ev": metric("observed", "gross_ev"),
            "wilson_lower": metric("observed", "wilson_lower"),
            "wilson_upper": metric("observed", "wilson_upper"),
            "p_iqr1": metric("observed", "p_iqr1"),
            "p_iqr3": metric("observed", "p_iqr3"),
        },
        "valuation": {
            "R_w": metric("decomposition", "R_w"),
            "R_l": metric("decomposition", "R_l"),
            "weekly_ev": metric("decomposition", "weekly_ev"),
            "compounded_20_week": metric("decomposition", "compounded_20_week"),
            "weekly_table": [weekly[key] for key in sorted(weekly)],
            "sensitivity": [sensitivity[key] for key in sorted(sensitivity, key=lambda item: _as_number(item) or 0.0)],
        },
        "risk_profile": blank_risk_inspect(
            public={
                "bankroll_dollars": _cents_to_dollars(bankroll_cents),
                "allocation_pct": float(allocation_bps) / 100.0 if _as_number(allocation_bps) is not None else None,
                "floor_dollars": _cents_to_dollars(floor_cents),
                "target_dollars": _cents_to_dollars(target_cents),
            }
        ),
        "question_status": rec.get("question_status") or metric("meta", "question_status"),
        "checks": checks,
        "honesty": {
            "risk_not": "candle_path_not_fill",
            "live_grade": "UNAVAILABLE",
            "fees": "UNAVAILABLE",
            "fills": "UNAVAILABLE",
            "net_ev": "NOT_COMPUTABLE",
        },
        "files": {
            "roller_filename": rec.get("roller_filename"),
            "abase_filename": rec.get("abase_filename"),
            "debase_filename": rec.get("debase_filename"),
            "debase_sha256": rec.get("debase_sha256"),
            "abase_sha256": rec.get("abase_sha256"),
            "source_csv_sha256": rec.get("source_csv_sha256"),
        },
    }


def _stored_roller_metrics(dest: Path, rec: dict[str, Any]) -> dict[str, Any]:
    by_metric: dict[str, str] = {}
    metrics_path = dest / str(rec.get("debase_filename") or "")
    if metrics_path.is_file():
        with metrics_path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                metric = str(row.get("metric") or "")
                if metric.startswith("roller_"):
                    by_metric[metric] = str(row.get("value") or "")
    return {key: _as_number(value) for key, value in by_metric.items()}


def _overlay_roller_report(inspect: dict[str, Any], dest: Path, rec: dict[str, Any], cfg: RollerConfig | None) -> dict[str, Any]:
    stored = _stored_roller_metrics(dest, rec)
    public = inspect.get("desk_settings") if isinstance(inspect.get("desk_settings"), dict) else None
    roller_path = dest / str(rec.get("roller_filename") or "")
    if roller_path.is_file():
        try:
            parsed = parse_labs_csv(roller_path.read_bytes())
            observed = summarize_observed(parsed)
            p_used = inspect.get("p_working")
            if p_used is None:
                p_used = inspect.get("p_iqr1")
            if p_used is None:
                p_used = working_p_from_observed(observed)["p_working"]
            inspect["desk"] = compute_roller_desk(parsed, observed, cfg=cfg, p_used=float(p_used))
            inspect["desk"] = {**inspect["desk"], "note": DEBASE_DESK_NOTE, "p_basis": P_WORKING_BASIS}
            if stored.get("roller_P_min_bankroll_le_floor") is not None or stored.get("roller_mean_terminal_bankroll") is not None:
                inspect["risk_profile"] = risk_inspect_from_stored(stored, public=public)
            else:
                inspect["risk_profile"] = inspect_risk_profile_from_desk(
                    inspect["desk"],
                    research_result_hash=str(observed.get("result_hash") or ""),
                    cfg=cfg,
                    public=public,
                )
            inspect["risk_profile"] = {**inspect["risk_profile"], "note": DEBASE_MC_NOTE, "p_basis": P_WORKING_BASIS}
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
            "note": DEBASE_DESK_NOTE,
            "p_basis": P_WORKING_BASIS,
        }
        inspect["risk_profile"] = risk_inspect_from_stored(stored, public=public)
    return inspect


def load_debase_inspect(result_id: str, cfg: RollerConfig | None = None) -> dict[str, Any] | None:
    rec = get_debase_result(result_id, cfg)
    if rec is None:
        return None
    dest = phase_b_root(cfg) / result_id
    inspect = {**rec, **inspect_from_debase(rec, dest)}
    return _overlay_roller_report(inspect, dest, rec, cfg)


def get_debase_csv_bytes(
    result_id: str,
    *,
    which: str = "debase",
    cfg: RollerConfig | None = None,
) -> tuple[str, bytes] | None:
    rec = get_debase_result(result_id, cfg)
    if rec is None:
        return None
    root = phase_b_root(cfg)
    dest = root / result_id
    if which == "roller":
        name = str(rec.get("roller_filename") or "")
    elif which == "abase":
        name = str(rec.get("abase_filename") or "")
    elif which == "debase":
        name = str(rec.get("debase_filename") or "")
    else:
        raise SuperasiError("INVALID_CSV_WHICH", "which must be debase, abase, or roller")
    path = dest / name
    if not path.is_file():
        return None
    return name, path.read_bytes()
