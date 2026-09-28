"""Parse Match Charting Project CSVs into canonical tennis PBP rows.

SOURCE LICENSE (CC BY-NC-SA 4.0 — NONCOMMERCIAL USE ONLY)
---------------------------------------------------------
Match Charting Project, Jeff Sackmann. Commercial use is PROHIBITED. Momento
Systems LLC must replace or separately license this source before any
commercial B2B/D2C use. Attribution required; ShareAlike applies to
derivatives. ``LICENSE_FIELDS`` below must be embedded in every manifest that
describes data produced by this module.

POINT-IN-TIME
-------------
MCP has no timestamp column. Every row emitted here carries
``event_timestamp = None``, ``pbp_basis = SEQUENCE_ONLY`` and
``pit_joinable = False``. Those two columns exist as columns (not constants)
precisely so a future timestamped feed can emit ``TIMESTAMPED_OBSERVED`` /
``True`` into the same canonical schema. The matches-index ``Time`` column is
retained verbatim as ``source_time_raw`` and is never used to synthesize a
timestamp.

SCORE ORIENTATION (measured, not assumed)
-----------------------------------------
``Pts`` is the score **before** the point is played and is written
**server-first**, including inside tiebreaks where the server alternates.
``Set1``/``Set2`` and ``Gm1``/``Gm2`` are player-indexed. The two orientations
differ, so rows carry both the verbatim server-relative pair
(``points_server_raw`` / ``points_returner_raw``) and the player-indexed pair
(``points_p1_raw`` / ``points_p2_raw``). See
``POINT_SCORE_ORIENTATION_SERVER_FIRST`` for the measurement.

ROW TYPING
----------
Rows are typed ``dict[str, object]``: ``int`` for counts, ``str`` for score
tokens and identifiers, ``bool`` for flags, ``None`` for missing. No floats
anywhere. Missing is ``None`` — never 0, never "", never False. Use
``row_to_csv_row`` to serialize with the ROLLER CSV convention ("" = missing).

FAIL-CLOSED FIELD POLICY
------------------------
The upstream CSVs contain a small number of column-shifted and duplicated
rows (verified: 35 malformed men's rows, 20 women's, plus duplicated
``match_id`` values). Any match-level field whose value falls outside its
verified domain is emitted as ``None`` rather than passed through, and
``match_metadata_status`` records why.
"""

from __future__ import annotations

import csv
import hashlib
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any

SOURCE_MCP = "tennis_mcp"

LICENSE_FIELDS: dict[str, str] = {
    "license": "CC BY-NC-SA 4.0",
    "license_commercial_use": "PROHIBITED",
    "license_attribution": "Jeff Sackmann - Match Charting Project",
    "license_source_repo": "https://github.com/JeffSackmann/tennis_MatchChartingProject",
    "license_note": (
        "NonCommercial. Momento Systems LLC must replace or separately license this "
        "source before any commercial B2B/D2C use. ShareAlike applies to derivatives."
    ),
}

# pbp_basis domain. MCP is always SEQUENCE_ONLY; the other value exists so a
# timestamped feed can populate the same schema without a migration.
PBP_BASIS_SEQUENCE_ONLY = "SEQUENCE_ONLY"
PBP_BASIS_TIMESTAMPED_OBSERVED = "TIMESTAMPED_OBSERVED"

TOUR_MEN = "M"
TOUR_WOMEN = "W"
# NOTE: `tour` carries the MCP circuit/gender token verbatim ("M"/"W"). It is
# deliberately NOT mapped to "ATP"/"WTA" here: MCP also charts Davis Cup, BJK
# Cup, ITF and college matches, which are not ATP/WTA tour events. The Kalshi
# series hint lives in roller.tennis.crosswalk, where it belongs.
VALID_TOURS = frozenset({TOUR_MEN, TOUR_WOMEN})

VALID_SURFACES = frozenset({"Hard", "Clay", "Grass", "Carpet"})
VALID_BEST_OF = frozenset({3, 5})

