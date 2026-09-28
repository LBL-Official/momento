"""STAX universe compatibility. Compiled values only. No date expansion."""

from __future__ import annotations

from typing import Any

from roller.research_query.season_dates import normalize_season_id
from roller.research_query.season_mapping import normalize_league, warehouse_season
from roller.research_query.sport_family import FAMILY_UNKNOWN, families_in
from roller.stax.models import CanonicalUniverse, ConstraintViolation, _empty_to_none


CONSTRAINT_MESSAGE = "SPORT / LEAGUE / TIMEFRAME MUST MATCH"


def _canon_league(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        raise ConstraintViolation("league required", {"field": "league_set"})
    try:
        return normalize_league(text)
    except ValueError:
        return text.upper()


def _canon_season(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        raise ConstraintViolation("season required", {"field": "seasons"})
    try:
        return warehouse_season(text)
    except Exception:
        return normalize_season_id(text)


def _compiled_question_dict(source: dict[str, Any] | None) -> dict[str, Any] | None:
    """Prefer an already-compiled ResearchQuestion over UI / client universe fields."""
    source = source or {}
    question = source.get("question")
    if isinstance(question, dict) and isinstance(question.get("universe"), dict):
        return question
    compile_block = source.get("compile")
    if isinstance(compile_block, dict):
        q = compile_block.get("question")
        if isinstance(q, dict) and isinstance(q.get("universe"), dict):
            return q
    result = source.get("result")
    if isinstance(result, dict):
        return _compiled_question_dict(result)
    return None


def extract_raw_universe(source: dict[str, Any] | None) -> dict[str, Any]:
    """Compiled ResearchQuestion.universe only. Never UI labels or client aliases."""
    source = source or {}
    question = _compiled_question_dict(source)
    if question is not None:
        return _normalize_keys(question["universe"])
    for key in ("draft", "workflow_draft"):
        draft = source.get(key)
        if not isinstance(draft, dict):
            continue
        from roller.research_query.compiler import compile_draft

        compiled = compile_draft(draft)
        return _normalize_keys(compiled.question.to_dict()["universe"])
    raise ConstraintViolation(
        "research object has no compiled universe",
        {"reason": "UNIVERSE_MISSING"},
    )


def _looks_like_universe(raw: dict[str, Any]) -> bool:
    return any(
        k in raw
        for k in (
            "sports",
            "leagues",
            "seasons",
            "date_from",
            "dateFrom",
            "league_set",
            "sport_family",
        )
    )


def _normalize_keys(raw: dict[str, Any]) -> dict[str, Any]:
    if raw.get("league_set") or raw.get("sport_family"):
        return {
            "sports": list(raw.get("sports") or ()),
            "leagues": list(raw.get("leagues") or raw.get("league_set") or ()),
            "seasons": list(raw.get("seasons") or ()),
            "date_from": raw.get("date_from"),
            "date_to": raw.get("date_to"),
            "sport_family": raw.get("sport_family"),
        }
    return {
        "sports": list(raw.get("sports") or ()),
        "leagues": list(raw.get("leagues") or ()),
        "seasons": list(raw.get("seasons") or ()),
        "date_from": raw.get("date_from", raw.get("dateFrom")),
        "date_to": raw.get("date_to", raw.get("dateTo")),
    }


def canonicalize_universe(universe: dict[str, Any] | CanonicalUniverse) -> CanonicalUniverse:
    if isinstance(universe, CanonicalUniverse):
        return universe
    if universe.get("sport_family") and universe.get("league_set") is not None:
        if "sports" not in universe and "leagues" not in universe:
            return CanonicalUniverse.from_dict(universe)
    sports = tuple(str(s) for s in (universe.get("sports") or ()) if s)
    leagues = tuple(_canon_league(x) for x in (universe.get("leagues") or ()))
    seasons = tuple(sorted({_canon_season(x) for x in (universe.get("seasons") or ())}))
    league_set = tuple(sorted(set(leagues)))
    families = families_in(sports, league_set)
    if len(families) == 1:
        sport_family = next(iter(families))
    elif len(families) > 1:
        sport_family = "mixed"
    else:
        sport_family = str(universe.get("sport_family") or FAMILY_UNKNOWN)
    return CanonicalUniverse(
        sport_family=sport_family,
        league_set=league_set,
        seasons=seasons,
        date_from=_empty_to_none(universe.get("date_from")),
        date_to=_empty_to_none(universe.get("date_to")),
    )


def universe_from_source(source: dict[str, Any] | None) -> CanonicalUniverse:
    return canonicalize_universe(extract_raw_universe(source))


def diff_universes(locked: CanonicalUniverse, candidate: CanonicalUniverse) -> dict[str, Any]:
    mismatches: dict[str, Any] = {}
    if locked.sport_family != candidate.sport_family:
        mismatches["sport"] = {
            "locked": locked.sport_family,
            "candidate": candidate.sport_family,
        }
    if locked.league_set != candidate.league_set:
        mismatches["league_set"] = {
            "locked": list(locked.league_set),
            "candidate": list(candidate.league_set),
        }
    if locked.seasons != candidate.seasons:
        mismatches["seasons"] = {
            "locked": list(locked.seasons),
            "candidate": list(candidate.seasons),
        }
    if locked.date_from != candidate.date_from or locked.date_to != candidate.date_to:
        mismatches["timeframe"] = {
            "locked": {"date_from": locked.date_from, "date_to": locked.date_to},
            "candidate": {"date_from": candidate.date_from, "date_to": candidate.date_to},
        }
    return mismatches


def assert_compatible(
    locked: CanonicalUniverse | dict[str, Any],
    candidate: CanonicalUniverse | dict[str, Any],
) -> CanonicalUniverse:
    a = canonicalize_universe(locked) if not isinstance(locked, CanonicalUniverse) else locked
    b = canonicalize_universe(candidate) if not isinstance(candidate, CanonicalUniverse) else candidate
    mismatches = diff_universes(a, b)
    if mismatches:
        raise ConstraintViolation(CONSTRAINT_MESSAGE, mismatches)
    return a


def assert_timeframe_unchanged(
    saved: CanonicalUniverse,
    executed: CanonicalUniverse,
) -> None:
    """Automation must not rewrite the saved window."""
    if (
        saved.date_from != executed.date_from
        or saved.date_to != executed.date_to
        or saved.seasons != executed.seasons
    ):
        raise ConstraintViolation(
            "automation must not expand or rewrite the saved timeframe",
            {
                "saved": saved.to_dict(),
                "executed": executed.to_dict(),
            },
        )
