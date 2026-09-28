"""Deterministic crosswalk: charted tennis match <-> Kalshi tennis event.

RESEARCH ONLY. No orders, no pricing, no network.

NO I/O
------
Kalshi data is passed in already loaded (list of dicts, or anything with
``to_dict("records")``). This module never opens a socket and never reads the
warehouse, so the runtime query path can call it with zero network
dependency.

METHOD PRIORITY
---------------
1. ``UUID_PAIR_DATE``              - Kalshi ``custom_strike.tennis_competitor``
                                     UUID pair + date. Strongest key; requires
                                     the caller to supply a name->UUID registry
                                     because MCP carries no UUIDs.
2. ``FULL_NAME_PAIR_DATE``         - normalized full-name pair + date, with a
                                     +/-N day tolerance for timezone rollover.
                                     The offset actually used is recorded.
3. ``SURNAME_PAIR_DATE_TOURNAMENT`` - normalized surname pair + date +
                                     tournament agreement.
4. Fail closed - ``UNMATCHED`` or ``AMBIGUOUS``. Never a guess.

FAIL-CLOSED RULES
-----------------
* More than one Kalshi candidate at the best date tier -> ``AMBIGUOUS``.
* More than one charted match claiming the same Kalshi event -> all of them
  demoted to ``AMBIGUOUS``.
* Missing date on either side -> ``UNMATCHED``, never a name-only match.
* Surname method additionally requires tournament agreement, because surnames
  alone repeat across events.

KNOWN UNMATCHABLE
-----------------
Kalshi does not list ITF events or Davis Cup / BJK Cup / United Cup team
ties. Those charted matches are expected to end ``UNMATCHED`` with reason
``NOT_LISTED_COMPETITION`` and must not be forced into a match.

SOURCE LICENSE: the charted side is CC BY-NC-SA 4.0 (NonCommercial,
attribution Jeff Sackmann). See ``roller.tennis.pbp.LICENSE_FIELDS``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from roller.tennis.names import (
    full_name_key,
    normalize_name,
    pair_key,
    split_versus,
    surname_keys,
    surname_pair_matches,
)

METHOD_UUID = "UUID_PAIR_DATE"
METHOD_FULL_NAME = "FULL_NAME_PAIR_DATE"
METHOD_SURNAME = "SURNAME_PAIR_DATE_TOURNAMENT"
METHOD_UNMATCHED = "UNMATCHED"
METHOD_AMBIGUOUS = "AMBIGUOUS"
METHOD_PRIORITY: tuple[str, ...] = (METHOD_UUID, METHOD_FULL_NAME, METHOD_SURNAME)

STATUS_MATCHED = "MATCHED"
STATUS_AMBIGUOUS = "AMBIGUOUS"
STATUS_UNMATCHED = "UNMATCHED"

# String enum, not a number: confidence is a category, never arithmetic.
CONFIDENCE_EXACT = "EXACT"
CONFIDENCE_HIGH = "HIGH"
CONFIDENCE_MEDIUM = "MEDIUM"
CONFIDENCE_NONE = "NONE"
CONFIDENCE_BY_METHOD: dict[str, str] = {
    METHOD_UUID: CONFIDENCE_EXACT,
    METHOD_FULL_NAME: CONFIDENCE_HIGH,
    METHOD_SURNAME: CONFIDENCE_MEDIUM,
}

REASON_NO_MCP_DATE = "NO_MCP_DATE"
REASON_NO_CANDIDATE = "NO_CANDIDATE"
REASON_NO_USABLE_KEY = "NO_USABLE_KEY"
REASON_MULTIPLE_EVENTS = "MULTIPLE_KALSHI_CANDIDATES"
REASON_MULTIPLE_MATCHES = "MULTIPLE_MCP_MATCHES_PER_EVENT"
REASON_NOT_LISTED = "NOT_LISTED_COMPETITION"

DEFAULT_DATE_TOLERANCE_DAYS = 2

# MCP circuit token -> Kalshi series. Used only to narrow the candidate pool;
# a Kalshi event with no series ticker is never excluded by it.
SERIES_BY_TOUR: dict[str, str] = {"M": "KXATPMATCH", "W": "KXWTAMATCH"}

# Competition name tokens that carry no discriminating information.
_GENERIC_COMPETITION_TOKENS = frozenset(
    {
        "atp",
        "wta",
        "men",
        "mens",
        "women",
        "womens",
        "singles",
        "doubles",
        "tour",
        "masters",
        "championship",
        "championships",
        "international",
        "internationals",
        "classic",
        "250",
        "500",
        "1000",
        "finals",
        "cup",
        "open",
    }
)

# Curated equivalences between MCP tournament names and Kalshi competition
# names. These are documented real-world facts, not inferred aliases. Keys and
# values are normalized tokens.
_COMPETITION_ALIASES: dict[str, frozenset[str]] = {
    "roland": frozenset({"french"}),
    "garros": frozenset({"french"}),
    "french": frozenset({"roland", "garros"}),
    "flushing": frozenset({"us"}),
}

# Competitions MCP charts that Kalshi is known not to list as head-to-head
# match markets. Matched on normalized tournament tokens.
_NOT_LISTED_TOKENS = frozenset({"davis", "bjk", "fed", "united", "laver", "itf", "billie", "jean", "king"})


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_date(value: Any) -> date | None:
    """Accept 'YYYY-MM-DD' or an ISO datetime and take its date part. Fail closed."""
    if isinstance(value, date):
        return value
    text = _text(value)
    if text is None or len(text) < 10:
        return None
    head = text[:10]
    try:
        year, month, day = (int(part) for part in head.split("-"))
        return date(year, month, day)
    except (TypeError, ValueError):
        return None


def _competition_tokens(raw: Any) -> frozenset[str]:
    tokens = {t for t in normalize_name(raw).split() if t and t not in _GENERIC_COMPETITION_TOKENS}
    expanded = set(tokens)
    for token in tokens:
        expanded |= _COMPETITION_ALIASES.get(token, frozenset())
    return frozenset(expanded)


def competitions_agree(mcp_tournament: Any, kalshi_competition: Any) -> bool:
    """True when the two competition names share a discriminating token."""
    left = _competition_tokens(mcp_tournament)
    right = _competition_tokens(kalshi_competition)
    if not left or not right:
        return False
    return bool(left & right)


def is_not_listed_competition(mcp_tournament: Any) -> bool:
    """Known team-event / ITF competitions Kalshi does not list."""
    tokens = set(normalize_name(mcp_tournament).split())
    return bool(tokens & _NOT_LISTED_TOKENS)


@dataclass(frozen=True)
class KalshiTennisEvent:
    """Normalized read-only view of one Kalshi tennis event."""

    event_ticker: str
    series_ticker: str | None
    event_date: date | None
    competition: str | None
    title: str | None
    uuid_pair: frozenset[str] | None
    full_name_pair: frozenset[str] | None
    surname_pair: tuple[frozenset[str], frozenset[str]] | None
    market_ticker_by_uuid: dict[str, str] = field(default_factory=dict)
    market_ticker_by_name_key: dict[str, str] = field(default_factory=dict)
    uuid_by_name_key: dict[str, str] = field(default_factory=dict)


def _event_rows(kalshi_events: Any) -> list[Mapping[str, Any]]:
    if kalshi_events is None:
        return []
    to_dict = getattr(kalshi_events, "to_dict", None)
    if callable(to_dict):  # pandas DataFrame
        return list(to_dict("records"))
    return [row for row in kalshi_events if isinstance(row, Mapping)]


def _series_from_ticker(event_ticker: str | None) -> str | None:
    if not event_ticker or "-" not in event_ticker:
        return None
    # The event ticker is SERIES-CODEBLOB. Only the series prefix is split off;
    # the code blob is deliberately never split further (verified: 19 of 1,600
    # sampled events break a fixed 3+3 date/player split).
    return event_ticker.split("-", 1)[0].strip() or None


_DATE_KEYS = (
    "event_date",
    "date",
    "strike_date",
    "game_date",
    "expected_expiration_time",
    "close_time",
    "expiration_time",
)


def normalize_kalshi_event(raw: Mapping[str, Any]) -> KalshiTennisEvent | None:
    """Normalize one Kalshi event dict. Returns None when it has no ticker."""
    event_ticker = _text(raw.get("event_ticker") or raw.get("ticker"))
    if event_ticker is None:
        return None

    series = _text(raw.get("series_ticker")) or _series_from_ticker(event_ticker)

    event_date = None
    for key in _DATE_KEYS:
        event_date = _as_date(raw.get(key))
        if event_date is not None:
            break

    metadata = raw.get("product_metadata")
    competition = None
    if isinstance(metadata, Mapping):
        competition = _text(metadata.get("competition"))
    competition = competition or _text(raw.get("competition"))

    title = _text(raw.get("title")) or _text(raw.get("event_title"))
    sub_title = _text(raw.get("sub_title")) or _text(raw.get("event_subtitle"))

    uuids: list[str] = []
    name_keys: list[str] = []
    surname_sets: list[frozenset[str]] = []
    market_by_uuid: dict[str, str] = {}
    market_by_name: dict[str, str] = {}
    uuid_by_name: dict[str, str] = {}

    for market in raw.get("markets") or []:
        if not isinstance(market, Mapping):
            continue
        market_ticker = _text(market.get("ticker")) or ""
        strike = market.get("custom_strike")
        competitor = None
        if isinstance(strike, Mapping):
            competitor = _text(strike.get("tennis_competitor"))
        competitor = competitor or _text(market.get("tennis_competitor"))
        name = _text(market.get("yes_sub_title"))
        key = full_name_key(name) if name else ""
        if competitor:
            uuids.append(competitor)
            if market_ticker:
                market_by_uuid[competitor] = market_ticker
        if key:
            name_keys.append(key)
            surname_sets.append(surname_keys(name))
            if market_ticker:
                market_by_name[key] = market_ticker
            if competitor:
                uuid_by_name[key] = competitor

    uuid_pair = pair_key(uuids[0], uuids[1]) if len(uuids) == 2 else None
    full_pair = pair_key(name_keys[0], name_keys[1]) if len(name_keys) == 2 else None

    surname_pair: tuple[frozenset[str], frozenset[str]] | None = None
    if len(surname_sets) == 2 and surname_sets[0] and surname_sets[1]:
        surname_pair = (surname_sets[0], surname_sets[1])
    else:
        # Fall back to the event title, which is "Surname vs Surname".
        sides = split_versus(title) or split_versus(sub_title)
        if sides:
            left, right = surname_keys(sides[0]), surname_keys(sides[1])
            if left and right:
                surname_pair = (left, right)

    return KalshiTennisEvent(
        event_ticker=event_ticker,
        series_ticker=series,
        event_date=event_date,
        competition=competition,
        title=title,
        uuid_pair=uuid_pair,
        full_name_pair=full_pair,
        surname_pair=surname_pair,
        market_ticker_by_uuid=market_by_uuid,
        market_ticker_by_name_key=market_by_name,
        uuid_by_name_key=uuid_by_name,
    )


def normalize_kalshi_events(kalshi_events: Any) -> list[KalshiTennisEvent]:
    out: list[KalshiTennisEvent] = []
    for raw in _event_rows(kalshi_events):
        normalized = normalize_kalshi_event(raw)
        if normalized is not None:
            out.append(normalized)
    return out


def build_competitor_registry(events: Iterable[KalshiTennisEvent]) -> dict[str, str]:
    """Build {full_name_key: tennis_competitor UUID} from normalized events.

    A name that maps to more than one UUID across the corpus is dropped, not
    resolved arbitrarily, so the UUID method can never silently mis-key.
    """
    seen: dict[str, set[str]] = {}
    for event in events:
        for name_key, uuid in event.uuid_by_name_key.items():
            seen.setdefault(name_key, set()).add(uuid)
    return {key: next(iter(values)) for key, values in seen.items() if len(values) == 1}


CROSSWALK_COLUMNS: tuple[str, ...] = (
    "tennis_match_id",
    "source_match_id",
    "match_date",
    "tour",
    "tournament",
    "round",
    "p1_name",
    "p2_name",
    "kalshi_event_ticker",
    "kalshi_series_ticker",
    "kalshi_competition",
    "kalshi_event_date",
    "kalshi_p1_market_ticker",
    "kalshi_p2_market_ticker",
    "kalshi_p1_competitor_uuid",
    "kalshi_p2_competitor_uuid",
    "crosswalk_status",
    "crosswalk_method",
    "crosswalk_confidence",
    "date_offset_days",
    "candidate_count",
    "unmatched_reason",
)


def _unmatched_row(match: Mapping[str, Any], reason: str) -> dict[str, Any]:
    return {
        "tennis_match_id": _text(match.get("tennis_match_id")),
        "source_match_id": _text(match.get("source_match_id")),
        "match_date": _text(match.get("match_date")),
        "tour": _text(match.get("tour")),
        "tournament": _text(match.get("tournament")),
        "round": _text(match.get("round")),
        "p1_name": _text(match.get("p1_name")),
        "p2_name": _text(match.get("p2_name")),
        "kalshi_event_ticker": None,
        "kalshi_series_ticker": None,
        "kalshi_competition": None,
        "kalshi_event_date": None,
        "kalshi_p1_market_ticker": None,
        "kalshi_p2_market_ticker": None,
        "kalshi_p1_competitor_uuid": None,
        "kalshi_p2_competitor_uuid": None,
        "crosswalk_status": STATUS_UNMATCHED,
        "crosswalk_method": METHOD_UNMATCHED,
        "crosswalk_confidence": CONFIDENCE_NONE,
        "date_offset_days": None,
        "candidate_count": 0,
        "unmatched_reason": reason,
    }


def _ambiguous_row(
    match: Mapping[str, Any],
    method: str,
    candidate_count: int,
    reason: str,
) -> dict[str, Any]:
    row = _unmatched_row(match, reason)
    row["crosswalk_status"] = STATUS_AMBIGUOUS
    row["crosswalk_method"] = METHOD_AMBIGUOUS
    row["candidate_count"] = candidate_count
    row["unmatched_reason"] = f"{reason}:{method}"
    return row


def _mcp_uuid_pair(
    match: Mapping[str, Any], registry: Mapping[str, str]
) -> tuple[frozenset[str] | None, str | None, str | None]:
    key1 = full_name_key(match.get("p1_name"))
    key2 = full_name_key(match.get("p2_name"))
    uuid1 = registry.get(key1) if key1 else None
    uuid2 = registry.get(key2) if key2 else None
    if not uuid1 or not uuid2:
        return None, uuid1, uuid2
    return pair_key(uuid1, uuid2), uuid1, uuid2


def _event_matches_key(
    event: KalshiTennisEvent,
    method: str,
    match: Mapping[str, Any],
    uuid_pair: frozenset[str] | None,
    full_pair: frozenset[str] | None,
    mcp_surnames: tuple[frozenset[str], frozenset[str]] | None,
) -> bool:
    if method == METHOD_UUID:
        return uuid_pair is not None and event.uuid_pair == uuid_pair
    if method == METHOD_FULL_NAME:
        return full_pair is not None and event.full_name_pair == full_pair
    if method == METHOD_SURNAME:
        if mcp_surnames is None or event.surname_pair is None:
            return False
        if not surname_pair_matches(mcp_surnames, event.surname_pair):
            return False
        return competitions_agree(match.get("tournament"), event.competition)
    return False


def _resolve_market_side(
    event: KalshiTennisEvent,
    name: Any,
    uuid_hint: str | None,
) -> tuple[str | None, str | None]:
    """(market_ticker, competitor_uuid) for one charted player on the event."""
    key = full_name_key(name)
    uuid = uuid_hint or (event.uuid_by_name_key.get(key) if key else None)
    ticker = None
    if uuid:
        ticker = event.market_ticker_by_uuid.get(uuid)
    if ticker is None and key:
        ticker = event.market_ticker_by_name_key.get(key)
    return ticker, uuid


def build_crosswalk(
    mcp_matches: Iterable[Mapping[str, Any]],
    kalshi_events: Any,
    *,
    competitor_registry: Mapping[str, str] | None = None,
    date_tolerance_days: int = DEFAULT_DATE_TOLERANCE_DAYS,
    series_by_tour: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Crosswalk charted matches to Kalshi events. One row per charted match.

    ``kalshi_events`` must already be loaded (list of dicts or DataFrame).
    No network access occurs here.
    """
    if isinstance(kalshi_events, (list, tuple)) and all(
        isinstance(item, KalshiTennisEvent) for item in kalshi_events
    ):
        events = list(kalshi_events)
    else:
        events = normalize_kalshi_events(kalshi_events)
    registry = dict(competitor_registry or {})
    series_map = dict(series_by_tour if series_by_tour is not None else SERIES_BY_TOUR)
    tolerance = max(0, int(date_tolerance_days))

    by_date: dict[date, list[KalshiTennisEvent]] = {}
    for event in events:
        if event.event_date is not None:
            by_date.setdefault(event.event_date, []).append(event)

    rows: list[dict[str, Any]] = []
    for match in mcp_matches:
        rows.append(
            _crosswalk_one(
                match,
                by_date,
                registry=registry,
                tolerance=tolerance,
                series_map=series_map,
            )
        )
    return _demote_duplicate_targets(rows)


