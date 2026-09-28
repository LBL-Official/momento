"""FIRST75 NBA T40 clock and point-differential scatter. Not PIT."""

from __future__ import annotations

import csv
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any

from roller.choosin_texas.locks75 import (
    NBA_PATH_N_75,
    NBA_SLICE_N_75,
    NBA_SLICE_T40_75,
    NBA_SURVIVE_N_75,
    NBA_T40_N_75,
    NBA_T40_PERIOD_75,
    PARTITIONS_75,
)
from roller.choosin_texas.models import ChoosinTexasError, frac, pct_display, ratio_display
from roller.choosin_texas.nba_path import (
    ALIGNMENT_MODEL,
    AXIS_PAD,
    CLOCK_BIN_ORDER,
    NBA_SLICES,
    PERIOD_ORDER,
    _axis_pct,
    _bought_margin,
    _clock_bin,
    _clock_display,
    _int_value,
    _mean_block,
    _parse_clock_s,
    _period_label,
)
from roller.choosin_texas.sources import _as_bool, default_asked_six_75_csv


def load_nba_rows_75(path: Path | None = None) -> list[dict[str, Any]]:
    csv_path = path or default_asked_six_75_csv()
    if not csv_path.is_file():
        raise ChoosinTexasError("DATA_REQUIRED", f"missing {csv_path}")
    wanted = {
        (p.csv_sport, p.csv_slice)
        for p in PARTITIONS_75
        if p.csv_sport == "NBA" and p.csv_slice in NBA_SLICES
    }
    rows: list[dict[str, Any]] = []
    with csv_path.open(newline="", encoding="utf-8") as fh:
        for rec in csv.DictReader(fh):
            key = (str(rec.get("sport") or "").strip(), str(rec.get("slice") or "").strip())
            if key not in wanted:
                continue
            ticker = str(rec.get("ticker") or rec.get("event_id") or "?")
            t40 = _as_bool(rec.get("T40"), field="T40", ticker=ticker)
            side = str(rec.get("side") or "").strip()
            entry_home = _int_value(rec.get("score_home"), field="score_home", ticker=ticker)
            entry_away = _int_value(rec.get("score_away"), field="score_away", ticker=ticker)
            final_home = _int_value(rec.get("final_score_home"), field="final_score_home", ticker=ticker)
            final_away = _int_value(rec.get("final_score_away"), field="final_score_away", ticker=ticker)
            entry_margin = _int_value(
                rec.get("bought_team_margin"), field="bought_team_margin", ticker=ticker
            )
            recon_entry = _bought_margin(entry_home, entry_away, side, ticker=ticker)
            if recon_entry != entry_margin:
                raise ChoosinTexasError(
                    "LOCK_MISMATCH",
                    f"{ticker}: bought_team_margin {entry_margin} != {recon_entry}",
                )
            final_margin = _bought_margin(final_home, final_away, side, ticker=ticker)
            alignment = str(rec.get("alignment_confidence") or "").strip()
            if alignment not in {"HIGH", "MEDIUM"}:
                raise ChoosinTexasError(
                    "DATA_REQUIRED", f"{ticker}: alignment {alignment!r} not HIGH/MEDIUM"
                )
            item: dict[str, Any] = {
                "ticker": ticker,
                "slice": key[1],
                "bought_team": str(rec.get("bought_team") or ""),
                "side": side,
                "t40": t40,
                "entry_margin": entry_margin,
                "final_margin": final_margin,
                "alignment_confidence": alignment,
                "t40_margin": None,
                "exit_period": None,
                "exit_period_label": None,
                "exit_remaining_s": None,
                "exit_game_clock": None,
                "clock_bin": None,
            }
            if t40:
                period = _int_value(rec.get("exit_period"), field="exit_period", ticker=ticker)
                remaining_s = _parse_clock_s(rec.get("exit_game_clock"), ticker=ticker)
                exit_home = _int_value(rec.get("exit_score_home"), field="exit_score_home", ticker=ticker)
                exit_away = _int_value(rec.get("exit_score_away"), field="exit_score_away", ticker=ticker)
                item["t40_margin"] = _bought_margin(exit_home, exit_away, side, ticker=ticker)
                item["exit_period"] = period
                item["exit_period_label"] = _period_label(period)
                item["exit_remaining_s"] = remaining_s
                item["exit_game_clock"] = str(rec.get("exit_game_clock") or "").strip()
                item["clock_bin"] = _clock_bin(remaining_s)
            rows.append(item)
    return rows


