"""Terminal, path, explicit gross EV, and the predeclared contrasts."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from roller.choosin_texas.lubbock.observations import HOLM_SEASON, PRIMARY, Observation
from roller.choosin_texas.lubbock.schedule import RankedGame, phase_of
from roller.choosin_texas.lubbock.stats import (
    SCALE,
    bootstrap_contrast,
    bootstrap_mean,
    bootstrap_standardized,
    render_micro,
    scaled_mean,
    shorthand_cents,
    wilson,
)

OFFICIAL_SEASON_CONTRAST = {
    "estimate": "UNAVAILABLE",
    "lo": "UNAVAILABLE",
    "hi": "UNAVAILABLE",
    "p": "UNAVAILABLE",
    "classification": "UNAVAILABLE",
    "reason": (
        "For incomplete or completeness-unknown seasons, warehouse-relative deciles remain descriptive. "
        "Official-season final-10% and final-20% contrasts are UNAVAILABLE unless a full-season "
        "schedule denominator establishes those boundaries."
    ),
}

COMPLETENESS = "WAREHOUSE_COVERED_PROGRESS"


def _rate(numer: int, denom: int) -> str:
    if denom <= 0:
        return "UNAVAILABLE"
    return render_micro(scaled_mean(numer, denom))


def _micro_mean(total: int, n: int) -> str:
    if n <= 0:
        return "UNAVAILABLE"
    return render_micro(scaled_mean(total, n))


def _packs(rows: list[Observation], field: str) -> dict[str, tuple[int, int]]:
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        if field == "payoff" and row.payoff is not None:
            value = row.payoff
        elif field == "hold" and row.hold is not None:
            value = row.hold
        elif field == "t40" and row.t40 is not None:
            value = 1 if row.t40 else 0
        elif field == "yes" and row.yes is not None:
            value = 1 if row.yes else 0
        else:
            continue
        slot = totals[row.league_local_date]
        slot[0] += value
        slot[1] += 1
    return {date: (total, count) for date, (total, count) in totals.items()}


def _cell_packs(rows: list[Observation]) -> dict[str, dict[tuple[str, str], tuple[int, int]]]:
    found: dict[str, dict[tuple[str, str], list[int]]] = defaultdict(dict)
    for row in rows:
        if row.payoff is None:
            continue
        key = (row.entry_band, row.period)
        slot = found[row.league_local_date].setdefault(key, [0, 0])
        slot[0] += row.payoff
        slot[1] += 1
    return {
        date: {key: (total, count) for key, (total, count) in cells.items()}
        for date, cells in found.items()
    }


def _cells(rows: list[Observation]) -> dict[str, int]:
    counts = {
        "win_no_t40": 0,
        "win_t40": 0,
        "loss_no_t40": 0,
        "loss_t40": 0,
        "legacy_unsettled": 0,
        "unsettled_stop": 0,
        "legacy": 0,
    }
    for row in rows:
        if row.t40 is None:
            continue
        counts["legacy"] += 1
        if row.yes is None:
            counts["legacy_unsettled"] += 1
            if row.t40:
                counts["unsettled_stop"] += 1
            continue
        if row.yes and not row.t40:
            counts["win_no_t40"] += 1
        elif row.yes and row.t40:
            counts["win_t40"] += 1
        elif not row.yes and not row.t40:
            counts["loss_no_t40"] += 1
        else:
            counts["loss_t40"] += 1
    return counts


def _brier(rows: list[Observation]) -> str:
    if rows and all(row.nominal_entry for row in rows):
        return "UNAVAILABLE"
    total = Decimal(0)
    count = 0
    for row in rows:
        if row.nominal_entry or row.yes is None or row.entry_cents is None:
            continue
        price = Decimal(row.entry_cents) / Decimal(100)
        outcome = Decimal(1 if row.yes else 0)
        total += (price - outcome) ** 2
        count += 1
    if count == 0:
        return "UNAVAILABLE"
    return str((total / count).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def _calibration(rows: list[Observation]) -> str:
    if not rows or all(row.nominal_entry for row in rows):
        return "UNAVAILABLE"
    numer = 0
    denom = 0
    for row in rows:
        if row.nominal_entry or row.yes is None or row.entry_cents is None:
            continue
        numer += (100 if row.yes else 0) - row.entry_cents
        denom += 100
    if denom == 0:
        return "UNAVAILABLE"
    return render_micro(scaled_mean(numer, denom))


def _entry_mean(rows: list[Observation]) -> str:
    if not rows or all(row.nominal_entry for row in rows):
        return "UNAVAILABLE"
    total = 0
    count = 0
    for row in rows:
        if row.nominal_entry or row.entry_cents is None:
            continue
        total += row.entry_cents
        count += 1
    return _micro_mean(total, count)


def _band_counts(rows: list[Observation]) -> dict[str, str]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row.entry_band] += 1
    return {band: str(count) for band, count in sorted(counts.items())}


def measure_rows(rows: list[Observation]) -> dict[str, object]:
    cells = _cells(rows)
    cell_n = cells["win_no_t40"] + cells["win_t40"] + cells["loss_no_t40"] + cells["loss_t40"]
    if cell_n + cells["legacy_unsettled"] != cells["legacy"]:
        raise AssertionError("legacy path cells do not reconcile")
    payoff_rows = [row for row in rows if row.payoff is not None]
    hold_rows = [row for row in rows if row.hold is not None]
    payoff_sum = sum(row.payoff or 0 for row in payoff_rows)
    formula_sum = (
        20 * cells["win_no_t40"]
        - 40 * (cells["win_t40"] + cells["loss_t40"] + cells["unsettled_stop"])
        - 80 * cells["loss_no_t40"]
    )
    explicit = _micro_mean(payoff_sum, len(payoff_rows))
    if payoff_rows and payoff_sum != formula_sum:
        raise AssertionError("explicit payoff sum disagrees with the cell formula")
    t40_k = cells["win_t40"] + cells["loss_t40"]
    yes_rows = [row for row in rows if row.yes is not None]
    yes_k = sum(1 for row in yes_rows if row.yes)
    no_t40 = cells["win_no_t40"] + cells["loss_no_t40"]
    t40_wilson = wilson(t40_k, cell_n)
    yes_wilson = wilson(yes_k, len(yes_rows))
    return {
        "rows": str(len(rows)),
        "legacy_rows": str(cells["legacy"]),
        "path_completeness": "PATH_COMPLETENESS_UNVERIFIED",
        "path_unverified_rows": str(len(rows)),
        "win_no_t40": str(cells["win_no_t40"]),
        "win_t40": str(cells["win_t40"]),
        "loss_no_t40": str(cells["loss_no_t40"]),
        "loss_t40": str(cells["loss_t40"]),
        "legacy_unsettled": str(cells["legacy_unsettled"]),
        "path_cell_rows": str(cell_n),
        "terminal_rows": str(len(yes_rows)),
        "cells_sum_to_legacy": str(cell_n + cells["legacy_unsettled"] == cells["legacy"]),
        "p_t40": _rate(t40_k, cell_n),
        "p_t40_wilson": t40_wilson or {"lo": "UNAVAILABLE", "hi": "UNAVAILABLE"},
        "p_yes": _rate(yes_k, len(yes_rows)),
        "p_yes_wilson": yes_wilson or {"lo": "UNAVAILABLE", "hi": "UNAVAILABLE"},
        "gap_vs_0_80": "UNAVAILABLE"
        if not yes_rows
        else render_micro(scaled_mean(yes_k, len(yes_rows)) - scaled_mean(80, 100)),
        "mean_observed_entry_cents": _entry_mean(rows),
        "calibration_residual": _calibration(rows),
        "brier": _brier(rows),
        "gross_ev_cents": explicit,
        "explicit_ev_check_cents": _micro_mean(
            20 * cells["win_no_t40"] - 40 * (cells["win_t40"] + cells["loss_t40"]) - 80 * cells["loss_no_t40"],
            cell_n,
        ),
        "legacy_shorthand_ev_cents": shorthand_cents(no_t40, cell_n, cells["loss_no_t40"]),
        "hold_ev_cents": _micro_mean(sum(row.hold or 0 for row in hold_rows), len(hold_rows)),
        "stop_minus_hold_cents": "UNAVAILABLE"
        if explicit == "UNAVAILABLE" or not hold_rows
        else render_micro(
            scaled_mean(payoff_sum, len(payoff_rows)) - scaled_mean(sum(row.hold or 0 for row in hold_rows), len(hold_rows))
        ),
        "entry_bands": _band_counts(rows),
        "net_ev": "UNAVAILABLE",
        "t40_flag_rows": str(cells["legacy"]),
    }


def _contrast_block(
    rows: list[Observation],
    late_pred,
    *,
    field: str,
    block: int,
    stream: str,
    side: str,
) -> dict[str, object]:
    late = [row for row in rows if late_pred(row)]
    early = [row for row in rows if row.decile is not None and not late_pred(row)]
    result = bootstrap_contrast(_packs(late, field), _packs(early, field), block=block, stream=stream)
    if result is None:
        return {
            "estimate": "UNAVAILABLE",
            "lo": "UNAVAILABLE",
            "hi": "UNAVAILABLE",
            "p": "UNAVAILABLE",
            "classification": "INSUFFICIENT_DATA",
            "distinct_active_dates_late": str(len({row.league_local_date for row in late})),
            "distinct_active_dates_early": str(len({row.league_local_date for row in early})),
            "n_dates_late": str(len({row.league_local_date for row in late})),
            "n_dates_early": str(len({row.league_local_date for row in early})),
            "n_late": str(len(late)),
            "n_early": str(len(early)),
            "block": str(block),
        }
    result["classification"] = "exploratory"
    result["contrast_kind"] = "warehouse_relative"
    result["distinct_active_dates_late"] = result["n_dates_late"]
    result["distinct_active_dates_early"] = result["n_dates_early"]
    result["n_late"] = str(len(late))
    result["n_early"] = str(len(early))
    result["hypothesized_side"] = side
    return result


def _bucket_payload(
    bucket_id: str,
    kind: str,
    overlapping: bool,
    games: list[RankedGame],
    rows: list[Observation],
    *,
    ev_interval: dict[str, str] | None,
) -> dict[str, object]:
    if not games:
        return {
            "bucket_id": bucket_id,
            "kind": kind,
            "overlapping": overlapping,
            "status": "UNAVAILABLE",
            "schedule_completeness": COMPLETENESS,
        }
    ranks = [game.game_rank for game in games]
    dates = [game.league_local_date for game in games]
    payload = measure_rows(rows)
    payload.update(
        {
            "bucket_id": bucket_id,
            "kind": kind,
            "overlapping": overlapping,
            "status": "OBSERVED",
            "schedule_completeness": COMPLETENESS,
            "first80_coverage_note": "FIRST80 rows are not the schedule denominator",
            "rank_lo": str(min(ranks)),
            "rank_hi": str(max(ranks)),
            "progress_lo": min(games, key=lambda game: game.game_rank).season_progress,
            "progress_hi": max(games, key=lambda game: game.game_rank).season_progress,
            "date_min": min(dates),
            "date_max": max(dates),
            "warehouse_games": str(len(games)),
            "canonical_linked_games": str(sum(1 for game in games if game.internal_game_id != game.event_ticker)),
            "first80_rows": str(len(rows)),
            "first80_games": str(len({row.event_ticker for row in rows})),
            "gross_ev_interval": ev_interval
            or {"estimate": payload["gross_ev_cents"], "lo": "UNAVAILABLE", "hi": "UNAVAILABLE"},
        }
    )
    return payload


def _daily(games: list[RankedGame]) -> list[dict[str, str]]:
    counts: dict[str, int] = defaultdict(int)
    for game in games:
        counts[game.league_local_date] += 1
    total = len(games)
    running = 0
    rows = []
    for date in sorted(counts):
        running += counts[date]
        rows.append(
            {
                "league_local_date": date,
                "games": str(counts[date]),
                "cumulative_games": str(running),
                "cumulative_progress": render_micro(scaled_mean(running, total)),
            }
        )
    return rows


def _collapsed_late(games: list[RankedGame]) -> set[str]:
    first: dict[str, RankedGame] = {}
    for game in games:
        current = first.get(game.league_local_date)
        if current is None or game.game_rank < current.game_rank:
            first[game.league_local_date] = game
    late_dates = {date for date, game in first.items() if game.decile == 9}
    return {game.event_ticker for game in games if game.league_local_date in late_dates}


def build_series(games: list[RankedGame], observations: list[Observation]) -> list[dict[str, object]]:
    seasons = sorted({(game.sport, game.season_id, game.phase) for game in games})
    built: list[dict[str, object]] = []
    for sport, season_id, phase in seasons:
        if phase not in {"REGULAR_SEASON", "POSTSEASON", "PRESEASON"}:
            continue
        group_games = [game for game in games if game.sport == sport and game.season_id == season_id and game.phase == phase]
        group_rows = [
            row
            for row in observations
            if row.sport == sport and row.season_id == season_id and row.phase == phase and row.join_status == "JOINED"
        ]
        if not group_games:
            continue
        primary = phase == "REGULAR_SEASON" and season_id == HOLM_SEASON[sport]
        stream_prefix = f"{sport}|{season_id}|{phase}"
        late = lambda row: row.decile == 9  # noqa: E731
        late_20 = lambda row: row.quintile == 4  # noqa: E731
        contrasts: dict[str, object] = {}
        if any(game.decile == 9 for game in group_games):
            contrasts["primary_ev"] = _contrast_block(
                group_rows, late, field="payoff", block=1, stream=f"{stream_prefix}|primary_ev|1", side="positive"
            )
            contrasts["primary_ev_block_3"] = _contrast_block(
                group_rows, late, field="payoff", block=3, stream=f"{stream_prefix}|primary_ev|3", side="positive"
            )
            contrasts["primary_ev_block_7"] = _contrast_block(
                group_rows, late, field="payoff", block=7, stream=f"{stream_prefix}|primary_ev|7", side="positive"
            )
            contrasts["supporting_t40"] = _contrast_block(
                group_rows, late, field="t40", block=1, stream=f"{stream_prefix}|t40|1", side="negative"
            )
            contrasts["terminal_yes"] = _contrast_block(
                group_rows, late, field="yes", block=1, stream=f"{stream_prefix}|yes|1", side="positive"
            )
            contrasts["secondary_ev"] = _contrast_block(
                group_rows, late_20, field="payoff", block=1, stream=f"{stream_prefix}|secondary_ev|1", side="positive"
            )
            contrasts["hold_ev"] = _contrast_block(
                group_rows, late, field="hold", block=1, stream=f"{stream_prefix}|hold_ev|1", side="positive"
            )
            late_ids = _collapsed_late(group_games)
            collapsed_rows = []
            for row in group_rows:
                copied = Observation(**{**row.__dict__})
                copied.decile = 9 if row.event_ticker in late_ids else 0
                collapsed_rows.append(copied)
            contrasts["date_preserving_primary_ev"] = _contrast_block(
                collapsed_rows,
                late,
                field="payoff",
                block=1,
                stream=f"{stream_prefix}|date_preserving|1",
                side="positive",
            )
            late_rows = [row for row in group_rows if row.decile == 9]
            early_rows = [row for row in group_rows if row.decile is not None and row.decile < 9]
            standardized = bootstrap_standardized(
                _cell_packs(late_rows),
                _cell_packs(early_rows),
                stream=f"{stream_prefix}|standardized|1",
            )
            contrasts["standardized_ev"] = standardized or {
                "estimate": "UNAVAILABLE",
                "lo": "UNAVAILABLE",
                "hi": "UNAVAILABLE",
                "classification": "INSUFFICIENT_DATA",
            }
        else:
            for name in (
                "primary_ev",
                "primary_ev_block_3",
                "primary_ev_block_7",
                "supporting_t40",
                "terminal_yes",
                "secondary_ev",
                "hold_ev",
                "date_preserving_primary_ev",
                "standardized_ev",
            ):
                contrasts[name] = {
                    "classification": "INSUFFICIENT_DATA",
                    "estimate": "UNAVAILABLE",
                    "contrast_kind": "warehouse_relative",
                }
        contrasts["official_season_final_10"] = dict(OFFICIAL_SEASON_CONTRAST)
        contrasts["official_season_final_20"] = dict(OFFICIAL_SEASON_CONTRAST)
        deciles = []
        for index in range(10):
            bucket_games = [game for game in group_games if game.decile == index]
            bucket_rows = [row for row in group_rows if row.decile == index]
            interval = bootstrap_mean(
                _packs(bucket_rows, "payoff"),
                block=1,
                stream=f"{stream_prefix}|decile|{index}",
            )
            deciles.append(
                _bucket_payload(
                    f"D{index + 1:02d}",
                    "decile",
                    False,
                    bucket_games,
                    bucket_rows,
                    ev_interval=interval,
                )
            )
        quintiles = []
        for index in range(5):
            bucket_games = [game for game in group_games if game.quintile == index]
            bucket_rows = [row for row in group_rows if row.quintile == index]
            interval = bootstrap_mean(
                _packs(bucket_rows, "payoff"),
                block=1,
                stream=f"{stream_prefix}|quintile|{index}",
            )
            quintiles.append(
                _bucket_payload(
                    f"Q{index + 1:02d}",
                    "quintile",
                    False,
                    bucket_games,
                    bucket_rows,
                    ev_interval=interval,
                )
            )
        cumulative = []
        ordered = sorted(group_games, key=lambda game: game.game_rank)
        total = len(ordered)
        for step in range(1, 11):
            cutoff = equal_prefix(total, step)
            bucket_games = [game for game in ordered if game.game_rank <= cutoff]
            tickers = {game.event_ticker for game in bucket_games}
            bucket_rows = [row for row in group_rows if row.event_ticker in tickers]
            interval = bootstrap_mean(
                _packs(bucket_rows, "payoff"),
                block=1,
                stream=f"{stream_prefix}|cumulative|{step}",
            )
            cumulative.append(
                _bucket_payload(
                    f"C{step * 10:02d}",
                    "cumulative",
                    step < 10,
                    bucket_games,
                    bucket_rows,
                    ev_interval=interval,
                )
            )
        phase_disagreement = 0
        for row in group_rows:
            if row.csv_phase and phase_of(row.csv_phase) != phase:
                phase_disagreement += 1
        dates = [game.game_date for game in group_games]
        built.append(
            {
                "sport": sport,
                "season_id": season_id,
                "source_season": group_games[0].source_season,
                "phase": phase,
                "universe_id": PRIMARY[sport],
                "holm_primary": primary,
                "role": "holm_primary" if primary else "sensitivity",
                "schedule_completeness": COMPLETENESS,
                "denominator": "WAREHOUSE_COVERED_PROGRESS",
                "warehouse_games": str(len(group_games)),
                "date_min": min(dates),
                "date_max": max(dates),
                "start_basis_counts": _basis_counts(group_games),
                "first80_rows": str(len(group_rows)),
                "phase_disagreement_rows": str(phase_disagreement),
                "candle_basis": "CANDLE_PATH_NOT_A_FILL",
                "net_ev": "UNAVAILABLE",
                "live_execution": False,
                "submits": False,
                "whole": measure_rows(group_rows),
                "deciles": deciles,
                "quintiles": quintiles,
                "cumulative": cumulative,
                "contrasts": contrasts,
                "daily": _daily(group_games),
            }
        )
    return built


def equal_prefix(total: int, step: int) -> int:
    """Cutoff rank for the first step/10 of an equal-count decile assignment."""
    from roller.choosin_texas.lubbock.stats import equal_count_bounds

    bounds = equal_count_bounds(total, 10)
    if step >= 10 or not bounds:
        return total
    included = [hi for index, _lo, hi in bounds if index < step]
    return max(included) if included else 0


def _basis_counts(games: list[RankedGame]) -> dict[str, str]:
    counts: dict[str, int] = defaultdict(int)
    for game in games:
        counts[game.start_basis] += 1
    return {key: str(value) for key, value in sorted(counts.items())}


def explicit_matches_cells(rows: list[Observation]) -> bool:
    usable = [row for row in rows if row.payoff is not None and row.yes is not None and row.t40 is not None]
    if not usable:
        return True
    total = sum(row.payoff or 0 for row in usable)
    win_no = sum(1 for row in usable if row.yes and not row.t40)
    t40 = sum(1 for row in usable if row.t40)
    loss_no = sum(1 for row in usable if row.yes is False and not row.t40)
    return total == 20 * win_no - 40 * t40 - 80 * loss_no


def assert_scale() -> None:
    if SCALE != 1_000_000:
        raise AssertionError("microcent scale drifted")
