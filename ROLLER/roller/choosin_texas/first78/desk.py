"""Display view for the FIRST78 ladder. Counts come from the artifact."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from roller.choosin_texas.first78.derived_scan import MID_STOPS, PATH_STOPS
from roller.choosin_texas.models import pct_display, ratio_display

SLICE_ORDER = ("Q2", "Q3", "H1_2", "H2_1")
SLICE_LABELS = {
    "Q2": ("NBA", "2Q"),
    "Q3": ("NBA", "3Q"),
    "H1_2": ("NCAAB", "1H second 10"),
    "H2_1": ("NCAAB", "2H first 10"),
}
PERIOD_ORDER = ("Q2", "Q3", "Q4", "OT")
CLOCK_BIN_ORDER = ("12:00-9:01", "9:00-6:01", "6:00-3:01", "3:00-0:00")
EV_BAR_FULL_CENTS = 8
CELL_KEYS = ("YES_NO_STOP", "YES_STOP", "NO_NO_STOP", "NO_STOP", "UNRESOLVED")


def clock_bin(remaining_s: int) -> str:
    if remaining_s > 9 * 60:
        return "12:00-9:01"
    if remaining_s > 6 * 60:
        return "9:00-6:01"
    if remaining_s > 3 * 60:
        return "6:00-3:01"
    return "3:00-0:00"


def period_label(period: int | None) -> str | None:
    if period is None:
        return None
    value = int(period)
    if value >= 5:
        return "OT"
    if value in (2, 3, 4):
        return f"Q{value}"
    return None


def _cells(raw: dict | None) -> dict[str, int]:
    source = raw or {}
    return {key: int(source.get(key) or 0) for key in CELL_KEYS}


def _ev_display(value: str | None) -> str | None:
    if value is None:
        return None
    return f"{float(Fraction(value)):+.4f}¢ / trade"


def _ev_bar(value: str | None) -> float:
    if value is None:
        return 0.0
    ev = Fraction(value)
    bar = Fraction(ev.numerator, ev.denominator * EV_BAR_FULL_CENTS) * 100
    return max(0.0, min(100.0, float(bar)))


def _path(stop: int, *, n: int, cells: dict[str, int], ev: str | None, book: int, entry_cents: int = 78) -> dict[str, Any]:
    wins = cells["YES_NO_STOP"]
    return {
        "key": f"{entry_cents}/{stop}",
        "stop_cents": stop,
        "official": stop == 67,
        "n": n,
        "S_display": ratio_display(wins, n) if n else None,
        "S_pct_display": pct_display(wins, n) if n else None,
        "S_bar_pct": float(Fraction(wins, n) * 100) if n else 0.0,
        "ev_per_trade_display": _ev_display(ev) if n else None,
        "book_cents": book,
        "ev_bar_pct": _ev_bar(ev) if n else 0.0,
    }


def _slice_block(name: str, variants: list[dict]) -> dict[str, Any]:
    sport, label = SLICE_LABELS[name]
    by_stop = {}
    for variant in variants:
        found = next((row for row in variant.get("slices") or [] if row.get("slice") == name), None)
        by_stop[int(variant["stop_cents"])] = found or {"n": 0, "cells": {}, "gross_ev_per_contract": None, "gross_sum_cents": 0}
    official = by_stop[67]
    cells = _cells(official.get("cells"))
    n = int(official.get("n") or 0)
    wins = cells["YES_NO_STOP"] + cells["YES_STOP"]
    losses = cells["NO_NO_STOP"] + cells["NO_STOP"]
    paths = [
        _path(
            stop,
            n=int(by_stop[stop].get("n") or 0),
            cells=_cells(by_stop[stop].get("cells")),
            ev=by_stop[stop].get("gross_ev_per_contract"),
            book=int(by_stop[stop].get("gross_sum_cents") or 0),
        )
        for stop in (67, 65, 60)
        if stop in by_stop
    ]
    official_path = next(path for path in paths if path["official"])
    return {
        "partition_id": name,
        "sport_label": sport,
        "slice_label": label,
        "n": n,
        "W": wins,
        "L": losses,
        "unresolved": cells["UNRESOLVED"],
        "terminal": {
            "p_display": ratio_display(wins, n) if n else None,
            "p_pct_display": pct_display(wins, n) if n else None,
        },
        "trade": official_path,
        "paths": [path for path in paths if not path["official"]],
        "cells": {
            "W_and_not_T67": cells["YES_NO_STOP"],
            "W_and_T67": cells["YES_STOP"],
            "L_and_not_T67": cells["NO_NO_STOP"],
            "L_and_T67": cells["NO_STOP"],
        },
    }


def _clock_display(remaining: Fraction) -> str:
    seconds = int(round(float(remaining)))
    minutes, rem = divmod(max(0, seconds), 60)
    return f"{minutes:02d}:{rem:02d}"


def build_clocks(samples: list[dict]) -> list[dict[str, Any]]:
    panels = []
    for slice_id, label in (("Q2", "2Q"), ("Q3", "3Q")):
        rows = [row for row in samples if row.get("slice") == slice_id and row.get("stopped")]
        available = []
        unavailable = 0
        for row in rows:
            period = period_label(row.get("stop_period"))
            remaining = row.get("stop_remaining_s")
            if period is None or remaining is None:
                unavailable += 1
                continue
            available.append((period, int(remaining)))
        n_stops = len(rows)
        bin_n = {(period, bin_id): 0 for period in PERIOD_ORDER for bin_id in CLOCK_BIN_ORDER}
        rem_by_period: dict[str, list[int]] = {period: [] for period in PERIOD_ORDER}
        for period, remaining in available:
            bin_n[(period, clock_bin(remaining))] += 1
            rem_by_period[period].append(remaining)
        bins = []
        for period in PERIOD_ORDER:
            for bin_id in CLOCK_BIN_ORDER:
                count = bin_n[(period, bin_id)]
                bins.append(
                    {
                        "period": period,
                        "clock_bin": bin_id,
                        "label": f"{period} {bin_id}",
                        "n": count,
                        "n_display": ratio_display(count, n_stops) if n_stops else None,
                        "pct_display": pct_display(count, n_stops) if n_stops else None,
                        "bar_pct": float(Fraction(count, n_stops) * 100) if n_stops else 0.0,
                    }
                )
        means = []
        for period in PERIOD_ORDER:
            values = rem_by_period[period]
            if not values:
                continue
            remaining = Fraction(sum(values), len(values))
            means.append(
                {
                    "period": period,
                    "n": len(values),
                    "clock_display": _clock_display(remaining),
                }
            )
        panels.append(
            {
                "slice": slice_id,
                "slice_label": label,
                "n_stops": n_stops,
                "unavailable": unavailable,
                "clock_availability": "MODELED_AVAILABILITY",
                "bins": bins,
                "mean_remaining": means,
            }
        )
    return panels


def clock_samples(rows: list[dict]) -> list[dict[str, Any]]:
    samples = []
    for row in rows:
        if row.get("sport") != "NBA" or row.get("slice") not in {"Q2", "Q3"}:
            continue
        samples.append(
            {
                "slice": row.get("slice"),
                "stopped": bool(row.get("stopped")),
                "entry_period": row.get("entry_period"),
                "entry_remaining_s": row.get("entry_remaining_s"),
                "stop_period": row.get("stop_period"),
                "stop_remaining_s": row.get("stop_remaining_s"),
            }
        )
    return samples


def build_desk(variants: list[dict], samples: list[dict] | None = None) -> dict[str, Any]:
    by_stop = {int(row["stop_cents"]): row for row in variants}
    official = by_stop.get(67) or {}
    cells = _cells(official.get("cells"))
    n = int(official.get("n_entries") or 0)
    wins = cells["YES_NO_STOP"] + cells["YES_STOP"]
    losses = cells["NO_NO_STOP"] + cells["NO_STOP"]
    paths = [
        _path(
            stop,
            n=int(by_stop[stop].get("n_entries") or 0),
            cells=_cells(by_stop[stop].get("cells")),
            ev=by_stop[stop].get("gross_ev_per_contract"),
            book=int(by_stop[stop].get("gross_sum_cents") or 0),
        )
        for stop in (67, 65, 60)
        if stop in by_stop
    ]
    partitions = [_slice_block(name, variants) for name in SLICE_ORDER]
    total_n = sum(row["n"] for row in partitions) or n
    for row in partitions:
        row["n_bar_pct"] = float(Fraction(row["n"], total_n) * 100) if total_n else 0.0
        row["n_share_display"] = ratio_display(row["n"], total_n) if total_n else None
    return {
        "population_id": "PRIMARY_EX_ANTE_FIRST78",
        "official_strategy_id": "FIRST78_67",
        "universe": {
            "n": n,
            "W": wins,
            "L": losses,
            "unresolved": cells["UNRESOLVED"],
            "terminal": {
                "p_display": ratio_display(wins, n) if n else None,
                "p_pct_display": pct_display(wins, n) if n else None,
            },
            "trade": next((path for path in paths if path["official"]), None),
            "paths": paths,
            "unit": "FIRST78 close up-crosses. One contract per game. Not Kalshi trade prints.",
            "verification": "OBSERVED",
        },
        "partitions": partitions,
        "clocks": build_clocks(samples or []),
        "variables": {
            "rule": "FIRST78",
            "K": 78,
            "stop_cents": 67,
            "comparison_stops": [65, 60],
            "entry_cap_cents": None,
            "gain_cents": 22,
            "path_stops": [67, 65, 60],
            "slices": ["nba_q2", "nba_q3", "ncaab_h1_2", "ncaab_h2_1"],
            "fee_applicability": "FEE_APPLICABILITY_UNVERIFIED",
            "locked": True,
            "recompute": "ARTIFACT",
            "note": "Gross threshold payoff on the 78¢ entry. A close is not a fill.",
        },
        "disclaimers": [
            "LIVE EXECUTION = FALSE",
            "CANDLE PATH ≠ FILL",
            "N is PRIMARY_EX_ANTE_FIRST78. It is not the locked 936 book.",
            "78/67 is the official stop. 78/65 and 78/60 are comparisons.",
            "Gross EV is an assumed threshold-price candle path.",
            "Fee applicability is FEE_APPLICABILITY_UNVERIFIED.",
        ],
        "alignment": {
            "model": "PERIOD_BOUNDED_LINEAR_GAME_CLOCK",
            "note": "Clock is a modeled PBP snap at the T67 candle. Missing alignment stays missing. PIT stays OPERATION_REQUIRED. Candle path ≠ fill.",
        },
    }


def attach_desk(body: dict[str, Any]) -> dict[str, Any]:
    if body.get("status") != "OBSERVED":
        return body
    if body.get("population_id") == "DERIVED_FOUR_FIRST78":
        payload = dict(body)
        payload["desk"] = present_derived(body)
        return payload
    payload = dict(body)
    samples = payload.get("clock_samples") or []
    payload["desk"] = build_desk(payload.get("variants") or [], samples)
    return payload


def _rank(paths: list[dict]) -> list[str]:
    def sort_key(path: dict) -> tuple:
        text = path.get("ev_per_trade_display") or ""
        try:
            value = float(str(text).split("¢")[0])
        except ValueError:
            value = float("-inf")
        return (-value, path["key"])

    return [path["key"] for path in sorted(paths, key=sort_key)]


def _stop_path(book: dict, stop: int, slice_name: str | None = None) -> dict[str, Any]:
    slot = book["stops"][str(stop)]
    block = slot["pool"] if slice_name is None else slot["slices"][slice_name]
    return _path(
        stop,
        n=int(block["n"]),
        cells=_cells(block.get("cells")),
        ev=block.get("gross_ev_per_contract"),
        book=int(block.get("gross_sum_cents") or 0),
        entry_cents=int(book["entry_cents"]),
    )


def _mean(values: list[int]) -> dict[str, Any] | None:
    if not values:
        return None
    total = sum(values)
    mean = Fraction(total, len(values))
    return {
        "n": len(values),
        "min": min(values),
        "max": max(values),
        "mean_display": f"{float(mean):+.4f}",
    }


def _axis(value: int, lo: int, hi: int) -> float:
    if hi == lo:
        return 50.0
    return max(0.0, min(100.0, (value - lo) * 100 / (hi - lo)))


def _scatter(rows: list[dict]) -> dict[str, Any]:
    plotted = [row for row in rows if row.get("entry_margin") is not None and row.get("final_margin") is not None]
    survive = [row for row in plotted if not row.get("stopped")]
    stopped = [row for row in plotted if row.get("stopped")]
    points = []
    if plotted:
        xs = [int(row["entry_margin"]) for row in plotted]
        ys = [int(row["final_margin"]) for row in plotted]
        x_lo, x_hi = min(xs), max(xs)
        y_lo, y_hi = min(ys), max(ys)
        for row in plotted:
            points.append(
                {
                    "ticker": row["ticker"],
                    "t67": bool(row.get("stopped")),
                    "entry_margin": row["entry_margin"],
                    "final_margin": row["final_margin"],
                    "plot_x_pct": _axis(int(row["entry_margin"]), x_lo, x_hi),
                    "plot_y_pct": _axis(int(row["final_margin"]), y_lo, y_hi),
                }
            )
    return {
        "missing": len(rows) - len(plotted),
        "n_survive": len(survive),
        "n_t67": len(stopped),
        "points": points,
        "x_label": "bought-team margin at FIRST78 entry",
        "y_label": "bought-team margin at final",
        "margins": {
            "survive": {
                "n": len(survive),
                "entry": _mean([int(row["entry_margin"]) for row in survive]),
                "final": _mean([int(row["final_margin"]) for row in survive]),
            },
            "t67": {
                "n": len(stopped),
                "entry": _mean([int(row["entry_margin"]) for row in stopped]),
                "final": _mean([int(row["final_margin"]) for row in stopped]),
                "t67_time": _mean([int(row["stop_margin"]) for row in stopped if row.get("stop_margin") is not None]),
            },
        },
    }


def _partition(book: dict, slice_name: str) -> dict[str, Any]:
    sport, label = SLICE_LABELS[slice_name]
    official = _stop_path(book, 67, slice_name)
    cells_block = book["stops"]["67"]["slices"][slice_name]
    cells = _cells(cells_block.get("cells"))
    n = int(cells_block["n"])
    wins = cells["YES_NO_STOP"] + cells["YES_STOP"]
    losses = cells["NO_NO_STOP"] + cells["NO_STOP"]
    paths = [_stop_path(book, stop, slice_name) for stop in PATH_STOPS]
    mids = [_stop_path(book, stop, slice_name) for stop in MID_STOPS]
    return {
        "partition_id": slice_name,
        "sport_label": sport,
        "slice_label": label,
        "n": n,
        "W": wins,
        "L": losses,
        "terminal": {
            "p_display": ratio_display(wins, n) if n else None,
            "p_pct_display": pct_display(wins, n) if n else None,
        },
        "trade": official,
        "paths": paths,
        "mid_paths": mids,
        "comparisons": [_stop_path(book, 65, slice_name)],
        "ledger_rank": _rank(paths),
        "mid_ledger_rank": _rank(mids),
        "cells": {
            "W_and_not_T67": cells["YES_NO_STOP"],
            "W_and_T67": cells["YES_STOP"],
            "L_and_not_T67": cells["NO_NO_STOP"],
            "L_and_T67": cells["NO_STOP"],
        },
        "cap_55_excluded": 0,
    }


def _companion(book: dict) -> dict[str, Any]:
    ladder = tuple(sorted(set(PATH_STOPS + MID_STOPS)))
    paths = [_stop_path(book, stop) for stop in ladder]
    partitions = []
    for name in SLICE_ORDER:
        sport, label = SLICE_LABELS[name]
        slice_paths = [_stop_path(book, stop, name) for stop in ladder]
        partitions.append(
            {
                "partition_id": name,
                "sport_label": sport,
                "slice_label": label,
                "n": int(book["stops"]["67"]["slices"][name]["n"]),
                "paths": slice_paths,
            }
        )
    return {
        "rule": book["rule"],
        "gain_cents": book["gain_cents"],
        "n": book["qualified"],
        "cap_cents": book["cap_cents"],
        "note": "Entry-threshold comparison on the same derived-four list. Not the official FIRST78_67 rule. Candle path ≠ fill.",
        "paths": paths,
        "ledger_rank": _rank(paths),
        "partitions": partitions,
    }


def present_derived(body: dict[str, Any]) -> dict[str, Any]:
    book = body["books"]["78"]
    official = _stop_path(book, 67)
    cells = _cells(book["stops"]["67"]["pool"].get("cells"))
    n = int(book["qualified"])
    wins = cells["YES_NO_STOP"] + cells["YES_STOP"]
    paths = [_stop_path(book, stop) for stop in PATH_STOPS]
    mids = [_stop_path(book, stop) for stop in MID_STOPS]
    partitions = [_partition(book, name) for name in SLICE_ORDER]
    total = sum(row["n"] for row in partitions) or n
    for row in partitions:
        row["n_bar_pct"] = float(Fraction(row["n"], total) * 100) if total else 0.0
        row["n_share_display"] = ratio_display(row["n"], total) if total else None
    return {
        "population_id": "DERIVED_FOUR_FIRST78",
        "official_strategy_id": "FIRST78_67",
        "membership_n": body.get("membership_n"),
        "exclusions": body.get("exclusions") or {},
        "universe": {
            "n": n,
            "W": wins,
            "L": cells["NO_NO_STOP"] + cells["NO_STOP"],
            "terminal": {
                "p_display": ratio_display(wins, n) if n else None,
                "p_pct_display": pct_display(wins, n) if n else None,
            },
            "trade": official,
            "paths": paths,
            "mid_paths": mids,
            "comparisons": [_stop_path(book, 65)],
            "ledger_rank": _rank(paths),
            "mid_ledger_rank": _rank(mids),
            "unit": "Derived-four contracts with a 78¢ up-cross. Not padded to 936.",
            "verification": "OBSERVED",
            "cap_55_excluded": 0,
        },
        "partitions": partitions,
        "companions": [_companion(body["books"]["79"]), _companion(body["books"]["81"])],
        "clocks": build_clocks(body.get("clock_samples") or []),
        "scatter": _scatter(body.get("scatter_rows") or []),
        "variables": {
            "rule": "FIRST78",
            "K": 78,
            "stop_cents": 67,
            "comparison_stops": [65],
            "entry_cap_cents": None,
            "gain_cents": 22,
            "path_stops": list(PATH_STOPS),
            "mid_stops": list(MID_STOPS),
            "slices": ["nba_q2", "nba_q3", "ncaab_h1_2", "ncaab_h2_1"],
            "fee_applicability": "FEE_APPLICABILITY_UNVERIFIED",
            "locked": True,
            "recompute": "DERIVED_FOUR_ARTIFACT",
            "note": "Stops sit around the 67¢ official exit. None of them are the 40¢ ladder. A close is not a fill.",
        },
        "disclaimers": [
            "LIVE EXECUTION = FALSE",
            "CANDLE PATH ≠ FILL",
            "Membership is the derived four, 936 games. Qualified N is the 78¢ up-cross subset.",
            "78/67 is the official stop. The ladder and the 79/81 blocks are comparisons.",
            "Fee applicability is FEE_APPLICABILITY_UNVERIFIED.",
        ],
        "alignment": {
            "model": "PERIOD_BOUNDED_LINEAR_GAME_CLOCK",
            "note": "Clock and margin are a modeled PBP snap at the 78¢ entry and the T67 candle. Missing scores stay missing. PIT stays OPERATION_REQUIRED. Candle path ≠ fill.",
        },
    }