# Classic game-score tokens. "AD" is preserved as the literal string and is
# never turned into a number.
POINT_AD = "AD"
CLASSIC_POINT_TOKENS = frozenset({"0", "15", "30", "40", POINT_AD})
# Tokens that can only occur inside a tiebreak. "0", "15", "30" and "40" are
# excluded because a long tiebreak really does pass through 15-x and 30-x.
_UNAMBIGUOUS_TIEBREAK_TOKENS_EXCLUDED = frozenset({"0", "15", "30", "40"})

# VERIFIED ORIENTATION OF `Pts` (measured, not assumed).
#
# `Pts` is the score BEFORE the point is played, written SERVER-first:
# left token = the server of *this* point, right token = the returner. This
# holds in tiebreaks too, where the server alternates and the tokens swap
# with it. Replaying every intra-game transition in charting-m-points-2020s:
#
#   left = server   : 404,674 consistent /    201 inconsistent (games)
#                     18,933 consistent /     23 inconsistent (tiebreaks)
#   left = player 1 :       0 consistent / 168,875 inconsistent (server == p2)
#
# `Set1`/`Set2` and `Gm1`/`Gm2`, by contrast, ARE player-indexed
# (78,800 consistent / 0 inconsistent). So the score columns use two
# different orientations and must not be read the same way.
POINT_SCORE_ORIENTATION_SERVER_FIRST = "SERVER_FIRST"

METADATA_OK = "OK"
METADATA_MISSING = "MISSING"
METADATA_AMBIGUOUS_DUPLICATE = "AMBIGUOUS_DUPLICATE"

TIEBREAK_BASIS_POINT_TOKEN = "POINT_TOKEN"
TIEBREAK_BASIS_CLASSIC_TOKEN = "CLASSIC_TOKEN"
TIEBREAK_BASIS_UNDETERMINED = "UNDETERMINED"

PBP_COLUMNS: tuple[str, ...] = (
    # identity
    "tennis_match_id",
    "source_match_id",
    "source",
    "tour",
    # match context
    "match_date",
    "tournament",
    "round",
    "surface",
    "best_of",
    "p1_name",
    "p2_name",
    "p1_hand",
    "p2_hand",
    # point position
    "point_number",
    "set_number",
    "game_number",
    "source_game_number",
    # score state before/at the point as charted
    "sets_p1",
    "sets_p2",
    "games_p1",
    "games_p2",
    "point_score_raw",
    "point_score_orientation",
    "points_server_raw",
    "points_returner_raw",
    "points_p1_raw",
    "points_p2_raw",
    "is_tiebreak",
    "tiebreak_basis",
    "source_tb_set",
    # actors
    "server",
    "receiver",
    "serve_number",
    "point_winner",
    # source-native detail retained verbatim
    "serve_1st_notation",
    "serve_2nd_notation",
    "point_notes",
    "source_court",
    "source_umpire",
    "source_final_tb",
    "source_charted_by",
    "source_time_raw",
    # point-in-time contract
    "event_timestamp",
    "pbp_basis",
    "pit_joinable",
    # provenance
    "match_metadata_status",
    "source_dataset",
    "source_file_hash",
    "dataset_version",
    "pipeline_version",
    "ingested_at",
)

MATCH_INDEX_COLUMNS: tuple[str, ...] = (
    "match_id",
    "Player 1",
    "Player 2",
    "Pl 1 hand",
    "Pl 2 hand",
    "Date",
    "Tournament",
    "Round",
    "Time",
    "Court",
    "Surface",
    "Umpire",
    "Best of",
    "Final TB?",
    "Charted by",
)

POINT_COLUMNS: tuple[str, ...] = (
    "match_id",
    "Pt",
    "Set1",
    "Set2",
    "Gm1",
    "Gm2",
    "Pts",
    "Gm#",
    "TbSet",
    "Svr",
    "1st",
    "2nd",
    "Notes",
    "PtWinner",
)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int(value: Any) -> int | None:
    text = _text(value)
    if text is None:
        return None
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def _non_negative_int(value: Any) -> int | None:
    parsed = _int(value)
    if parsed is None or parsed < 0:
        return None
    return parsed


def _bool(value: Any) -> bool | None:
    text = _text(value)
    if text is None:
        return None
    lowered = text.lower()
    if lowered in {"true", "t", "yes", "y", "1"}:
        return True
    if lowered in {"false", "f", "no", "n", "0"}:
        return False
    return None


