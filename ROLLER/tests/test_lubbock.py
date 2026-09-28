"""Lubbock season-progress invariants. Does not open sealed confirmation cohorts."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from roller.choosin_texas.lubbock.schedule import _is_real_clock
from roller.choosin_texas.lubbock.schedule import repo_root
from roller.choosin_texas.lubbock.serve import handle_export_csv, load_summary
from roller.choosin_texas.lubbock.stats import (
    INTERPRETATION,
    classify_holm,
    contrast_on_support,
    equal_count_bounds,
    explicit_payoff,
    percentile_interval,
    progress,
    recentered_p,
    retained_support,
    shorthand_cents,
    wilson,
)
from roller.choosin_texas.lubbock.stats import holm

ROOT = repo_root()
V1 = ROOT / "research/choosin_texas/lubbock/v1"
BOOK = ROOT / "research/choosin_texas/library/nba_2q_regular_8040_1lot_2026_27/book.json"
PACKAGE = ROOT / "ROLLER/roller/choosin_texas/lubbock"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_midnight_on_game_date_is_not_a_tip() -> None:
    from datetime import datetime, timezone

    midnight = datetime(2025, 11, 3, tzinfo=timezone.utc)
    assert _is_real_clock(midnight, "2025-11-03") is False
    tip = datetime(2025, 11, 3, 23, 30, tzinfo=timezone.utc)
    assert _is_real_clock(tip, "2025-11-03") is True


def test_buckets_and_payoff_rules() -> None:
    bounds = equal_count_bounds(1233, 10)
    covered = []
    sizes = []
    for _index, lo, hi in bounds:
        covered.extend(range(lo, hi + 1))
        sizes.append(hi - lo + 1)
    assert covered == list(range(1, 1234))
    assert max(sizes) - min(sizes) <= 1
    assert progress(1, 10) == "0.050000"
    assert explicit_payoff(t40=True, yes=True) == -40
    assert explicit_payoff(t40=False, yes=True) == 20
    assert explicit_payoff(t40=False, yes=False) == -80
    assert explicit_payoff(t40=False, yes=None) is None
    assert shorthand_cents(8, 10, 0) != "NOT_APPLICABLE"
    assert shorthand_cents(8, 10, 1) == "NOT_APPLICABLE"
    assert wilson(0, 0) is None
    assert classify_holm(estimate=5, lo=1, hi=2, holm_numer=1, holm_denom=2001) == "supported_in_this_sample"
    assert classify_holm(estimate=5, lo=1, hi=2, holm_numer=200, holm_denom=2001) == "inconclusive"
    assert classify_holm(estimate=5, lo=-1, hi=2, holm_numer=1, holm_denom=2001) == "inconclusive"
    assert classify_holm(estimate=-5, lo=-4, hi=-1, holm_numer=1, holm_denom=2001) == "contradicted_in_this_sample"
    late = {("80", "Q2"): (100, 2), ("84+", "Q2"): (40, 1)}
    early = {("80", "Q2"): (0, 4)}
    support, _strata, shares = retained_support(late, early)
    assert support == [("80", "Q2")]
    assert shares["late_retained_share"] == "0.666667"
    assert shares["early_retained_share"] == "1.000000"
    contrast, late_mean, early_mean = contrast_on_support(late, early, support)
    assert late_mean == 50 * 1_000_000
    assert early_mean == 0
    assert contrast == 50 * 1_000_000
    assert contrast_on_support(late, {("80", "Q2"): (0, 0)}, support) is None
    samples = list(range(2000))
    assert percentile_interval(samples) == (49, 1949)
    assert recentered_p([5] * 2000, 5) == "1/2001"
    adjusted = holm([("a", 1, 2001), ("b", 100, 2001), ("c", 100, 2001), ("d", 500, 2001)])
    assert adjusted[0]["holm_p"] == "4/2001"
    assert [row["label"] for row in adjusted] == ["a", "b", "c", "d"]


def test_spec_paragraph_and_no_sealed_access() -> None:
    spec = (ROOT / "research/choosin_texas/lubbock/LUBBOCK_SPEC_V1.md").read_text()
    assert INTERPRETATION in spec
    assert "WAREHOUSE_COVERED_PROGRESS" in spec
    for path in PACKAGE.glob("*.py"):
        text = path.read_text()
        assert "confirmation_cohort.json" not in text
        assert "research/austin/experiments" not in text


def test_persisted_run_keeps_locks_and_book() -> None:
    summary = load_summary()
    manifest = json.loads((V1 / "manifest.json").read_text())
    assert manifest["book_json_sha256"] == _sha(BOOK)
    assert manifest["confirmation_cohorts_opened"] is False
    assert summary["schedule_completeness"] == "WAREHOUSE_COVERED_PROGRESS"
    assert summary["net_ev"] == "UNAVAILABLE"
    assert summary["submits"] is False
    assert summary["live_execution"] is False
    assert summary["path_status"] == "PATH_COMPLETENESS_UNVERIFIED"
    assert [row["label"] for row in summary["holm"]] == ["NBA", "NCAAB", "WNBA", "MLB"]
    identity = summary["identity"]
    assert identity["nba_604"] == 604
    assert identity["ncaab_332"] == 332
    assert identity["derived_four"] == 936
    assert identity["asked_six"] == 1182
    assert identity["nba_matches_derived_four_nba"] is True

    grouped: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    deciles: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    quintiles: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    with (V1 / "assignments.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            key = (row["sport"], row["season_id"], row["phase"])
            grouped[key].append(int(row["game_rank"]))
            deciles[key].append(row["decile"])
            quintiles[key].append(row["quintile"])
    for key, ranks in grouped.items():
        assert sorted(ranks) == list(range(1, len(ranks) + 1))
        for labels in (deciles[key], quintiles[key]):
            counts = defaultdict(int)
            for label in labels:
                counts[label] += 1
            sizes = list(counts.values())
            assert max(sizes) - min(sizes) <= 1
            assert sum(sizes) == len(ranks)

    sports = defaultdict(int)
    cells = defaultdict(int)
    unverified = 0
    with (V1 / "observations.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row["sport"] != "MLB":
                sports[row["sport"]] += 1
            assert row["evaluation_status"] == "PATH_COMPLETENESS_UNVERIFIED"
            unverified += 1
            if row["t40"] == "" or row["yes"] == "":
                continue
            win = row["yes"] == "True"
            stop = row["t40"] == "True"
            if win and not stop:
                cells["win_no"] += 1
            elif win and stop:
                cells["win_t40"] += 1
            elif not win and not stop:
                cells["loss_no"] += 1
            else:
                cells["loss_t40"] += 1
    assert sports == {"NBA": 604, "NCAAB": 332, "WNBA": 246}
    assert sum(cells.values()) > 0
    assert unverified > 1182
    nba = next(row for row in summary["series"] if row["sport"] == "NBA" and row["holm_primary"])
    official = nba["contrasts"]["official_season_final_10"]
    assert official["classification"] == "UNAVAILABLE"
    assert nba["contrasts"]["official_season_final_20"]["estimate"] == "UNAVAILABLE"
    wnba = next(row for row in summary["series"] if row["sport"] == "WNBA" and row["holm_primary"])
    assert wnba["season_id"] == "2025"
    wnba_2026 = next(row for row in summary["series"] if row["sport"] == "WNBA" and row["season_id"] == "2026" and row["phase"] == "REGULAR_SEASON")
    assert wnba_2026["holm_primary"] is False
    for conclusion in summary["conclusions"]:
        statement = conclusion["statement"].lower()
        assert conclusion["classification"] == "UNAVAILABLE"
        assert "distinct active dates" in statement
        assert "independent active" not in statement
        assert "official-season final 10%" in statement
    assert nba["warehouse_games"] == "1233"
    assert nba["first80_rows"] == "550"
    assert nba["schedule_completeness"] == "WAREHOUSE_COVERED_PROGRESS"
    whole = nba["whole"]
    assert int(whole["win_no_t40"]) + int(whole["win_t40"]) + int(whole["loss_no_t40"]) + int(whole["loss_t40"]) + int(
        whole["legacy_unsettled"]
    ) == int(whole["legacy_rows"])
    ncaab = next(row for row in summary["series"] if row["sport"] == "NCAAB" and row["holm_primary"])
    assert ncaab["start_basis_counts"]["game_date"] == ncaab["warehouse_games"]
    wnba_years = {row["season_id"] for row in summary["series"] if row["sport"] == "WNBA" and row["phase"] == "REGULAR_SEASON"}
    mlb_years = {row["season_id"] for row in summary["series"] if row["sport"] == "MLB" and row["phase"] == "REGULAR_SEASON"}
    assert wnba_years == {"2025", "2026"}
    assert mlb_years == {"2025", "2026"}
    _filename, csv_text = handle_export_csv("NBA", "2025-2026", "REGULAR_SEASON", "decile")
    assert "WAREHOUSE_COVERED_PROGRESS" in csv_text
    assert "D10" in csv_text
    assert "UNAVAILABLE" in csv_text