def _crosswalk_one(
    match: Mapping[str, Any],
    by_date: Mapping[date, Sequence[KalshiTennisEvent]],
    *,
    registry: Mapping[str, str],
    tolerance: int,
    series_map: Mapping[str, str],
) -> dict[str, Any]:
    match_date = _as_date(match.get("match_date"))
    if match_date is None:
        return _unmatched_row(match, REASON_NO_MCP_DATE)

    expected_series = series_map.get(_text(match.get("tour")) or "")
    uuid_pair, uuid1, uuid2 = _mcp_uuid_pair(match, registry)
    full_pair = pair_key(full_name_key(match.get("p1_name")), full_name_key(match.get("p2_name")))
    s1, s2 = surname_keys(match.get("p1_name")), surname_keys(match.get("p2_name"))
    mcp_surnames = (s1, s2) if s1 and s2 else None

    if uuid_pair is None and full_pair is None and mcp_surnames is None:
        return _unmatched_row(match, REASON_NO_USABLE_KEY)

    for method in METHOD_PRIORITY:
        for offset in _offset_tiers(tolerance):
            candidates: list[tuple[KalshiTennisEvent, int]] = []
            for delta in offset:
                for event in by_date.get(match_date + timedelta(days=delta), ()):
                    if expected_series and event.series_ticker and event.series_ticker != expected_series:
                        continue
                    if _event_matches_key(event, method, match, uuid_pair, full_pair, mcp_surnames):
                        candidates.append((event, delta))
            if not candidates:
                continue
            unique = {event.event_ticker for event, _ in candidates}
            if len(unique) > 1:
                return _ambiguous_row(match, method, len(unique), REASON_MULTIPLE_EVENTS)
            event, delta = candidates[0]
            return _matched_row(match, event, method, delta, uuid1, uuid2)

    if is_not_listed_competition(match.get("tournament")):
        return _unmatched_row(match, REASON_NOT_LISTED)
    return _unmatched_row(match, REASON_NO_CANDIDATE)