def _slice_clock_75(rows: list[dict[str, Any]], slice_id: str) -> dict[str, Any]:
    t40_rows = [row for row in rows if row["slice"] == slice_id and row["t40"]]
    n_t40 = len(t40_rows)
    expected = NBA_SLICE_T40_75[slice_id]
    if n_t40 != expected:
        raise ChoosinTexasError(
            "LOCK_MISMATCH", f"FIRST75 NBA {slice_id} T40 {n_t40} != lock {expected}"
        )
    period_n = {label: 0 for label in PERIOD_ORDER}
    rem_by_period: dict[str, list[int]] = defaultdict(list)
    bin_n = {(period, bin_id): 0 for period in PERIOD_ORDER for bin_id in CLOCK_BIN_ORDER}
    for row in t40_rows:
        period = str(row["exit_period_label"])
        bin_id = str(row["clock_bin"])
        period_n[period] += 1
        rem_by_period[period].append(int(row["exit_remaining_s"]))
        bin_n[(period, bin_id)] += 1
    if period_n != NBA_T40_PERIOD_75[slice_id]:
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            f"FIRST75 NBA {slice_id} T40 period mix {period_n} != lock {NBA_T40_PERIOD_75[slice_id]}",
        )
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
                    "n_display": ratio_display(count, n_t40),
                    "pct_display": pct_display(count, n_t40),
                    "bar_pct": float(Fraction(count, n_t40) * 100),
                }
            )
    means = []
    for period in PERIOD_ORDER:
        values = rem_by_period.get(period) or []
        if not values:
            continue
        remaining = Fraction(sum(values), len(values))
        means.append(
            {
                "period": period,
                "n": len(values),
                "remaining_s": frac(remaining.numerator, remaining.denominator),
                "clock_display": _clock_display(remaining),
            }
        )
    return {
        "slice": slice_id,
        "slice_label": "2Q" if slice_id == "Q2" else "3Q",
        "n": NBA_SLICE_N_75[slice_id],
        "n_t40": n_t40,
        "period_mix": period_n,
        "bins": bins,
        "mean_remaining": means,
    }


def _cohort_summary(rows: list[dict[str, Any]], *, t40: bool) -> dict[str, Any]:
    cohort = [row for row in rows if row["t40"] is t40]
    body = {
        "n": len(cohort),
        "entry": _mean_block([int(row["entry_margin"]) for row in cohort]),
        "final": _mean_block([int(row["final_margin"]) for row in cohort]),
    }
    if t40:
        body["t40_time"] = _mean_block([int(row["t40_margin"]) for row in cohort])
    return body


def build_nba_path_75(path: Path | None = None) -> dict[str, Any]:
    rows = load_nba_rows_75(path)
    if len(rows) != NBA_PATH_N_75:
        raise ChoosinTexasError(
            "LOCK_MISMATCH", f"FIRST75 NBA path N {len(rows)} != {NBA_PATH_N_75}"
        )
    survive = [row for row in rows if not row["t40"]]
    t40_rows = [row for row in rows if row["t40"]]
    if len(survive) != NBA_SURVIVE_N_75 or len(t40_rows) != NBA_T40_N_75:
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            f"FIRST75 NBA survive/T40 {len(survive)}/{len(t40_rows)} "
            f"!= {NBA_SURVIVE_N_75}/{NBA_T40_N_75}",
        )
    for slice_id, expected in NBA_SLICE_N_75.items():
        got = sum(1 for row in rows if row["slice"] == slice_id)
        if got != expected:
            raise ChoosinTexasError(
                "LOCK_MISMATCH", f"FIRST75 NBA {slice_id} N {got} != {expected}"
            )

    xs = [int(row["entry_margin"]) for row in rows]
    ys = [int(row["final_margin"]) for row in rows]
    x_lo, x_hi = min(xs) - AXIS_PAD, max(xs) + AXIS_PAD
    y_lo, y_hi = min(ys) - AXIS_PAD, max(ys) + AXIS_PAD
    points = []
    for row in rows:
        x_pct = _axis_pct(int(row["entry_margin"]), x_lo, x_hi)
        y_pct = _axis_pct(int(row["final_margin"]), y_lo, y_hi)
        points.append(
            {
                "ticker": row["ticker"],
                "slice": row["slice"],
                "bought_team": row["bought_team"],
                "t40": row["t40"],
                "cohort": "T40" if row["t40"] else "survive",
                "entry_margin": row["entry_margin"],
                "final_margin": row["final_margin"],
                "t40_margin": row["t40_margin"],
                "alignment_confidence": row["alignment_confidence"],
                "plot_x_pct": x_pct,
                "plot_y_pct": 100.0 - y_pct,
            }
        )
    return {
        "status": "OBSERVED",
        "product": "Choosin Texas",
        "page": "texas_75",
        "live_execution": False,
        "submits": False,
        "sport": "NBA",
        "rule": "FIRST75",
        "n": NBA_PATH_N_75,
        "n_survive": NBA_SURVIVE_N_75,
        "n_t40": NBA_T40_N_75,
        "alignment": {
            "model": ALIGNMENT_MODEL,
            "note": (
                "Clock and T40 score are a modeled PBP snap at the T40 candle "
                "after FIRST75 entry. Not warehouse PBP↔candle PIT. "
                "PIT stays OPERATION_REQUIRED. Candle path ≠ fill."
            ),
        },
        "clocks": [_slice_clock_75(rows, slice_id) for slice_id in NBA_SLICES],
        "scatter": {
            "x_label": "bought-team margin at FIRST75 entry",
            "y_label": "bought-team margin at final",
            "x_min": x_lo,
            "x_max": x_hi,
            "y_min": y_lo,
            "y_max": y_hi,
            "points": points,
        },
        "margins": {
            "survive": _cohort_summary(rows, t40=False),
            "t40": _cohort_summary(rows, t40=True),
        },
    }
