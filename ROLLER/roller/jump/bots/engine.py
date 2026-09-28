"""Research engine from a committed ITI slot. Not mlb_factory_v1. Not a submitter."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from roller.jump.errors import JumpError

ENGINE_KIND = "research_iti"
ENGINE_POINTER = "research_iti"
KNOWN_SPORTS = {
    "nba": "nba",
    "ncaab": "ncaab",
    "mlb": "mlb",
    "atp": "atp",
    "wta": "wta",
}


def _cents_to_e4(cents: Any) -> int | None:
    if cents is None or cents == "":
        return None
    return int(cents) * 100


def _token(raw: Any) -> str:
    return str(raw or "").strip().lower()


def sport_slug_from_iti(iti: dict[str, Any]) -> str:
    question = iti.get("question") if isinstance(iti.get("question"), dict) else {}
    universe = question.get("universe") if isinstance(question.get("universe"), dict) else {}
    sports = [_token(item) for item in list(universe.get("sports") or []) if _token(item)]
    leagues = [_token(item) for item in list(universe.get("leagues") or []) if _token(item)]
    if "tennis" in sports and not ({"atp", "wta"} & set(leagues)):
        raise JumpError("DATA_REQUIRED", "tennis ITI requires ATP or WTA; mixed tennis is refused")
    tokens = leagues or sports
    if not tokens:
        folder = _token(str(iti.get("source_folder") or iti.get("folder") or "").split("/")[0])
        tokens = [folder] if folder else []
    slugs: list[str] = []
    for token in tokens:
        slug = KNOWN_SPORTS.get(token)
        if slug and slug not in slugs:
            slugs.append(slug)
    if len(slugs) != 1:
        raise JumpError("DATA_REQUIRED", "ITI engine requires exactly one of NBA, NCAAB, MLB, ATP, WTA")
    return slugs[0]


def build_research_engine(iti: dict[str, Any]) -> dict[str, Any]:
    """Durable engine spec. Candle-path. Not 80/81. Worker stays OPERATION_REQUIRED."""
    if not iti:
        raise JumpError("DATA_REQUIRED", "ITI commit is required to build an engine")
    question = iti.get("question") if isinstance(iti.get("question"), dict) else None
    sport = sport_slug_from_iti(iti)
    entry_cents = iti.get("entry_cents")
    win_cents = iti.get("win_cents")
    loss_cents = iti.get("loss_cents")
    spec_ready = bool(question) and entry_cents is not None and win_cents is not None and loss_cents is not None
    engine = {
        "kind": ENGINE_KIND,
        "engine_pointer": ENGINE_POINTER,
        "strategy_pointer": iti.get("folder"),
        "source": "ROLLER → SuperASI A → SuperASI B → ITI",
        "sport": sport,
        "question": question,
        "prices": {
            "entry_cents": entry_cents,
            "win_cents": win_cents,
            "loss_cents": loss_cents,
            "entry_e4": _cents_to_e4(entry_cents),
            "win_e4": _cents_to_e4(win_cents),
            "loss_e4": _cents_to_e4(loss_cents),
        },
        "iti": {
            "folder": iti.get("folder"),
            "run_id": iti.get("run_id"),
            "slot_id": iti.get("slot_id"),
            "strategy_name": iti.get("strategy_name"),
            "lab_id": iti.get("lab_id"),
            "phase_a_result_id": iti.get("phase_a_result_id"),
            "phase_b_result_id": iti.get("phase_b_result_id"),
            "BASE_GRADE": iti.get("BASE_GRADE"),
            "DEBASE_GRADE": iti.get("DEBASE_GRADE"),
            "population": iti.get("population"),
            "metadata_sha256": iti.get("metadata_sha256"),
        },
        "implementation": {
            "spec": "IMPLEMENTED" if spec_ready else "DATA_REQUIRED",
            "worker": "OPERATION_REQUIRED",
            "submit": False,
            "signal": "research_iti_candle_path",
            "not_mlb_factory": True,
            "not_80_81": True,
        },
        "honesty": {
            "candle_path_not_fill": True,
            "iti_is_not_live_signal": True,
            "live_execution": False,
            "browser_is_not_engine": True,
        },
        "live_execution": False,
    }
    blob = json.dumps(
        {
            "sport": sport,
            "folder": iti.get("folder"),
            "slot_id": iti.get("slot_id"),
            "run_id": iti.get("run_id"),
            "prices": engine["prices"],
            "question": question,
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    engine["engine_fingerprint"] = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    return engine


def hydrate_research_engine(bot: dict[str, Any]) -> bool:
    """Attach the ITI engine and drop a stamped MLB factory. Does not save."""
    if bot.get("kind") != "iti":
        return False
    changed = False
    engine = bot.get("engine") if isinstance(bot.get("engine"), dict) else None
    if engine is None or engine.get("kind") != ENGINE_KIND:
        packed = dict(bot.get("iti") or {}) if isinstance(bot.get("iti"), dict) else {}
        packed["folder"] = bot.get("strategy_folder") or packed.get("folder")
        folder = str(packed.get("folder") or "").strip()
        if folder:
            try:
                from roller.jump.bots.source_iti import load_iti_commit

                loaded = load_iti_commit(folder, require_engine=True)
                engine = loaded.get("engine") if isinstance(loaded.get("engine"), dict) else None
                if loaded.get("question") and not (bot.get("iti") or {}).get("question"):
                    iti = dict(packed)
                    iti["question"] = loaded["question"]
                    bot["iti"] = iti
                    changed = True
            except JumpError:
                engine = None
        if engine is None and folder:
            try:
                engine = build_research_engine(packed)
            except JumpError:
                engine = None
        if engine:
            bot["engine"] = engine
            bot["engine_pointer"] = engine.get("engine_pointer")
            bot["strategy_pointer"] = engine.get("strategy_pointer")
            bot["sport"] = engine.get("sport")
            changed = True
    if bot.get("factory_id") or bot.get("factory_version"):
        bot["factory_id"] = None
        bot["factory_version"] = None
        changed = True
    return changed
