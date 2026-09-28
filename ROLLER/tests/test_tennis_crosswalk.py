"""Deterministic MCP-match <-> Kalshi-event crosswalk.

Fixtures are small inline synthetic Kalshi payloads. No network, no warehouse
dependency except one integration test that skips when the real MCP files are
absent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from roller.tennis import names
from roller.tennis.crosswalk import (
    CONFIDENCE_EXACT,
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_NONE,
    CROSSWALK_COLUMNS,
    METHOD_AMBIGUOUS,
    METHOD_FULL_NAME,
    METHOD_SURNAME,
    METHOD_UNMATCHED,
    METHOD_UUID,
    REASON_MULTIPLE_EVENTS,
    REASON_MULTIPLE_MATCHES,
    REASON_NOT_LISTED,
    REASON_NO_MCP_DATE,
    STATUS_AMBIGUOUS,
    STATUS_MATCHED,
    STATUS_UNMATCHED,
    build_competitor_registry,
    build_crosswalk,
    competitions_agree,
    crosswalk_summary,
    is_not_listed_competition,
    normalize_kalshi_events,
)
from roller.tennis.pbp import canonical_match_id, read_match_index

ZVEREV_UUID = "dc4002ad-fb32-4f36-b59f-7c7af1927c57"
KHACHANOV_UUID = "11111111-2222-3333-4444-555555555555"
MEDVEDEV_UUID = "66666666-7777-8888-9999-000000000000"

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


def _market(ticker, name, uuid, rules="in the 2026 US Open Men Singles Semifinal"):
    return {
        "ticker": ticker,
        "yes_sub_title": name,
        "custom_strike": {"tennis_competitor": uuid} if uuid else {},
        "rules_primary": f"...{rules} after a ball has been played",
    }


def _event(
    event_ticker="KXATPMATCH-26SEP09ZVEVAN",
    event_date="2026-09-09",
    competition="US Open Men Singles",
    title="Zverev vs Khachanov",
    markets=None,
):
    return {
        "event_ticker": event_ticker,
        "series_ticker": event_ticker.split("-", 1)[0],
        "event_date": event_date,
        "title": title,
        "sub_title": f"{title} (Sep 09)",
        "product_metadata": {"competition": competition},
        "markets": markets
        if markets is not None
        else [
            _market(f"{event_ticker}-ZVE", "Alexander Zverev", ZVEREV_UUID),
            _market(f"{event_ticker}-KHA", "Karen Khachanov", KHACHANOV_UUID),
        ],
    }


def _mcp(
    source_match_id="20260909-M-US_Open-SF-Alexander_Zverev-Karen_Khachanov",
    match_date="2026-09-09",
    tour="M",
    tournament="US Open",
    p1="Alexander Zverev",
    p2="Karen Khachanov",
    round_="SF",
):
    return {
        "source_match_id": source_match_id,
        "tennis_match_id": canonical_match_id(source_match_id),
        "match_date": match_date,
        "tour": tour,
        "tournament": tournament,
        "round": round_,
        "p1_name": p1,
        "p2_name": p2,
    }


# ---------------------------------------------------------- normalization


def test_accents_punctuation_and_hyphens_normalize():
    assert names.normalize_name("Andrey Rublëv") == "andrey rublev"
    assert names.normalize_name("Jo-Wilfried Tsonga") == "jo wilfried tsonga"
    assert names.normalize_name("Félix Auger-Aliassime") == "felix auger aliassime"
    assert names.full_name_key("Alexander Zverev") == names.full_name_key("ZVEREV, Alexander")


def test_multi_token_surnames():
    assert names.particle_surname("Botic Van De Zandschulp") == "van de zandschulp"
    assert names.particle_surname("Jesper De Jong") == "de jong"
    assert names.particle_surname("Carlos Alcaraz") == "alcaraz"
    # Kalshi renders the surname alone; the key sets must still intersect.
    assert names.surname_keys("Botic Van De Zandschulp") & names.surname_keys("Van De Zandschulp")
    assert names.surname_keys("Jesper De Jong") & names.surname_keys("De Jong")
    assert names.surname_keys("Lesley Pattinama Kerkhove") & names.surname_keys("Pattinama Kerkhove")


def test_versus_split_and_failure():
    assert names.split_versus("Zverev vs Khachanov") == ("Zverev", "Khachanov")
    assert names.split_versus("Zverev vs Khachanov (Sep 11)") == ("Zverev", "Khachanov")
    assert names.split_versus("Zverev") is None
    assert names.split_versus("A vs B vs C") is None


def test_pair_key_rejects_a_self_pair():
    assert names.pair_key("a", "b") == frozenset({"a", "b"})
    assert names.pair_key("a", "a") is None
    assert names.pair_key("", "b") is None


def test_event_ticker_code_blob_is_never_split():
    # 26SEP03VANDE and 26AUG24KWONLAJ break a fixed 3+3 split. Only the series
    # prefix is taken; player codes come from markets, never from the blob.
    events = normalize_kalshi_events([_event(event_ticker="KXATPMATCH-26SEP03VANDE")])
    assert events[0].series_ticker == "KXATPMATCH"
    assert events[0].event_ticker == "KXATPMATCH-26SEP03VANDE"


# ------------------------------------------------------------- method 1


def test_uuid_pair_plus_date_is_the_highest_confidence_path():
    events = normalize_kalshi_events([_event()])
    registry = build_competitor_registry(events)
    rows = build_crosswalk([_mcp()], events, competitor_registry=registry)
    assert len(rows) == 1
    row = rows[0]
    assert row["crosswalk_status"] == STATUS_MATCHED
    assert row["crosswalk_method"] == METHOD_UUID
    assert row["crosswalk_confidence"] == CONFIDENCE_EXACT
    assert row["date_offset_days"] == 0
    assert row["kalshi_event_ticker"] == "KXATPMATCH-26SEP09ZVEVAN"
    assert row["kalshi_p1_competitor_uuid"] == ZVEREV_UUID
    assert row["kalshi_p2_competitor_uuid"] == KHACHANOV_UUID
    assert row["kalshi_p1_market_ticker"] == "KXATPMATCH-26SEP09ZVEVAN-ZVE"


def test_registry_drops_a_name_that_maps_to_two_uuids():
    clash = _event(
        event_ticker="KXATPMATCH-26SEP10ZVESIN",
        event_date="2026-09-10",
        title="Zverev vs Sinner",
        markets=[
            _market("KXATPMATCH-26SEP10ZVESIN-ZVE", "Alexander Zverev", "deadbeef-0000-0000-0000-000000000000"),
            _market("KXATPMATCH-26SEP10ZVESIN-SIN", "Jannik Sinner", MEDVEDEV_UUID),
        ],
    )
    events = normalize_kalshi_events([_event(), clash])
    registry = build_competitor_registry(events)
    assert names.full_name_key("Alexander Zverev") not in registry
    assert names.full_name_key("Karen Khachanov") in registry


# ------------------------------------------------------------- method 2


def test_full_name_pair_matches_without_uuids():
    rows = build_crosswalk([_mcp()], [_event()])
    row = rows[0]
    assert row["crosswalk_method"] == METHOD_FULL_NAME
    assert row["crosswalk_confidence"] == CONFIDENCE_HIGH
    assert row["date_offset_days"] == 0


def test_full_name_pair_survives_accents_and_ordering():
    event = _event(
        title="Rublev vs Medvedev",
        markets=[
            _market("KXATPMATCH-26SEP09ZVEVAN-MED", "Daniil Medvedev", MEDVEDEV_UUID),
            _market("KXATPMATCH-26SEP09ZVEVAN-RUB", "Andrey Rublev", KHACHANOV_UUID),
        ],
    )
    rows = build_crosswalk([_mcp(p1="Andrey Rublëv", p2="Daniil Medvedev")], [event])
    assert rows[0]["crosswalk_status"] == STATUS_MATCHED
    assert rows[0]["crosswalk_method"] == METHOD_FULL_NAME


def test_date_tolerance_records_the_offset_used():
    rows = build_crosswalk([_mcp(match_date="2026-09-08")], [_event()])
    row = rows[0]
    assert row["crosswalk_status"] == STATUS_MATCHED
    assert row["date_offset_days"] == 1
    rows = build_crosswalk([_mcp(match_date="2026-09-11")], [_event()])
    assert rows[0]["date_offset_days"] == -2


def test_date_outside_tolerance_does_not_match():
    rows = build_crosswalk([_mcp(match_date="2026-09-12")], [_event()])
    assert rows[0]["crosswalk_status"] == STATUS_UNMATCHED
    assert rows[0]["crosswalk_method"] == METHOD_UNMATCHED
    assert rows[0]["crosswalk_confidence"] == CONFIDENCE_NONE


def test_same_day_beats_a_neighbouring_day():
    near = _event(
        event_ticker="KXATPMATCH-26SEP08ZVEKHA",
        event_date="2026-09-08",
        title="Zverev vs Khachanov",
    )
    rows = build_crosswalk([_mcp()], [near, _event()])
    assert rows[0]["kalshi_event_ticker"] == "KXATPMATCH-26SEP09ZVEVAN"
    assert rows[0]["date_offset_days"] == 0


# ------------------------------------------------------------- method 3


def test_surname_pair_needs_date_and_tournament_agreement():
    surname_only = _event(
        markets=[
            _market("KXATPMATCH-26SEP09ZVEVAN-ZVE", "Zverev", None),
            _market("KXATPMATCH-26SEP09ZVEVAN-KHA", "Khachanov", None),
        ]
    )
    rows = build_crosswalk([_mcp()], [surname_only])
    assert rows[0]["crosswalk_method"] == METHOD_SURNAME
    assert rows[0]["crosswalk_confidence"] == CONFIDENCE_MEDIUM

    # Same surnames, same date, different tournament -> fail closed.
    wrong_comp = _event(
        competition="ATP Cincinnati",
        markets=[
            _market("KXATPMATCH-26SEP09ZVEVAN-ZVE", "Zverev", None),
            _market("KXATPMATCH-26SEP09ZVEVAN-KHA", "Khachanov", None),
        ],
    )
    rows = build_crosswalk([_mcp()], [wrong_comp])
    assert rows[0]["crosswalk_status"] == STATUS_UNMATCHED


def test_tournament_agreement_tokens():
    assert competitions_agree("US Open", "US Open Men Singles")
    assert competitions_agree("Rome Masters", "ATP Rome")
    assert competitions_agree("Roland Garros", "French Open")
    assert not competitions_agree("Rome Masters", "ATP Cincinnati")
    # Two generic-only names share nothing discriminating.
    assert not competitions_agree("Masters", "ATP Masters 1000")


def test_surname_pair_requires_both_players_to_align():
    half_overlap = _event(
        title="Zverev vs Sinner",
        markets=[
            _market("KXATPMATCH-26SEP09ZVEVAN-ZVE", "Zverev", None),
            _market("KXATPMATCH-26SEP09ZVEVAN-SIN", "Sinner", None),
        ],
    )
    rows = build_crosswalk([_mcp()], [half_overlap])
    assert rows[0]["crosswalk_status"] == STATUS_UNMATCHED


# ------------------------------------------------------------ fail closed


def test_two_candidate_events_are_ambiguous_not_an_arbitrary_pick():
    twin = _event(event_ticker="KXATPMATCH-26SEP09ZVEKH2")
    rows = build_crosswalk([_mcp()], [_event(), twin])
    row = rows[0]
    assert row["crosswalk_status"] == STATUS_AMBIGUOUS
    assert row["crosswalk_method"] == METHOD_AMBIGUOUS
    assert row["kalshi_event_ticker"] is None
    assert row["candidate_count"] == 2
    assert row["unmatched_reason"].startswith(REASON_MULTIPLE_EVENTS)


def test_two_charted_matches_claiming_one_event_are_both_demoted():
    rows = build_crosswalk(
        [_mcp(match_date="2026-09-08"), _mcp(source_match_id="other", match_date="2026-09-10")],
        [_event()],
    )
    assert [r["crosswalk_status"] for r in rows] == [STATUS_AMBIGUOUS, STATUS_AMBIGUOUS]
    assert all(r["kalshi_event_ticker"] is None for r in rows)
    assert all(REASON_MULTIPLE_MATCHES in r["unmatched_reason"] for r in rows)


def test_missing_match_date_never_matches_on_names_alone():
    rows = build_crosswalk([_mcp(match_date=None)], [_event()])
    assert rows[0]["crosswalk_status"] == STATUS_UNMATCHED
    assert rows[0]["unmatched_reason"] == REASON_NO_MCP_DATE


def test_wrong_tour_series_is_excluded():
    rows = build_crosswalk([_mcp(tour="W")], [_event()])
    assert rows[0]["crosswalk_status"] == STATUS_UNMATCHED


def test_team_events_are_reported_not_forced():
    assert is_not_listed_competition("Davis Cup World Group")
    assert is_not_listed_competition("BJK Cup Finals")
    assert is_not_listed_competition("United Cup")
    assert not is_not_listed_competition("US Open")
    rows = build_crosswalk(
        [
            _mcp(
                source_match_id="20250915-M-Davis_Cup_Finals-RR-Flavio_Cobolli-Zizou_Bergs",
                tournament="Davis Cup Finals",
                p1="Flavio Cobolli",
                p2="Zizou Bergs",
            )
        ],
        [_event()],
    )
    assert rows[0]["crosswalk_status"] == STATUS_UNMATCHED
    assert rows[0]["unmatched_reason"] == REASON_NOT_LISTED


def test_no_kalshi_data_yields_all_unmatched_and_no_crash():
    rows = build_crosswalk([_mcp()], [])
    assert rows[0]["crosswalk_status"] == STATUS_UNMATCHED


# ---------------------------------------------------------------- shape


def test_every_row_carries_method_and_confidence():
    rows = build_crosswalk([_mcp(), _mcp(source_match_id="x", match_date="2020-01-01")], [_event()])
    for row in rows:
        assert set(row) == set(CROSSWALK_COLUMNS)
        assert row["crosswalk_method"]
        assert row["crosswalk_confidence"]
        assert isinstance(row["candidate_count"], int)


def test_summary_counts_are_integers():
    rows = build_crosswalk([_mcp(), _mcp(source_match_id="x", match_date="2020-01-01")], [_event()])
    summary = crosswalk_summary(rows)
    assert summary["total"] == 2
    assert summary[STATUS_MATCHED] == 1
    assert summary[STATUS_UNMATCHED] == 1
    assert all(isinstance(value, int) for value in summary.values())


def test_dataframe_input_is_accepted_without_network():
    pd = pytest.importorskip("pandas")
    frame = pd.DataFrame([_event()])
    rows = build_crosswalk([_mcp()], frame)
    assert rows[0]["crosswalk_status"] == STATUS_MATCHED


# ------------------------------------------------------------ integration


@pytest.mark.integration
@pytest.mark.skipif(
    not (WAREHOUSE / "charting-m-matches.csv").is_file(),
    reason="real MCP warehouse files absent",
)
def test_real_mcp_records_feed_the_crosswalk_shape():
    index = read_match_index(WAREHOUSE / "charting-m-matches.csv")
    window = [
        record
        for record in index.values()
        if record["match_date"] and record["match_date"] >= "2025-06-18"
    ]
    assert window, "expected charted matches inside the Kalshi window"
    rows = build_crosswalk(window[:200], [_event()])
    assert len(rows) == len(window[:200])
    for row in rows:
        assert set(row) == set(CROSSWALK_COLUMNS)
        assert row["crosswalk_status"] in {STATUS_MATCHED, STATUS_AMBIGUOUS, STATUS_UNMATCHED}