def canonical_match_id(source_match_id: Any, *, source: str = SOURCE_MCP) -> str | None:
    """Stable internal id. Deterministic hash of source + source id."""
    text = _text(source_match_id)
    if text is None:
        return None
    digest = hashlib.sha256(f"{source}|{text}".encode()).hexdigest()[:16]
    return f"TENNIS-{digest}"


def parse_match_id(source_match_id: Any) -> dict[str, str | None]:
    """Extract only the fields the match_id encodes reliably.

    Format is ``YYYYMMDD-<M|W>-<Tournament>-<Round>-<Player1>-<Player2>``, but
    tournament and player segments contain their own hyphens in real rows
    (e.g. ``20221103-M-Paris_Masters--Casper_Ruud-Lorenzo_Musetti`` has an
    empty round). Only the first two segments are trustworthy, so only those
    are parsed here. Names, tournament and round come from the matches index.
    """
    text = _text(source_match_id)
    if text is None:
        return {"match_date": None, "tour": None}
    parts = text.split("-")
    date = _iso_date(parts[0]) if parts else None
    tour = None
    if len(parts) >= 2:
        token = parts[1].strip().upper()
        if token in VALID_TOURS:
            tour = token
    return {"match_date": date, "tour": tour}


def _iso_date(value: Any) -> str | None:
    """'20250618' -> '2025-06-18'. Anything else -> None (fail closed)."""
    text = _text(value)
    if text is None or len(text) != 8 or not text.isdigit():
        return None
    year, month, day = int(text[0:4]), int(text[4:6]), int(text[6:8])
    if not (1900 <= year <= 2100) or not (1 <= month <= 12) or not (1 <= day <= 31):
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def split_point_score(raw: Any) -> tuple[str | None, str | None]:
    """Split ``Pts`` into **(server_points, returner_points)**.

    The source writes this column server-first; see
    ``POINT_SCORE_ORIENTATION_SERVER_FIRST``. 'AD' is preserved as the literal
    string and never converted to a number.

    Returns (None, None) unless there are exactly two non-empty tokens, so a
    malformed score fails closed instead of being half-parsed.
    """
    text = _text(raw)
    if text is None:
        return None, None
    parts = text.split("-")
    if len(parts) != 2:
        return None, None
    left, right = parts[0].strip().upper(), parts[1].strip().upper()
    if not left or not right:
        return None, None
    return left, right


def orient_point_score(
    server_points: str | None,
    returner_points: str | None,
    server: int | None,
) -> tuple[str | None, str | None]:
    """Re-orient a server-first score into (player_1_points, player_2_points).

    Without a known server the mapping is unknowable, so both sides are None.
    The verbatim server-relative pair is still retained on the row.
    """
    if server_points is None or returner_points is None or server not in (1, 2):
        return None, None
    if server == 1:
        return server_points, returner_points
    return returner_points, server_points


def _is_unambiguous_tiebreak_token(token: str | None) -> bool:
    if not token:
        return False
    return token.isdigit() and token not in _UNAMBIGUOUS_TIEBREAK_TOKENS_EXCLUDED


def _is_classic_only_token(token: str | None) -> bool:
    return token in {"15", "30", "40", POINT_AD}


def classify_game_tiebreak(point_scores: Iterable[Any]) -> tuple[bool | None, str]:
    """Decide whether a whole charted game is a tiebreak, from its scores.

    The source ``TbSet`` column does NOT mean "this point is in a tiebreak" —
    it is true for ~99.9% of 2020s rows because it flags whether the *set* is
    tiebreak-eligible. Verified against the real files. So tiebreak detection
    is done from the point-score tokens of the whole game:

      1. any token that can only be a tiebreak score (a digit other than
         0/15/30/40) -> tiebreak;
      2. else any classic-only token (15/30/40/AD) -> not a tiebreak;
      3. else (the game is charted with nothing but "0-0") -> UNDETERMINED.

    Rule 1 outranks rule 2 because epic tiebreaks genuinely reach 15-14 and
    beyond; six such games exist in the 2020s men's file. A game containing
    both "AD" and a tiebreak-only token is a charting contradiction and
    returns None.
    """
    has_tb = False
    has_classic = False
    has_ad = False
    for raw in point_scores:
        left, right = split_point_score(raw)
        for token in (left, right):
            if _is_unambiguous_tiebreak_token(token):
                has_tb = True
            elif _is_classic_only_token(token):
                has_classic = True
                if token == POINT_AD:
                    has_ad = True
    if has_tb and has_ad:
        return None, TIEBREAK_BASIS_UNDETERMINED
    if has_tb:
        return True, TIEBREAK_BASIS_POINT_TOKEN
    if has_classic:
        return False, TIEBREAK_BASIS_CLASSIC_TOKEN
    return None, TIEBREAK_BASIS_UNDETERMINED