def _offset_tiers(tolerance: int) -> list[tuple[int, ...]]:
    """Date offsets grouped by absolute distance, nearest first.

    Same-day is tried alone before +/-1, so a same-day event always wins over
    a neighbouring-day one, and an ambiguity at +/-1 never shadows a clean
    same-day hit.
    """
    tiers: list[tuple[int, ...]] = [(0,)]
    for step in range(1, tolerance + 1):
        tiers.append((-step, step))
    return tiers


def _matched_row(
    match: Mapping[str, Any],
    event: KalshiTennisEvent,
    method: str,
    date_offset_days: int,
    uuid1: str | None,
    uuid2: str | None,
) -> dict[str, Any]:
    p1_ticker, p1_uuid = _resolve_market_side(event, match.get("p1_name"), uuid1)
    p2_ticker, p2_uuid = _resolve_market_side(event, match.get("p2_name"), uuid2)
    row = _unmatched_row(match, "")
    row.update(
        {
            "kalshi_event_ticker": event.event_ticker,
            "kalshi_series_ticker": event.series_ticker,
            "kalshi_competition": event.competition,
            "kalshi_event_date": event.event_date.isoformat() if event.event_date else None,
            "kalshi_p1_market_ticker": p1_ticker,
            "kalshi_p2_market_ticker": p2_ticker,
            "kalshi_p1_competitor_uuid": p1_uuid,
            "kalshi_p2_competitor_uuid": p2_uuid,
            "crosswalk_status": STATUS_MATCHED,
            "crosswalk_method": method,
            "crosswalk_confidence": CONFIDENCE_BY_METHOD[method],
            "date_offset_days": date_offset_days,
            "candidate_count": 1,
            "unmatched_reason": None,
        }
    )
    return row


