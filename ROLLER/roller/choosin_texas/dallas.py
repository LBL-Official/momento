"""Dallas desk: NBA FIRST80 score/price snapshots vs later T40. Not live."""

from __future__ import annotations

import csv
import math
from fractions import Fraction
from pathlib import Path
from typing import Any

from roller.choosin_texas.locks import (
    NBA_PATH_N,
    NBA_SLICE_N,
    NBA_SLICE_SURVIVE,
    NBA_SLICE_T40,
    NBA_SLICE_T40_LOSE,
    NBA_SLICE_T40_WIN,
    NBA_SURVIVE_N,
    NBA_T40_LOSE_N,
    NBA_T40_N,
    NBA_T40_WIN_N,
    PARTITIONS,
)
from roller.choosin_texas.models import ChoosinTexasError, pct_display, ratio_display
from roller.choosin_texas.nba_path import (
    NBA_SLICES,
    _axis_pct,
    _bought_margin,
    _int_value,
    _parse_clock_s,
    _period_label,
)
from roller.choosin_texas.sources import _as_bool, _cents_field, default_asked_six_csv

AXIS_PAD = 2
PREGAME_SOURCE = "KALSHI_LAST_PRE_TIP_YES_BID"
COHORT_LABEL = {
    "survive": "survive",
    "t40_win": "T40 then won",
    "t40_lose": "T40 then lost",
}
LEAD_BINS = (
    ("le0", "≤0"),
    ("1_3", "1–3"),
    ("4_6", "4–6"),
    ("7_9", "7–9"),
    ("ge10", "≥10"),
)
PREGAME_BINS = (
    ("le30", "≤30¢"),
    ("31_35", "31–35¢"),
    ("36_40", "36–40¢"),
    ("41_45", "41–45¢"),
    ("46_50", "46–50¢"),
    ("51_55", "51–55¢"),
    ("56_60", "56–60¢"),
    ("61_65", "61–65¢"),
    ("66_70", "66–70¢"),
    ("ge71", "≥71¢"),
)
TICK_STEPS = (1, 2, 5, 10, 20, 25, 50, 100)


def _lead_bin(lead: int) -> str:
    if lead <= 0:
        return "le0"
    if lead <= 3:
        return "1_3"
    if lead <= 6:
        return "4_6"
    if lead <= 9:
        return "7_9"
    return "ge10"


def _pregame_bin(cents: int) -> str:
    if cents <= 30:
        return "le30"
    if cents <= 35:
        return "31_35"
    if cents <= 40:
        return "36_40"
    if cents <= 45:
        return "41_45"
    if cents <= 50:
        return "46_50"
    if cents <= 55:
        return "51_55"
    if cents <= 60:
        return "56_60"
    if cents <= 65:
        return "61_65"
    if cents <= 70:
        return "66_70"
    return "ge71"


def _pregame_cents(rec: dict[str, Any], side: str, *, ticker: str) -> int:
    field = "pregame_home_win_prob" if side == "home" else "pregame_away_win_prob"
    raw = rec.get(field)
    if raw is None or str(raw).strip() == "":
        raise ChoosinTexasError("DATA_REQUIRED", f"missing {field} for {ticker}")
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ChoosinTexasError(
            "DATA_REQUIRED", f"cannot parse {field}={raw!r} for {ticker}"
        ) from exc
    if value < 0 or value > 1.5:
        raise ChoosinTexasError(
            "LOCK_MISMATCH", f"{ticker}: {field}={value} is not a 0–1 pre-tip bid"
        )
    return int(round(value * 100))


def _rate_block(count: int, n: int) -> dict[str, Any]:
    if n <= 0:
        raise ChoosinTexasError("LOCK_MISMATCH", "Dallas rate denominator is 0")
    return {
        "n": n,
        "count": count,
        "display": ratio_display(count, n),
        "pct_display": pct_display(count, n),
        "bar_pct": float(Fraction(count, n) * 100),
    }


