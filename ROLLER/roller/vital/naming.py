"""Vital Bot Standard naming. Shared convention. Not a shared bot implementation."""

from __future__ import annotations

import re

from roller.vital.errors import VitalError
from roller.vital.mlb_001.boundary import FORBIDDEN_AS_BOT_ID
from roller.vital.mlb_001.identity import BOT_ALIASES, BOT_ID

BOT_ID_RE = re.compile(r"^([a-z][a-z0-9]+)-([0-9]{3})$")

BOT_STANDARD_PHASE = {
    "1": "ACCEPTED",
    "2": "IMPLEMENTED",
    "3": "IMPLEMENTED",
    "4": "IMPLEMENTED",
    "5": "IMPLEMENTED",
    "6": "IMPLEMENTED",
}


def parse_bot_id(bot_id: str) -> tuple[str, int]:
    token = str(bot_id or "").strip()
    if token in FORBIDDEN_AS_BOT_ID:
        raise VitalError("INVALID_BOT_ID", f"sport dump is not a bot_id: {token}")
    match = BOT_ID_RE.fullmatch(token)
    if match is None:
        raise VitalError("INVALID_BOT_ID", f"bot_id must be sport-nnn: {bot_id}")
    sport, ordinal = match.group(1), int(match.group(2))
    if ordinal < 1:
        raise VitalError("INVALID_BOT_ID", f"bot ordinal must be >= 001: {bot_id}")
    return sport, ordinal


def display_name(bot_id: str) -> str:
    sport, ordinal = parse_bot_id(bot_id)
    return f"{sport.upper()} Bot {ordinal:03d}"


def package_module(bot_id: str) -> str:
    sport, ordinal = parse_bot_id(bot_id)
    return f"roller.vital.{sport}_{ordinal:03d}"


def folder_relpath(bot_id: str) -> str:
    parse_bot_id(bot_id)
    return f"research/vital/bots/{bot_id}"


def next_sport_bot_id(sport: str, existing: list[str] | None = None) -> str:
    """Next unused {sport}-NNN. mlb-001 is reserved even if the folder is missing."""
    slug = str(sport or "").strip().lower()
    if not slug or slug in {"vital", "jump"}:
        raise VitalError("INVALID_BOT_ID", f"invalid sport for bot_id: {sport}")
    parse_bot_id(f"{slug}-001")
    highest = 1 if slug == "mlb" else 0
    for token in existing or []:
        try:
            found, ordinal = parse_bot_id(token)
        except VitalError:
            continue
        if found == slug:
            highest = max(highest, ordinal)
    return f"{slug}-{highest + 1:03d}"


def next_mlb_bot_id(existing: list[str] | None = None) -> str:
    """Next unused mlb-NNN. mlb-001 is reserved even if the folder is missing."""
    return next_sport_bot_id("mlb", existing)


def resolve_canonical_bot_id(raw: str) -> str:
    token = str(raw or "").strip()
    if token == BOT_ID or token in BOT_ALIASES:
        return BOT_ID
    parse_bot_id(token)
    return token
