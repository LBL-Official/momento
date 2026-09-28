"""Canonical tennis PBP parsing and deterministic tennis state.

Source under test is the Match Charting Project (CC BY-NC-SA 4.0,
NonCommercial, Jeff Sackmann). Fixtures here are small synthetic rows; the
one test that touches the real 190MB warehouse files skips when absent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from roller.tennis import state as tstate
from roller.tennis.pbp import (
    LICENSE_FIELDS,
    PBP_BASIS_SEQUENCE_ONLY,
    PBP_COLUMNS,
    canonical_match_id,
    classify_game_tiebreak,
    derive_serve_number,
    normalize_match_row,
    orient_point_score,
    parse_match_id,
    parse_match_points,
    read_match_index,
    row_to_csv_row,
    split_point_score,
)

INGEST = {
    "ingested_at": "2026-09-11T00:00:00Z",
    "dataset_version": "4fc396d1146348214af013665ba19603c32bca5218a49e9ccd132fa64f4ab73b",
    "pipeline_version": "tennis-pbp-1",
}

MATCH_ID = "20250618-M-Halle-R16-Quentin_Halys-Daniil_Medvedev"

WAREHOUSE = (
    Path(__file__).resolve().parents[2]
    / "Backtesting Suite"
    / "Data"
    / "TENNIS"
    / "2025-2026"
    / "warehouse"
    / "raw"
    / "mcp"
)


def _match_row(**overrides):
    row = {
        "match_id": MATCH_ID,
        "Player 1": "Quentin Halys",
        "Player 2": "Daniil Medvedev",
        "Pl 1 hand": "R",
        "Pl 2 hand": "R",
        "Date": "20250618",
        "Tournament": "Halle",
        "Round": "R16",
        "Time": "11:10 AM",
        "Court": "Centre",
        "Surface": "Grass",
        "Umpire": "",
        "Best of": "3",
        "Final TB?": "A",
        "Charted by": "test",
    }
    row.update(overrides)
    return row


def _point(pt, set1, set2, gm1, gm2, pts, gmno, svr, winner, first="4*", second="", tb="True"):
    return {
        "match_id": MATCH_ID,
        "Pt": str(pt),
        "Set1": str(set1),
        "Set2": str(set2),
        "Gm1": str(gm1),
        "Gm2": str(gm2),
        "Pts": pts,
        "Gm#": str(gmno),
        "TbSet": tb,
        "Svr": str(svr),
        "1st": first,
        "2nd": second,
        "Notes": "",
        "PtWinner": str(winner),
    }


def _game_points():
    """One service game held by player 1, from 0-0 to AD-40."""
    return [
        _point(1, 0, 0, 0, 0, "0-0", 1, 1, 1),
        _point(2, 0, 0, 0, 0, "15-0", 1, 1, 2),
        _point(3, 0, 0, 0, 0, "15-15", 1, 1, 2),
        _point(4, 0, 0, 0, 0, "15-30", 1, 1, 2),
        _point(5, 0, 0, 0, 0, "15-40", 1, 1, 1),
        _point(6, 0, 0, 0, 0, "30-40", 1, 1, 1),
        _point(7, 0, 0, 0, 0, "40-40", 1, 1, 1),
        _point(8, 0, 0, 0, 0, "AD-40", 1, 1, 1),
    ]


def _parse(points, match_row=None):
    index = normalize_match_row(match_row or _match_row())
    return parse_match_points(points, index, **INGEST)


# ---------------------------------------------------------------- provenance


def test_license_is_surfaced_and_noncommercial():
    assert LICENSE_FIELDS["license"] == "CC BY-NC-SA 4.0"
    assert LICENSE_FIELDS["license_commercial_use"] == "PROHIBITED"
    assert "Sackmann" in LICENSE_FIELDS["license_attribution"]


def test_every_mcp_row_is_sequence_only_and_not_pit_joinable():
    rows = _parse(_game_points())
    assert rows
    for row in rows:
        assert row["pbp_basis"] == PBP_BASIS_SEQUENCE_ONLY
        assert row["pit_joinable"] is False
        assert row["event_timestamp"] is None


def test_match_start_time_is_retained_but_never_becomes_a_timestamp():
    rows = _parse(_game_points())
    assert rows[0]["source_time_raw"] == "11:10 AM"
    assert rows[0]["event_timestamp"] is None


def test_rows_expose_every_canonical_column():
    rows = _parse(_game_points())
    for row in rows:
        assert set(row) == set(PBP_COLUMNS)


def test_csv_serialization_uses_empty_string_for_missing():
    rows = _parse(_game_points())
    serialized = row_to_csv_row(rows[0])
    assert serialized["event_timestamp"] == ""
    assert serialized["pit_joinable"] == "0"
    assert list(serialized) == list(PBP_COLUMNS)


def test_canonical_match_id_is_deterministic_and_namespaced():
    first = canonical_match_id(MATCH_ID)
    assert first == canonical_match_id(MATCH_ID)
    assert first != canonical_match_id(MATCH_ID + "x")
    assert first.startswith("TENNIS-")
    assert canonical_match_id("") is None


# ------------------------------------------------------------- numbering


def test_point_set_and_game_numbering():
    points = [
        _point(1, 0, 0, 0, 0, "0-0", 1, 1, 1),
        _point(2, 0, 0, 1, 0, "0-0", 2, 2, 2),
        _point(3, 0, 0, 3, 2, "0-0", 6, 1, 1),
        _point(4, 1, 0, 0, 0, "0-0", 11, 2, 2),
        _point(5, 1, 1, 2, 3, "0-0", 30, 1, 1),
    ]
    rows = _parse(points)
    assert [r["point_number"] for r in rows] == [1, 2, 3, 4, 5]
    assert [r["set_number"] for r in rows] == [1, 1, 1, 2, 3]
    # game_number is within the current set; Gm# is match-cumulative and kept.
    assert [r["game_number"] for r in rows] == [1, 2, 6, 1, 6]
    assert [r["source_game_number"] for r in rows] == [1, 2, 6, 11, 30]


def test_points_are_sorted_by_ordinal_even_when_the_source_is_not():
    # 597 of 3,337 matches in the real 2020s men's file are stored out of order.
    shuffled = [_game_points()[i] for i in (5, 0, 7, 2, 1, 6, 3, 4)]
    rows = _parse(shuffled)
    assert [r["point_number"] for r in rows] == [1, 2, 3, 4, 5, 6, 7, 8]


def test_match_id_prefix_parsing_only_trusts_date_and_circuit():
    parsed = parse_match_id(MATCH_ID)
    assert parsed == {"match_date": "2025-06-18", "tour": "M"}
    # Empty round, doubled hyphen: still parses, still does not invent names.
    assert parse_match_id("20221103-M-Paris_Masters--Casper_Ruud-Lorenzo_Musetti")["tour"] == "M"
    assert parse_match_id("garbage") == {"match_date": None, "tour": None}


# ------------------------------------------------------------ point scores


def test_ad_is_preserved_as_the_literal_string():
    rows = _parse(_game_points())
    ad_row = rows[-1]
    assert ad_row["points_p1_raw"] == "AD"
    assert ad_row["points_p2_raw"] == "40"
    assert ad_row["point_score_raw"] == "AD-40"
    assert not isinstance(ad_row["points_p1_raw"], int)


def test_point_score_raw_is_verbatim():
    rows = _parse(_game_points())
    assert [r["point_score_raw"] for r in rows] == [
        "0-0",
        "15-0",
        "15-15",
        "15-30",
        "15-40",
        "30-40",
        "40-40",
        "AD-40",
    ]


def test_point_score_is_server_relative_not_player_one_relative():
    # Measured on the real files: with `left = server` 404,674 intra-game
    # transitions replay correctly against 201 that do not; with
    # `left = player 1`, every Svr==2 transition (168,875) is wrong.
    rows = _parse(
        [
            _point(1, 0, 0, 0, 0, "0-0", 1, 2, 1),
            _point(2, 0, 0, 0, 0, "0-15", 1, 2, 2),
            _point(3, 0, 0, 0, 0, "15-15", 1, 2, 2),
            _point(4, 0, 0, 0, 0, "30-15", 1, 2, 1),
        ]
    )
    assert rows[0]["point_score_orientation"] == "SERVER_FIRST"
    # Player 2 is serving, so the raw left token is player 2's score.
    assert [(r["points_server_raw"], r["points_returner_raw"]) for r in rows] == [
        ("0", "0"),
        ("0", "15"),
        ("15", "15"),
        ("30", "15"),
    ]
    assert [(r["points_p1_raw"], r["points_p2_raw"]) for r in rows] == [
        ("0", "0"),
        ("15", "0"),
        ("15", "15"),
        ("15", "30"),
    ]


def test_player_oriented_score_is_none_when_the_server_is_unknown():
    rows = _parse([_point(1, 0, 0, 0, 0, "40-30", 1, "", 1)])
    row = rows[0]
    assert row["server"] is None
    # Verbatim server-relative tokens survive; the player mapping does not
    # get guessed.
    assert (row["points_server_raw"], row["points_returner_raw"]) == ("40", "30")
    assert (row["points_p1_raw"], row["points_p2_raw"]) == (None, None)


def test_malformed_point_score_fails_closed():
    assert split_point_score("40") == (None, None)
    assert split_point_score("") == (None, None)
    assert split_point_score("15-30-40") == (None, None)
    rows = _parse([_point(1, 0, 0, 0, 0, "40", 1, 1, 1)])
    assert rows[0]["points_p1_raw"] is None
    assert rows[0]["points_p2_raw"] is None
    assert rows[0]["point_score_raw"] == "40"


# -------------------------------------------------------------- tiebreaks


def _tiebreak_points():
    """A real tiebreak: p1 serves point 1, then serve alternates in pairs, and
    p1 wins every point. Scores are written server-first, so they flip with the
    serve."""
    return [
        _point(1, 0, 0, 6, 6, "0-0", 13, 1, 1),
        _point(2, 0, 0, 6, 6, "0-1", 13, 2, 1),
        _point(3, 0, 0, 6, 6, "0-2", 13, 2, 1),
        _point(4, 0, 0, 6, 6, "3-0", 13, 1, 1),
        _point(5, 0, 0, 6, 6, "4-0", 13, 1, 1),
        _point(6, 0, 0, 6, 6, "0-5", 13, 2, 1),
        _point(7, 0, 0, 6, 6, "0-6", 13, 2, 1),
    ]


def test_tiebreak_points_are_not_encoded_as_classic_game_scores():
    rows = _parse(_tiebreak_points())
    assert all(r["is_tiebreak"] is True for r in rows)
    raw = [(r["points_p1_raw"], r["points_p2_raw"]) for r in rows]
    assert raw == [
        ("0", "0"),
        ("1", "0"),
        ("2", "0"),
        ("3", "0"),
        ("4", "0"),
        ("5", "0"),
        ("6", "0"),
    ]
    flat = {token for pair in raw for token in pair}
    assert not (flat & {"15", "30", "40", "AD"})


def test_tiebreak_score_flips_with_the_serve():
    rows = _parse(_tiebreak_points())
    # Point 3: p1 leads 2-0 but p2 is serving, so the source writes "0-2".
    third = rows[2]
    assert third["point_score_raw"] == "0-2"
    assert (third["points_server_raw"], third["points_returner_raw"]) == ("0", "2")
    assert (third["points_p1_raw"], third["points_p2_raw"]) == ("2", "0")


def test_tbset_column_alone_does_not_mean_tiebreak():
    # Verified against the real files: TbSet is True on 546,865 of 547,478
    # 2020s men's rows. It flags a tiebreak-eligible SET, not a tiebreak point.
    rows = _parse(_game_points())
    assert all(r["source_tb_set"] is True for r in rows)
    assert all(r["is_tiebreak"] is False for r in rows)


def test_long_tiebreak_reaching_fifteen_is_still_a_tiebreak():
    # Real case: Davis Cup tiebreaks reach 15-14. "15" must not flip the game
    # back to a classic game.
    scores = ["0-0", "5-5", "10-10", "14-14", "15-14"]
    decided, basis = classify_game_tiebreak(scores)
    assert decided is True
    assert basis == "POINT_TOKEN"


def test_game_charted_only_at_zero_zero_is_undetermined_not_false():
    decided, basis = classify_game_tiebreak(["0-0"])
    assert decided is None
    assert basis == "UNDETERMINED"


def test_contradictory_game_with_ad_and_tiebreak_token_fails_closed():
    decided, _ = classify_game_tiebreak(["AD-40", "5-4"])
    assert decided is None


def test_tiebreak_classification_is_per_game_not_per_match():
    rows = _parse(_game_points() + _tiebreak_points_after_first_game())
    by_game = {(r["set_number"], r["game_number"]): r["is_tiebreak"] for r in rows}
    assert by_game[(1, 1)] is False
    assert by_game[(1, 13)] is True


def _tiebreak_points_after_first_game():
    out = []
    for i, pts in enumerate(["0-0", "1-0", "2-0", "3-0"], start=9):
        out.append(_point(i, 0, 0, 6, 6, pts, 13, 1, 1))
    return out


# ------------------------------------------------------- server / receiver


def test_server_and_receiver_are_complementary():
    rows = _parse([_point(1, 0, 0, 0, 0, "0-0", 1, 1, 1), _point(2, 0, 0, 1, 0, "0-0", 2, 2, 2)])
    assert (rows[0]["server"], rows[0]["receiver"]) == (1, 2)
    assert (rows[1]["server"], rows[1]["receiver"]) == (2, 1)


def test_invalid_server_yields_none_not_a_guess():
    rows = _parse([_point(1, 0, 0, 0, 0, "0-0", 1, "", 1)])
    assert rows[0]["server"] is None
    assert rows[0]["receiver"] is None


def test_orient_point_score_fails_closed_without_a_server():
    assert orient_point_score("40", "30", 1) == ("40", "30")
    assert orient_point_score("40", "30", 2) == ("30", "40")
    assert orient_point_score("40", "30", None) == (None, None)
    assert orient_point_score(None, "30", 1) == (None, None)


def test_serve_number_from_second_serve_column():
    assert derive_serve_number("4*", "") == 1
    assert derive_serve_number("4d", "6b3f1*") == 2
    assert derive_serve_number("", "6b3f1*") == 2
    # No notation at all is no evidence, so it stays None rather than 1.
    assert derive_serve_number("", "") is None
    rows = _parse(
        [
            _point(1, 0, 0, 0, 0, "0-0", 1, 1, 1, first="4*", second=""),
            _point(2, 0, 0, 0, 0, "15-0", 1, 1, 1, first="4d", second="6b1*"),
            _point(3, 0, 0, 0, 0, "30-0", 1, 1, 1, first="", second=""),
        ]
    )
    assert [r["serve_number"] for r in rows] == [1, 2, None]


def test_point_winner_domain():
    rows = _parse([_point(1, 0, 0, 0, 0, "0-0", 1, 1, 2), _point(2, 0, 0, 0, 0, "0-15", 1, 1, "x")])
    assert rows[0]["point_winner"] == 2
    assert rows[1]["point_winner"] is None


# --------------------------------------------------- match metadata hygiene


def test_best_of_and_surface_outside_domain_fail_closed():
    # Real upstream defect: some Davis Cup rows are column-shifted, so
    # Surface holds an umpire name and Best of holds "1".
    row = normalize_match_row(
        _match_row(Surface="Eva Asderaki-Moore", **{"Best of": "1", "Date": "20240915"})
    )
    assert row["surface"] is None
    assert row["best_of"] is None


def test_best_of_three_and_five_both_survive():
    assert normalize_match_row(_match_row(**{"Best of": "3"}))["best_of"] == 3
    assert normalize_match_row(_match_row(**{"Best of": "5"}))["best_of"] == 5


def test_date_disagreement_between_match_id_and_column_fails_closed():
    row = normalize_match_row(_match_row(Date="20250101"))
    assert row["match_date"] is None
    assert normalize_match_row(_match_row())["match_date"] == "2025-06-18"


def test_missing_match_metadata_leaves_context_null_not_zero():
    rows = parse_match_points([_point(1, 0, 0, 0, 0, "0-0", 1, 1, 1)], None, **INGEST)
    assert rows[0]["best_of"] is None
    assert rows[0]["surface"] is None
    assert rows[0]["p1_name"] is None
    # The circuit token and date still come from the match_id prefix.
    assert rows[0]["tour"] == "M"
    assert rows[0]["match_date"] == "2025-06-18"
    assert rows[0]["match_metadata_status"] == "MISSING"


# ------------------------------------------------------------ state module


def test_break_point_requires_receiver_game_point():
    # p1 serving, p2 at 40 -> break point.
    assert tstate.break_point("30", "40", 1, False) is True
    # p1 serving, p1 at 40 -> game point for the server, not a break point.
    assert tstate.break_point("40", "30", 1, False) is False
    # p2 serving, p1 at AD -> break point.
    assert tstate.break_point("AD", "40", 2, False) is True
    assert tstate.break_point("40", "40", 1, False) is False


def test_break_point_is_false_inside_a_tiebreak():
    # A tiebreak has no service game to break. Determinate, so False not None.
    assert tstate.break_point("6", "5", 1, True) is False


def test_missing_state_stays_none_and_never_becomes_false():
    assert tstate.break_point(None, "40", 1, False) is None
    assert tstate.break_point("30", "40", None, False) is None
    assert tstate.break_point("30", "40", 1, None) is None
    assert tstate.set_point(None, None, 5, 4, False) == (None, None)
    assert tstate.match_point("40", "30", 5, 4, 1, 0, None, False) == (None, None)
    assert tstate.point_lead("40", "30", None) is None
    assert tstate.set_lead(None, 0) is None
    assert tstate.game_lead(5, None) is None
    empty = tstate.derive_state(None)
    assert set(empty) == set(tstate.STATE_FIELDS)
    assert all(value is None for value in empty.values())
    assert not any(value is False for value in empty.values())


def test_set_point_standard_and_seven_five():
    assert tstate.set_point("40", "30", 5, 4, False) == (True, False)
    # 6-5 does not win a set, so 40-30 at 5-5 is not a set point.
    assert tstate.set_point("40", "30", 5, 5, False) == (False, False)
    assert tstate.set_point("40", "30", 6, 5, False) == (True, False)
    assert tstate.set_point("30", "AD", 4, 5, False) == (False, True)


def test_set_point_inside_a_tiebreak():
    assert tstate.set_point("6", "4", 6, 6, True) == (True, False)
    assert tstate.set_point("5", "4", 6, 6, True) == (False, False)
    assert tstate.set_point("6", "6", 6, 6, True) == (False, False)
    # 7-6 in a tiebreak is a set point: 8-6 clears the target with the margin.
    assert tstate.set_point("7", "6", 6, 6, True) == (True, False)
    assert tstate.set_point("4", "6", 6, 6, True) == (False, True)


def test_match_point_best_of_three_and_five():
    assert tstate.sets_to_win(3) == 2
    assert tstate.sets_to_win(5) == 3
    # One set up in a best-of-3, serving for the match.
    assert tstate.match_point("40", "30", 5, 4, 1, 0, 3, False) == (True, False)
    # Same score in a best-of-5 with one set is only a set point.
    assert tstate.match_point("40", "30", 5, 4, 1, 0, 5, False) == (False, False)
    assert tstate.match_point("40", "30", 5, 4, 2, 0, 5, False) == (True, False)
    assert tstate.match_point("40", "30", 5, 4, 1, 0, None, False) == (None, None)


def test_leads_are_three_separate_dimensions():
    row = {
        "sets_p1": 1,
        "sets_p2": 0,
        "games_p1": 2,
        "games_p2": 4,
        "points_p1_raw": "15",
        "points_p2_raw": "40",
        "is_tiebreak": False,
        "server": 1,
        "best_of": 3,
    }
    derived = tstate.derive_state(row)
    assert derived["set_lead"] == 1
    assert derived["game_lead"] == -2
    assert derived["point_lead"] == -2
    # Up a set, down a break, down in the game: never one number.
    assert len({derived["set_lead"], derived["game_lead"]}) == 2
    assert derived["break_point"] is True


def test_point_lead_uses_ranks_in_a_game_and_counts_in_a_tiebreak():
    assert tstate.point_lead("AD", "40", False) == 1
    assert tstate.point_lead("40", "40", False) == 0
    assert tstate.point_lead("0", "40", False) == -3
    assert tstate.point_lead("10", "8", True) == 2
    # Numeric tiebreak scores are not run through the 0/15/30/40 ladder.
    assert tstate.point_lead("3", "1", True) == 2


def test_yes_relative_view_flips_with_the_contract_side():
    row = {
        "sets_p1": 1,
        "sets_p2": 0,
        "games_p1": 5,
        "games_p2": 4,
        "points_p1_raw": "40",
        "points_p2_raw": "30",
        "is_tiebreak": False,
        "server": 1,
        "best_of": 3,
    }
    yes1 = tstate.yes_view(row, 1)
    yes2 = tstate.yes_view(row, 2)
    assert yes1["yes_serving"] is True
    assert yes1["yes_returning"] is False
    assert yes2["yes_serving"] is False
    assert yes2["yes_returning"] is True
    assert (yes1["yes_set_lead"], yes1["yes_game_lead"], yes1["yes_point_lead"]) == (1, 1, 1)
    assert (yes2["yes_set_lead"], yes2["yes_game_lead"], yes2["yes_point_lead"]) == (-1, -1, -1)
    assert yes1["yes_match_point"] is True
    assert yes2["yes_match_point"] is False
    assert yes2["yes_faces_match_point"] is True


def test_yes_view_without_a_yes_player_is_all_none():
    row = {"server": 1, "sets_p1": 1, "sets_p2": 0, "is_tiebreak": False}
    view = tstate.yes_view(row, None)
    assert all(value is None for value in view.values())


def test_state_derives_over_parsed_rows_end_to_end():
    rows = _parse(_game_points())
    derived = [tstate.derive_state(row) for row in rows]
    # 15-40 with p1 serving is a break point; AD-40 is a game point for p1.
    assert derived[4]["break_point"] is True
    assert derived[7]["game_point_p1"] is True
    assert derived[7]["break_point"] is False
    assert all(d["sets_to_win"] == 2 for d in derived)


# ------------------------------------------------------------- integration


@pytest.mark.integration
@pytest.mark.skipif(
    not (WAREHOUSE / "charting-m-matches.csv").is_file(),
    reason="real MCP warehouse files absent",
)
def test_real_mcp_match_index_loads_and_fails_closed_on_bad_rows():
    index = read_match_index(WAREHOUSE / "charting-m-matches.csv")
    assert len(index) >= 7000
    sample = index.get(MATCH_ID)
    assert sample is not None
    assert sample["tour"] == "M"
    assert sample["match_date"] == "2025-06-18"
    assert sample["best_of"] in (3, 5)
    # Upstream has a duplicated match_id that must stay flagged, not merged.
    duplicated = index.get(
        "20240915-M-Davis_Cup_World_Group-RR-Botic_Van_De_Zandschulp-Matteo_Berrettini"
    )
    assert duplicated is not None
    assert duplicated["match_metadata_status"] == "AMBIGUOUS_DUPLICATE"
    for record in index.values():
        assert record["surface"] in (None, "Hard", "Clay", "Grass", "Carpet")
        assert record["best_of"] in (None, 3, 5)