def derive_serve_number(first: Any, second: Any) -> int | None:
    """1 when the point was played on the first serve, 2 on the second.

    MCP puts the rally notation in ``2nd`` only when the first serve was a
    fault. With neither column populated there is no evidence at all, so the
    answer is None — never a guessed 1.
    """
    has_second = _text(second) is not None
    has_first = _text(first) is not None
    if has_second:
        return 2
    if has_first:
        return 1
    return None


def _player_slot(value: Any) -> int | None:
    parsed = _int(value)
    return parsed if parsed in (1, 2) else None


def read_match_index(path: Path) -> dict[str, dict[str, Any]]:
    """Load a charting-*-matches.csv into {source_match_id: normalized match}.

    Duplicated ``match_id`` values exist upstream. They are kept as a single
    entry flagged ``AMBIGUOUS_DUPLICATE`` with all ambiguous fields nulled;
    no arbitrary winner is picked.
    """
    index: dict[str, dict[str, Any]] = {}
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            record = normalize_match_row(raw)
            key = record.get("source_match_id")
            if not key:
                continue
            existing = index.get(key)
            if existing is None:
                index[key] = record
            else:
                index[key] = _collapse_duplicate(existing, record)
    return index


def _collapse_duplicate(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    for column in (
        "match_date",
        "tour",
        "tournament",
        "round",
        "surface",
        "best_of",
        "p1_name",
        "p2_name",
        "p1_hand",
        "p2_hand",
        "source_court",
        "source_umpire",
        "source_final_tb",
        "source_charted_by",
        "source_time_raw",
    ):
        if left.get(column) != right.get(column):
            merged[column] = None
    merged["match_metadata_status"] = METADATA_AMBIGUOUS_DUPLICATE
    return merged


def normalize_match_row(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize one matches-index row, failing closed per field."""
    source_match_id = _text(raw.get("match_id"))
    from_id = parse_match_id(source_match_id)

    column_date = _iso_date(raw.get("Date"))
    id_date = from_id["match_date"]
    # The match_id prefix is the more reliable of the two (the Date column is
    # shifted in the malformed rows). Disagreement fails closed.
    if id_date and column_date and id_date != column_date:
        match_date: str | None = None
    else:
        match_date = id_date or column_date

    best_of = _int(raw.get("Best of"))
    if best_of not in VALID_BEST_OF:
        best_of = None

    surface = _text(raw.get("Surface"))
    if surface not in VALID_SURFACES:
        surface = None

    status = METADATA_OK
    if source_match_id is None:
        status = METADATA_MISSING

    return {
        "source_match_id": source_match_id,
        "tennis_match_id": canonical_match_id(source_match_id),
        "source": SOURCE_MCP,
        "tour": from_id["tour"],
        "match_date": match_date,
        "tournament": _text(raw.get("Tournament")),
        "round": _text(raw.get("Round")),
        "surface": surface,
        "best_of": best_of,
        "p1_name": _text(raw.get("Player 1")),
        "p2_name": _text(raw.get("Player 2")),
        "p1_hand": _text(raw.get("Pl 1 hand")),
        "p2_hand": _text(raw.get("Pl 2 hand")),
        "source_court": _text(raw.get("Court")),
        "source_umpire": _text(raw.get("Umpire")),
        "source_final_tb": _text(raw.get("Final TB?")),
        "source_charted_by": _text(raw.get("Charted by")),
        # Retained verbatim and never used to build a timestamp.
        "source_time_raw": _text(raw.get("Time")),
        "match_metadata_status": status,
    }


def _empty_match_record(source_match_id: str | None) -> dict[str, Any]:
    from_id = parse_match_id(source_match_id)
    return {
        "source_match_id": source_match_id,
        "tennis_match_id": canonical_match_id(source_match_id),
        "source": SOURCE_MCP,
        "tour": from_id["tour"],
        "match_date": from_id["match_date"],
        "tournament": None,
        "round": None,
        "surface": None,
        "best_of": None,
        "p1_name": None,
        "p2_name": None,
        "p1_hand": None,
        "p2_hand": None,
        "source_court": None,
        "source_umpire": None,
        "source_final_tb": None,
        "source_charted_by": None,
        "source_time_raw": None,
        "match_metadata_status": METADATA_MISSING,
    }


def _game_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    """Group points into charted games without trusting ``Gm#``.

    (sets, games) uniquely identifies a game inside a match; ``Gm#`` is only
    the fallback because it is blank in a handful of rows.
    """
    sets_p1 = _non_negative_int(row.get("Set1"))
    sets_p2 = _non_negative_int(row.get("Set2"))
    games_p1 = _non_negative_int(row.get("Gm1"))
    games_p2 = _non_negative_int(row.get("Gm2"))
    if None not in (sets_p1, sets_p2, games_p1, games_p2):
        return ("SCORE", sets_p1, sets_p2, games_p1, games_p2)
    return ("SOURCE_GM", _text(row.get("Gm#")))


def _sorted_points(rows: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Order by the point ordinal.

    597 of 3,337 matches in the 2020s men's file are stored out of ``Pt``
    order, so sorting is mandatory. Rows with an unparseable ``Pt`` sort last
    in stable file order rather than being dropped.
    """
    indexed = list(enumerate(rows))
    indexed.sort(key=lambda pair: (_int(pair[1].get("Pt")) is None, _int(pair[1].get("Pt")) or 0, pair[0]))
    return [row for _, row in indexed]


def parse_match_points(
    point_rows: Iterable[Mapping[str, Any]],
    match_record: Mapping[str, Any] | None,
    *,
    ingested_at: str,
    dataset_version: str,
    pipeline_version: str,
    source_dataset: str = SOURCE_MCP,
    source_file_hash: str = "",
) -> list[dict[str, Any]]:
    """Canonical PBP rows for exactly one match.

    ``point_rows`` may arrive in any order; they are sorted by ``Pt``.
    """
    rows = [row for row in point_rows if isinstance(row, Mapping)]
    if not rows:
        return []
    source_match_id = _text(rows[0].get("match_id"))
    record = dict(match_record) if match_record else _empty_match_record(source_match_id)

    ordered = _sorted_points(rows)
    by_game: dict[tuple[Any, ...], list[Mapping[str, Any]]] = {}
    for row in ordered:
        by_game.setdefault(_game_key(row), []).append(row)
    tiebreak_by_game = {
        key: classify_game_tiebreak(row.get("Pts") for row in group) for key, group in by_game.items()
    }

    out: list[dict[str, Any]] = []
    for row in ordered:
        sets_p1 = _non_negative_int(row.get("Set1"))
        sets_p2 = _non_negative_int(row.get("Set2"))
        games_p1 = _non_negative_int(row.get("Gm1"))
        games_p2 = _non_negative_int(row.get("Gm2"))
        set_number = None if sets_p1 is None or sets_p2 is None else sets_p1 + sets_p2 + 1
        game_number = None if games_p1 is None or games_p2 is None else games_p1 + games_p2 + 1

        point_score_raw = _text(row.get("Pts"))
        points_server_raw, points_returner_raw = split_point_score(point_score_raw)
        is_tiebreak, tiebreak_basis = tiebreak_by_game[_game_key(row)]

        server = _player_slot(row.get("Svr"))
        receiver = None if server is None else 3 - server
        points_p1_raw, points_p2_raw = orient_point_score(
            points_server_raw, points_returner_raw, server
        )

        out.append(
            {
                "tennis_match_id": record.get("tennis_match_id"),
                "source_match_id": source_match_id,
                "source": SOURCE_MCP,
                "tour": record.get("tour"),
                "match_date": record.get("match_date"),
                "tournament": record.get("tournament"),
                "round": record.get("round"),
                "surface": record.get("surface"),
                "best_of": record.get("best_of"),
                "p1_name": record.get("p1_name"),
                "p2_name": record.get("p2_name"),
                "p1_hand": record.get("p1_hand"),
                "p2_hand": record.get("p2_hand"),
                "point_number": _non_negative_int(row.get("Pt")),
                "set_number": set_number,
                "game_number": game_number,
                "source_game_number": _non_negative_int(row.get("Gm#")),
                "sets_p1": sets_p1,
                "sets_p2": sets_p2,
                "games_p1": games_p1,
                "games_p2": games_p2,
                "point_score_raw": point_score_raw,
                "point_score_orientation": POINT_SCORE_ORIENTATION_SERVER_FIRST,
                "points_server_raw": points_server_raw,
                "points_returner_raw": points_returner_raw,
                "points_p1_raw": points_p1_raw,
                "points_p2_raw": points_p2_raw,
                "is_tiebreak": is_tiebreak,
                "tiebreak_basis": tiebreak_basis,
                "source_tb_set": _bool(row.get("TbSet")),
                "server": server,
                "receiver": receiver,
                "serve_number": derive_serve_number(row.get("1st"), row.get("2nd")),
                "point_winner": _player_slot(row.get("PtWinner")),
                "serve_1st_notation": _text(row.get("1st")),
                "serve_2nd_notation": _text(row.get("2nd")),
                "point_notes": _text(row.get("Notes")),
                "source_court": record.get("source_court"),
                "source_umpire": record.get("source_umpire"),
                "source_final_tb": record.get("source_final_tb"),
                "source_charted_by": record.get("source_charted_by"),
                "source_time_raw": record.get("source_time_raw"),
                # MCP is sequence-only. These three are inseparable.
                "event_timestamp": None,
                "pbp_basis": PBP_BASIS_SEQUENCE_ONLY,
                "pit_joinable": False,
                "match_metadata_status": record.get("match_metadata_status"),
                "source_dataset": source_dataset,
                "source_file_hash": source_file_hash,
                "dataset_version": dataset_version,
                "pipeline_version": pipeline_version,
                "ingested_at": ingested_at,
            }
        )
    return out


def parse_points_file(
    path: Path,
    match_index: Mapping[str, Mapping[str, Any]],
    *,
    ingested_at: str,
    dataset_version: str,
    pipeline_version: str,
    source_dataset: str = SOURCE_MCP,
    source_file_hash: str = "",
    only_match_ids: set[str] | None = None,
) -> Iterator[dict[str, Any]]:
    """Stream canonical rows out of a charting-*-points-*.csv.

    Points are buffered per match (a match is a few hundred rows) because
    tiebreak classification and ``Pt`` ordering are match-scoped. The whole
    file is never held in memory as canonical rows.
    """
    buffer: dict[str, list[Mapping[str, Any]]] = {}
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            key = _text(raw.get("match_id"))
            if key is None:
                continue
            if only_match_ids is not None and key not in only_match_ids:
                continue
            buffer.setdefault(key, []).append(raw)
    for key in sorted(buffer):
        yield from parse_match_points(
            buffer[key],
            match_index.get(key),
            ingested_at=ingested_at,
            dataset_version=dataset_version,
            pipeline_version=pipeline_version,
            source_dataset=source_dataset,
            source_file_hash=source_file_hash,
        )


def row_to_csv_row(row: Mapping[str, Any]) -> dict[str, str]:
    """Serialize a canonical row with the ROLLER CSV convention ("" = missing)."""
    out: dict[str, str] = {}
    for column in PBP_COLUMNS:
        value = row.get(column)
        if value is None:
            out[column] = ""
        elif value is True:
            out[column] = "1"
        elif value is False:
            out[column] = "0"
        else:
            out[column] = str(value)
    return out


def match_records(match_index: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Match-level records in a stable order, for the crosswalk."""
    return [dict(match_index[key]) for key in sorted(match_index)]
