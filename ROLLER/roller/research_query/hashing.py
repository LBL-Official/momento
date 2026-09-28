"""Canonical AST hashes. Draft display order must not change identity."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from roller.research_query.models import OPERATION_SEMANTICS_VERSION, ResearchQuestion

CODE_VERSION = "research_query_v1.2_ops"


def _canon(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _canon(obj[k]) for k in sorted(obj)}
    if isinstance(obj, list):
        return [_canon(x) for x in obj]
    return obj


def dumps_canon(obj: Any) -> str:
    return json.dumps(_canon(obj), separators=(",", ":"), ensure_ascii=True)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def question_hash(question: ResearchQuestion) -> str:
    return sha256_hex(dumps_canon(question.to_dict()))


def _exact_diffs(filters: dict[str, Any]) -> list[int]:
    raw = filters.get("exactDiffs") or filters.get("exact_diffs") or []
    out: list[int] = []
    for item in raw:
        try:
            n = int(item)
        except (TypeError, ValueError):
            continue
        if n not in out:
            out.append(n)
    return sorted(out)


def _custom_range(filters: dict[str, Any]) -> tuple[int, int] | None:
    raw = filters.get("customRange") or filters.get("custom_range") or {}
    if not isinstance(raw, dict):
        return None
    lo = raw.get("min") if raw.get("min") is not None else raw.get("from")
    hi = raw.get("max") if raw.get("max") is not None else raw.get("to")
    if lo is None or hi is None or lo == "" or hi == "":
        return None
    try:
        a, b = int(lo), int(hi)
    except (TypeError, ValueError):
        return None
    return (min(a, b), max(a, b))


def normalize_state_filters(filters: dict[str, Any] | None) -> dict[str, Any] | None:
    """Non-default TE chips only. any/any is absent so existing hashes stay stable.

    Extra lead / MLB chips are omitted when unset. Adding them must not change
    NBA any/any hashes.
    """
    if not filters:
        return None
    side = str(filters.get("scoreSide") or filters.get("score_side") or "any")
    band = str(filters.get("absDiff") or filters.get("abs_diff") or "any")
    extra: dict[str, Any] = {}
    exact = _exact_diffs(filters)
    if exact:
        extra["exact_diffs"] = exact
    custom = _custom_range(filters)
    if custom:
        extra["custom_range"] = {"min": custom[0], "max": custom[1]}
    half = str(filters.get("half") or "").strip().lower()
    if half in {"top", "bottom"}:
        extra["half"] = half
    yes_bat = filters.get("yesBatting") if "yesBatting" in filters else filters.get("yes_batting")
    if yes_bat in (True, False, "true", "false", "batting", "pitching"):
        if yes_bat in (True, "true", "batting"):
            extra["yes_batting"] = True
        elif yes_bat in (False, "false", "pitching"):
            extra["yes_batting"] = False
    outs = filters.get("outs")
    if outs not in (None, "", "any"):
        if isinstance(outs, (list, tuple)):
            extra["outs"] = sorted({int(x) for x in outs})
        else:
            extra["outs"] = [int(outs)]
    count = str(filters.get("count") or "").strip()
    if count and count != "any":
        extra["count"] = count
    runners = str(filters.get("runners") or "").strip()
    if runners and runners != "any":
        extra["runners"] = runners
    point_scores = filters.get("tennisPointScores") or filters.get("tennis_point_scores")
    if isinstance(point_scores, (list, tuple)) and point_scores:
        extra["tennis_point_scores"] = sorted({str(x) for x in point_scores})
    serve = filters.get("tennisServe") or filters.get("tennis_serve")
    if isinstance(serve, (list, tuple)) and serve:
        extra["tennis_serve"] = sorted({str(x) for x in serve})
    elif isinstance(serve, str) and serve and serve != "any":
        extra["tennis_serve"] = [serve]
    events = filters.get("tennisEventStates") or filters.get("tennis_event_states")
    if isinstance(events, (list, tuple)) and events:
        extra["tennis_event_states"] = sorted({str(x) for x in events})
    for src, dest in (
        ("tennisSetLead", "tennis_set_lead"),
        ("tennis_set_lead", "tennis_set_lead"),
        ("tennisGameLead", "tennis_game_lead"),
        ("tennis_game_lead", "tennis_game_lead"),
        ("tennisPointLead", "tennis_point_lead"),
        ("tennis_point_lead", "tennis_point_lead"),
    ):
        raw_lead = filters.get(src)
        if isinstance(raw_lead, dict) and raw_lead:
            extra[dest] = _canon(raw_lead)
    if side == "any" and band == "any" and not extra:
        return None
    if extra:
        out: dict[str, Any] = {}
        if side != "any":
            out["score_side"] = side
        if band != "any":
            out["abs_diff"] = band
        out.update(extra)
        return out
    return {"score_side": side, "abs_diff": band}


def te_scope_funnel_label(requested: dict[str, Any] | None) -> str:
    """Funnel text for requested PIT chips. exact_diffs is not |Δ| None."""
    if not requested:
        return "TE scope"
    bits = [f"TE scope {requested.get('score_side') or 'any'}"]
    exact = requested.get("exact_diffs") or []
    if exact:
        bits.append("exact " + ",".join(str(x) for x in exact))
    band = requested.get("abs_diff")
    if band and str(band) != "any":
        bits.append(f"|Δ| {band}")
    custom = requested.get("custom_range") or {}
    if isinstance(custom, dict) and custom.get("min") is not None and custom.get("max") is not None:
        bits.append(f"range {custom['min']}–{custom['max']}")
    return " · ".join(bits)


def layer_hashes(
    question: ResearchQuestion,
    *,
    state: dict[str, Any] | None = None,
    exposure: dict[str, Any] | None = None,
) -> dict[str, str]:
    q = question.to_dict()
    state_obj = normalize_state_filters(state)
    qh = question_hash(question)
    if state_obj:
        qh = sha256_hex(dumps_canon({"question": q, "state_filters": state_obj}))
    if exposure:
        qh = sha256_hex(dumps_canon({"question_hash": qh, "exposure": exposure}))
    out = {
        "universe_hash": sha256_hex(dumps_canon(q["universe"])),
        "entry_hash": sha256_hex(dumps_canon(q["entry_conditions"])),
        "state_hash": sha256_hex(dumps_canon(state_obj or [])),
        "path_hash": sha256_hex(dumps_canon(q["path_conditions"])),
        "measurement_hash": sha256_hex(dumps_canon({"terminal": q["terminal"]})),
        "question_hash": qh,
        "code_version": CODE_VERSION,
        "operation_semantics_version": OPERATION_SEMANTICS_VERSION,
    }
    if exposure:
        out["exposure_hash"] = sha256_hex(dumps_canon(exposure))
    return out