def _cohort_rates(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    t40_win = sum(1 for row in rows if row["cohort"] == "t40_win")
    t40_lose = sum(1 for row in rows if row["cohort"] == "t40_lose")
    survive = sum(1 for row in rows if row["cohort"] == "survive")
    t40_n = t40_win + t40_lose
    if t40_win + t40_lose + survive != n or t40_n + survive != n:
        raise ChoosinTexasError("LOCK_MISMATCH", "Dallas bin cohort identity failed")
    return {
        "n": n,
        "t40": _rate_block(t40_n, n),
        "t40_win": _rate_block(t40_win, n),
        "t40_lose": _rate_block(t40_lose, n),
        "survive": _rate_block(survive, n),
    }


def _cut_hover(label: str, rates: dict[str, Any]) -> list[str]:
    return [
        label,
        f"n {rates['n']}",
        f"T40 {rates['t40']['display']} · {rates['t40']['pct_display']}",
        f"W ∩ T40 {rates['t40_win']['display']} · {rates['t40_win']['pct_display']}",
        f"L ∩ T40 {rates['t40_lose']['display']} · {rates['t40_lose']['pct_display']}",
        f"survive {rates['survive']['display']} · {rates['survive']['pct_display']}",
    ]


def _bucket_rows(
    rows: list[dict[str, Any]],
    *,
    key_fn,
    labels: tuple[tuple[str, str], ...],
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {key: [] for key, _ in labels}
    for row in rows:
        key = key_fn(row)
        if key not in groups:
            raise ChoosinTexasError("LOCK_MISMATCH", f"unknown Dallas bucket {key}")
        groups[key].append(row)
    out = []
    for key, label in labels:
        group = groups[key]
        if not group:
            continue
        rates = _cohort_rates(group)
        out.append(
            {
                "key": key,
                "label": label,
                "n": rates["n"],
                "t40": rates["t40"],
                "t40_win": rates["t40_win"],
                "t40_lose": rates["t40_lose"],
                "survive": rates["survive"],
                "hover_lines": _cut_hover(label, rates),
            }
        )
    if sum(int(row["n"]) for row in out) != len(rows):
        raise ChoosinTexasError("LOCK_MISMATCH", "Dallas bucket n does not sum to slice N")
    return out


def _cross_grid(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (_lead_bin(int(row["lead_80"])), _pregame_bin(int(row["pregame_cents"])))
        groups.setdefault(key, []).append(row)
    lead_labels = dict(LEAD_BINS)
    pregame_labels = dict(PREGAME_BINS)
    cells = []
    used_lead: set[str] = set()
    used_pregame: set[str] = set()
    for lead_key, _ in LEAD_BINS:
        for pregame_key, _ in PREGAME_BINS:
            group = groups.get((lead_key, pregame_key))
            if not group:
                continue
            rates = _cohort_rates(group)
            used_lead.add(lead_key)
            used_pregame.add(pregame_key)
            label = f"lead {lead_labels[lead_key]} · open {pregame_labels[pregame_key]}"
            cells.append(
                {
                    "key": f"{lead_key}__{pregame_key}",
                    "lead_key": lead_key,
                    "lead_label": lead_labels[lead_key],
                    "pregame_key": pregame_key,
                    "pregame_label": pregame_labels[pregame_key],
                    "n": rates["n"],
                    "t40": rates["t40"],
                    "t40_win": rates["t40_win"],
                    "t40_lose": rates["t40_lose"],
                    "survive": rates["survive"],
                    "hover_lines": _cut_hover(label, rates),
                }
            )
    if sum(int(cell["n"]) for cell in cells) != len(rows):
        raise ChoosinTexasError("LOCK_MISMATCH", "Dallas cross n does not sum to slice N")
    return {
        "lead_labels": [{"key": key, "label": label} for key, label in LEAD_BINS if key in used_lead],
        "pregame_labels": [
            {"key": key, "label": label} for key, label in PREGAME_BINS if key in used_pregame
        ],
        "cells": cells,
    }


def _cuts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "lead_80": _bucket_rows(rows, key_fn=lambda row: _lead_bin(int(row["lead_80"])), labels=LEAD_BINS),
        "pregame": _bucket_rows(
            rows, key_fn=lambda row: _pregame_bin(int(row["pregame_cents"])), labels=PREGAME_BINS
        ),
        "cross": _cross_grid(rows),
    }


def load_dallas_rows(path: Path | None = None) -> list[dict[str, Any]]:
    csv_path = path or default_asked_six_csv()
    if not csv_path.is_file():
        raise ChoosinTexasError("DATA_REQUIRED", f"missing {csv_path}")
    wanted = {
        (p.csv_sport, p.csv_slice)
        for p in PARTITIONS
        if p.csv_sport == "NBA" and p.csv_slice in NBA_SLICES
    }
    rows: list[dict[str, Any]] = []
    with csv_path.open(newline="", encoding="utf-8") as fh:
        for rec in csv.DictReader(fh):
            key = (str(rec.get("sport") or "").strip(), str(rec.get("slice") or "").strip())
            if key not in wanted:
                continue
            ticker = str(rec.get("ticker") or rec.get("event_id") or "?")
            side = str(rec.get("side") or "").strip()
            if side not in {"home", "away"}:
                raise ChoosinTexasError("LOCK_MISMATCH", f"bad side {side!r} for {ticker}")
            source = str(rec.get("pregame_source") or "").strip()
            if source != PREGAME_SOURCE:
                raise ChoosinTexasError(
                    "LOCK_MISMATCH", f"{ticker}: pregame_source {source!r}"
                )
            t40 = _as_bool(rec.get("T40"), field="T40", ticker=ticker)
            win = _as_bool(rec.get("W"), field="W", ticker=ticker)
            entry_home = _int_value(rec.get("score_home"), field="score_home", ticker=ticker)
            entry_away = _int_value(rec.get("score_away"), field="score_away", ticker=ticker)
            final_home = _int_value(rec.get("final_score_home"), field="final_score_home", ticker=ticker)
            final_away = _int_value(rec.get("final_score_away"), field="final_score_away", ticker=ticker)
            lead_80 = _int_value(rec.get("bought_team_margin"), field="bought_team_margin", ticker=ticker)
            if _bought_margin(entry_home, entry_away, side, ticker=ticker) != lead_80:
                raise ChoosinTexasError(
                    "LOCK_MISMATCH", f"{ticker}: lead at 80 does not match scores"
                )
            entry_bid = _cents_field(
                rec.get("market_yes_bid"), field="market_yes_bid", ticker=ticker
            )
            if entry_bid < 80:
                raise ChoosinTexasError("LOCK_MISMATCH", f"{ticker}: entry bid {entry_bid} < 80")
            pregame = _pregame_cents(rec, side, ticker=ticker)
            final_lead = _bought_margin(final_home, final_away, side, ticker=ticker)
            if t40:
                cohort = "t40_win" if win else "t40_lose"
            else:
                cohort = "survive"
            item: dict[str, Any] = {
                "ticker": ticker,
                "slice": key[1],
                "bought_team": str(rec.get("bought_team") or ""),
                "side": side,
                "w": win,
                "t40": t40,
                "cohort": cohort,
                "pregame_cents": pregame,
                "entry_bid": entry_bid,
                "lead_80": lead_80,
                "final_lead": final_lead,
                "t40_lead": None,
                "exit_period_label": None,
                "exit_game_clock": None,
            }
            if t40:
                period = _int_value(rec.get("exit_period"), field="exit_period", ticker=ticker)
                item["t40_lead"] = _bought_margin(
                    _int_value(rec.get("exit_score_home"), field="exit_score_home", ticker=ticker),
                    _int_value(rec.get("exit_score_away"), field="exit_score_away", ticker=ticker),
                    side,
                    ticker=ticker,
                )
                item["exit_period_label"] = _period_label(period)
                item["exit_game_clock"] = str(rec.get("exit_game_clock") or "").strip()
                _parse_clock_s(item["exit_game_clock"], ticker=ticker)
            rows.append(item)
    return rows


def _assert_locks(rows: list[dict[str, Any]]) -> None:
    if len(rows) != NBA_PATH_N:
        raise ChoosinTexasError("LOCK_MISMATCH", f"Dallas N {len(rows)} != {NBA_PATH_N}")
    survive = sum(1 for row in rows if row["cohort"] == "survive")
    t40_win = sum(1 for row in rows if row["cohort"] == "t40_win")
    t40_lose = sum(1 for row in rows if row["cohort"] == "t40_lose")
    if (survive, t40_win, t40_lose) != (NBA_SURVIVE_N, NBA_T40_WIN_N, NBA_T40_LOSE_N):
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            f"Dallas cohorts {survive}/{t40_win}/{t40_lose} != "
            f"{NBA_SURVIVE_N}/{NBA_T40_WIN_N}/{NBA_T40_LOSE_N}",
        )
    if survive + t40_win + t40_lose != NBA_PATH_N or t40_win + t40_lose != NBA_T40_N:
        raise ChoosinTexasError("LOCK_MISMATCH", "Dallas cohort identity failed")
    for slice_id in NBA_SLICES:
        sub = [row for row in rows if row["slice"] == slice_id]
        if len(sub) != NBA_SLICE_N[slice_id]:
            raise ChoosinTexasError(
                "LOCK_MISMATCH", f"Dallas {slice_id} N {len(sub)} != {NBA_SLICE_N[slice_id]}"
            )
        got = (
            sum(1 for row in sub if row["cohort"] == "survive"),
            sum(1 for row in sub if row["t40"]),
            sum(1 for row in sub if row["cohort"] == "t40_win"),
            sum(1 for row in sub if row["cohort"] == "t40_lose"),
        )
        expected = (
            NBA_SLICE_SURVIVE[slice_id],
            NBA_SLICE_T40[slice_id],
            NBA_SLICE_T40_WIN[slice_id],
            NBA_SLICE_T40_LOSE[slice_id],
        )
        if got != expected:
            raise ChoosinTexasError(
                "LOCK_MISMATCH", f"Dallas {slice_id} cohorts {got} != {expected}"
            )


def _rates(rows: list[dict[str, Any]]) -> dict[str, Any]:
    body = _cohort_rates(rows)
    body["note"] = "W∩T40 is a path stop and a terminal win. Not an early-exit rule."
    return body


def _chart_axis(xs: list[int], ys: list[int]) -> dict[str, int]:
    return {
        "x_min": min(xs) - AXIS_PAD,
        "x_max": max(xs) + AXIS_PAD,
        "y_min": min(ys) - AXIS_PAD,
        "y_max": max(ys) + AXIS_PAD,
    }


def _tick_step(lo: int, hi: int) -> int:
    span = max(1, hi - lo)
    for step in TICK_STEPS:
        if span / step <= 6:
            return step
    return 100


def _ticks(lo: int, hi: int, *, invert: bool) -> list[dict[str, Any]]:
    if hi < lo:
        raise ChoosinTexasError("LOCK_MISMATCH", f"Dallas axis {lo} > {hi}")
    if hi == lo:
        return [{"value": lo, "label": str(lo), "plot_pct": 50.0}]
    step = _tick_step(lo, hi)
    start = math.ceil(lo / step) * step
    values = [lo]
    value = start
    while value < hi:
        if value != lo:
            values.append(int(value))
        value += step
    if values[-1] != hi:
        values.append(hi)
    out = []
    for item in values:
        pct = _axis_pct(int(item), lo, hi)
        if invert:
            pct = 100.0 - pct
        out.append({"value": int(item), "label": str(int(item)), "plot_pct": pct})
    return out


def _chart_payload(x_label: str, y_label: str, axis: dict[str, int]) -> dict[str, Any]:
    return {
        "x_label": x_label,
        "y_label": y_label,
        **axis,
        "x_ticks": _ticks(axis["x_min"], axis["x_max"], invert=False),
        "y_ticks": _ticks(axis["y_min"], axis["y_max"], invert=True),
    }


def _cohort_name(cohort: str) -> str:
    if cohort not in COHORT_LABEL:
        raise ChoosinTexasError("LOCK_MISMATCH", f"unknown Dallas cohort {cohort}")
    return COHORT_LABEL[cohort]


def _game_hover(row: dict[str, Any]) -> list[str]:
    lines = [
        f"{row['ticker']} · {row['bought_team']}",
        "this dot = one FIRST80 book",
        f"cohort = {_cohort_name(row['cohort'])}",
        (
            f"pregame {row['pregame_cents']}¢ · lead at 80 = {row['lead_80']} · "
            f"entry {row['entry_bid']}¢"
        ),
        f"final lead {row['final_lead']}",
    ]
    if row["t40"]:
        lines.append(
            f"T40 lead {row['t40_lead']} · {row['exit_period_label']} {row['exit_game_clock']}"
        )
    return lines


def _snapshot_hover(row: dict[str, Any], label: str, lead: int, price: int) -> list[str]:
    return [
        f"{row['ticker']} · {row['bought_team']}",
        f"this dot = {label}",
        f"cohort = {_cohort_name(row['cohort'])}",
        f"lead at snapshot = {lead} · price {price}¢",
    ]


def _collapse_hover(row: dict[str, Any], delta: int) -> list[str]:
    return [
        f"{row['ticker']} · {row['bought_team']}",
        "this dot = T40 collapse (lead at 80 → lead at 40)",
        f"cohort = {_cohort_name(row['cohort'])}",
        f"lead 80 = {row['lead_80']} → T40 lead {row['t40_lead']} · delta {delta}",
        f"{row['exit_period_label']} {row['exit_game_clock']}",
    ]


def _slice_payload(rows: list[dict[str, Any]], slice_id: str) -> dict[str, Any]:
    game_axis = _chart_axis(
        [int(row["lead_80"]) for row in rows],
        [int(row["pregame_cents"]) for row in rows],
    )
    snap_leads: list[int] = []
    snap_prices: list[int] = []
    for row in rows:
        snap_leads.extend([0, int(row["lead_80"]), int(row["final_lead"])])
        snap_prices.extend([int(row["pregame_cents"]), int(row["entry_bid"]), 100 if row["w"] else 0])
        if row["t40"]:
            snap_leads.append(int(row["t40_lead"]))
            snap_prices.append(40)
    snap_axis = _chart_axis(snap_leads, snap_prices)
    t40_rows = [row for row in rows if row["t40"]]
    collapse_axis = (
        _chart_axis(
            [int(row["lead_80"]) for row in t40_rows],
            [int(row["t40_lead"]) for row in t40_rows] + [int(row["lead_80"]) for row in t40_rows],
        )
        if t40_rows
        else {"x_min": 0, "x_max": 1, "y_min": 0, "y_max": 1}
    )

    games = []
    snapshots = []
    collapse = []
    for row in rows:
        games.append(
            {
                "ticker": row["ticker"],
                "slice": row["slice"],
                "bought_team": row["bought_team"],
                "cohort": row["cohort"],
                "w": row["w"],
                "t40": row["t40"],
                "pregame_cents": row["pregame_cents"],
                "entry_bid": row["entry_bid"],
                "lead_80": row["lead_80"],
                "t40_lead": row["t40_lead"],
                "final_lead": row["final_lead"],
                "exit_period_label": row["exit_period_label"],
                "exit_game_clock": row["exit_game_clock"],
                "plot_x_pct": _axis_pct(int(row["lead_80"]), game_axis["x_min"], game_axis["x_max"]),
                "plot_y_pct": 100.0
                - _axis_pct(int(row["pregame_cents"]), game_axis["y_min"], game_axis["y_max"]),
                "hover_lines": _game_hover(row),
            }
        )
        snaps = [
            ("PREGAME", 0, int(row["pregame_cents"])),
            ("FIRST80", int(row["lead_80"]), int(row["entry_bid"])),
        ]
        if row["t40"]:
            snaps.append(("T40", int(row["t40_lead"]), 40))
        snaps.append(("FINAL", int(row["final_lead"]), 100 if row["w"] else 0))
        for label, lead, price in snaps:
            snapshots.append(
                {
                    "ticker": row["ticker"],
                    "slice": row["slice"],
                    "bought_team": row["bought_team"],
                    "cohort": row["cohort"],
                    "label": label,
                    "lead": lead,
                    "price_cents": price,
                    "plot_x_pct": _axis_pct(lead, snap_axis["x_min"], snap_axis["x_max"]),
                    "plot_y_pct": 100.0
                    - _axis_pct(price, snap_axis["y_min"], snap_axis["y_max"]),
                    "hover_lines": _snapshot_hover(row, label, lead, price),
                }
            )
        if row["t40"]:
            delta = int(row["t40_lead"]) - int(row["lead_80"])
            collapse.append(
                {
                    "ticker": row["ticker"],
                    "slice": row["slice"],
                    "bought_team": row["bought_team"],
                    "cohort": row["cohort"],
                    "lead_80": row["lead_80"],
                    "t40_lead": row["t40_lead"],
                    "delta": delta,
                    "exit_period_label": row["exit_period_label"],
                    "exit_game_clock": row["exit_game_clock"],
                    "plot_x_pct": _axis_pct(
                        int(row["lead_80"]), collapse_axis["x_min"], collapse_axis["x_max"]
                    ),
                    "plot_y_pct": 100.0
                    - _axis_pct(
                        int(row["t40_lead"]), collapse_axis["y_min"], collapse_axis["y_max"]
                    ),
                    "plot_x0_pct": _axis_pct(
                        int(row["lead_80"]), collapse_axis["x_min"], collapse_axis["x_max"]
                    ),
                    "plot_y0_pct": 100.0
                    - _axis_pct(
                        int(row["lead_80"]), collapse_axis["y_min"], collapse_axis["y_max"]
                    ),
                    "hover_lines": _collapse_hover(row, delta),
                }
            )

    return {
        "slice": slice_id,
        "slice_label": "2Q" if slice_id == "Q2" else "3Q",
        "n": len(rows),
        "rates": _rates(rows),
        "games": games,
        "snapshots": snapshots,
        "collapse": collapse,
        "cuts": _cuts(rows),
        "game_chart": _chart_payload(
            "bought-team lead at FIRST80",
            "pregame Kalshi yes bid (bought team, ¢)",
            game_axis,
        ),
        "snapshot_chart": _chart_payload(
            "bought-team lead at snapshot",
            "contract price at snapshot (¢)",
            snap_axis,
        ),
        "collapse_chart": _chart_payload(
            "lead at FIRST80",
            "lead when T40 printed",
            collapse_axis,
        ),
    }


def build_dallas(path: Path | None = None) -> dict[str, Any]:
    rows = load_dallas_rows(path)
    _assert_locks(rows)
    slices = [_slice_payload([row for row in rows if row["slice"] == slice_id], slice_id) for slice_id in NBA_SLICES]
    return {
        "status": "OBSERVED",
        "product": "Choosin Texas",
        "page": "dallas",
        "live_execution": False,
        "submits": False,
        "sport": "NBA",
        "n": NBA_PATH_N,
        "n_survive": NBA_SURVIVE_N,
        "n_t40": NBA_T40_N,
        "n_t40_win": NBA_T40_WIN_N,
        "n_t40_lose": NBA_T40_LOSE_N,
        "rates": _rates(rows),
        "cuts": _cuts(rows),
        "slices": slices,
        "note": (
            "Historical snapshots, not a live current quote. "
            "PREGAME lead is tip (0). T40 price is the ledger 40. "
            "W∩T40 recovered after the path stop. Not an early-exit rule. "
            "Not warehouse PBP↔candle PIT."
        ),
        "disclaimers": [
            "LIVE EXECUTION = FALSE",
            "CANDLE PATH ≠ ACTUAL FILL",
            "no live current price or lead",
            "not an early-exit rule",
            "W∩T40 is a terminal win and an 80/40 loss",
            "cut rates are not a tradable filter",
        ],
    }