def _demote_duplicate_targets(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Two charted matches cannot be the same Kalshi event. Demote both."""
    counts: dict[str, int] = {}
    for row in rows:
        if row["crosswalk_status"] == STATUS_MATCHED and row["kalshi_event_ticker"]:
            counts[row["kalshi_event_ticker"]] = counts.get(row["kalshi_event_ticker"], 0) + 1
    if not any(count > 1 for count in counts.values()):
        return rows
    out: list[dict[str, Any]] = []
    for row in rows:
        ticker = row["kalshi_event_ticker"]
        if row["crosswalk_status"] == STATUS_MATCHED and ticker and counts.get(ticker, 0) > 1:
            demoted = _ambiguous_row(row, row["crosswalk_method"], counts[ticker], REASON_MULTIPLE_MATCHES)
            out.append(demoted)
        else:
            out.append(row)
    return out


def crosswalk_summary(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    """Counts by method/status. Integers only."""
    summary: dict[str, int] = {
        "total": 0,
        STATUS_MATCHED: 0,
        STATUS_AMBIGUOUS: 0,
        STATUS_UNMATCHED: 0,
        METHOD_UUID: 0,
        METHOD_FULL_NAME: 0,
        METHOD_SURNAME: 0,
    }
    for row in rows:
        summary["total"] += 1
        status = str(row.get("crosswalk_status"))
        if status in summary:
            summary[status] += 1
        method = str(row.get("crosswalk_method"))
        if status == STATUS_MATCHED and method in summary:
            summary[method] += 1
    return summary


def row_to_csv_row(row: Mapping[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for column in CROSSWALK_COLUMNS:
        value = row.get(column)
        out[column] = "" if value is None else str(value)
    return out


__all__ = [
    "CONFIDENCE_BY_METHOD",
    "CONFIDENCE_EXACT",
    "CONFIDENCE_HIGH",
    "CONFIDENCE_MEDIUM",
    "CONFIDENCE_NONE",
    "CROSSWALK_COLUMNS",
    "DEFAULT_DATE_TOLERANCE_DAYS",
    "KalshiTennisEvent",
    "METHOD_AMBIGUOUS",
    "METHOD_FULL_NAME",
    "METHOD_SURNAME",
    "METHOD_UNMATCHED",
    "METHOD_UUID",
    "REASON_MULTIPLE_EVENTS",
    "REASON_MULTIPLE_MATCHES",
    "REASON_NOT_LISTED",
    "REASON_NO_CANDIDATE",
    "REASON_NO_MCP_DATE",
    "REASON_NO_USABLE_KEY",
    "SERIES_BY_TOUR",
    "STATUS_AMBIGUOUS",
    "STATUS_MATCHED",
    "STATUS_UNMATCHED",
    "build_competitor_registry",
    "build_crosswalk",
    "competitions_agree",
    "crosswalk_summary",
    "is_not_listed_competition",
    "normalize_kalshi_event",
    "normalize_kalshi_events",
    "row_to_csv_row",
]
