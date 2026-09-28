"""Katy experiment 3: 2H last 10 on the four FIRST80 books. Price search only. No Austin."""

from __future__ import annotations

import json
from typing import Any

from roller.choosin_texas.houston import houston_identity
from roller.choosin_texas.katy.common import katy_root, select_cell, summarize_rule
from roller.choosin_texas.katy.four_universe import (
    NBA_MARK_REMAINING,
    NCAAB_MARK_REMAINING,
    apply_price_rule,
    measure_four,
    score_price_cell,
)

EXPERIMENT_ID = "KATY_V3_2H_LAST10_FOUR_UNIVERSE"
SLUG = "2h-last-10-price-search"
TITLE = "2H last 10 — four-universe price hedge vs 80/40"
NUMBER = 3
PRICE_LO = 41
PRICE_HI_GRID = (50, 55, 60, 65, 70, 75, 79)
BOOK_KEYS = ("nba_2q", "nba_3q", "ncaab_h1_2", "ncaab_h2_1")
LABELS = {
    "nba_2q": "NBA 2Q",
    "nba_3q": "NBA 3Q",
    "ncaab_h1_2": "NCAAB 1H second 10",
    "ncaab_h2_1": "NCAAB 2H first 10",
}


def experiment_dir():
    return katy_root() / SLUG


def _write_json(path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _load_json(path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def card(*, selected: dict[str, Any] | None = None) -> dict[str, Any]:
    lines = []
    if selected:
        for key in BOOK_KEYS:
            cell = selected.get(key) or {}
            if cell.get("status") == "SELECTED":
                lines.append(f"{LABELS[key]} {cell['price_lo']}–{cell['price_hi']} Δ{cell['delta_mean_cents']}¢")
            else:
                lines.append(f"{LABELS[key]} NONE")
    return {
        "number": NUMBER,
        "experiment_id": EXPERIMENT_ID,
        "slug": SLUG,
        "href": f"#/katy/{SLUG}",
        "title": TITLE,
        "question": (
            "On the locked NBA 2Q/3Q and NCAAB 1H/2H FIRST80 books, at 2H last 10 "
            "(NBA Q4 12:00 converted to that label; NCAAB 2H 10:00), what yes_bid range "
            "lets a Houston lock beat always-80/40 by cutting losers? No Austin."
        ),
        "marks": {
            "nba": "2H last 10 = Q4 12:00 remaining (720s)",
            "ncaab": "2H last 10 = 2H 10:00 remaining (600s)",
        },
        "rule": "Independent price search. PRICE_LO=41. PRICE_HI ∈ {50,55,60,65,70,75,79}. Maximize mixed 80/40 − always 80/40. Ties → fewer hedges, then tighter band. No Austin EV.",
        "status": "MEASURED" if selected else "DECLARED",
        "one_line": None if not lines else "; ".join(lines) + ". Search ≠ freeze. Books never combined.",
    }


def _book_search(measured: dict[str, Any], *, book_key: str) -> dict[str, Any]:
    rows = measured["rows"]
    cells = [score_price_cell(rows, lo=PRICE_LO, hi=hi) for hi in PRICE_HI_GRID]
    selected = select_cell(cells)
    if selected.get("status") == "SELECTED":
        applied = apply_price_rule(rows, lo=int(selected["price_lo"]), hi=int(selected["price_hi"]))
    else:
        applied = apply_price_rule(rows, lo=PRICE_LO, hi=PRICE_LO - 1)
    top = sorted(cells, key=lambda c: (-int(c["delta_sum_cents"]), int(c["n_hedge"]), int(c["price_hi"])))[:5]
    return {
        "book_key": book_key,
        "label": measured["label"],
        "loser_exam": measured["loser_exam"],
        "selected": selected,
        "top_cells": top,
        "cells": cells,
        "rows": applied,
        "summary": summarize_rule(applied, book=measured["label"]),
    }


def build_v3() -> dict[str, Any]:
    measured = measure_four()
    searched = {key: _book_search(measured[key], book_key=key) for key in BOOK_KEYS}
    selected = {key: searched[key]["selected"] for key in BOOK_KEYS}
    books = {key: searched[key]["summary"] for key in BOOK_KEYS}
    payload = {
        "status": "OBSERVED",
        "kind": "experiment",
        "product": "Katy Texas",
        "experiment_id": EXPERIMENT_ID,
        "slug": SLUG,
        "number": NUMBER,
        "title": TITLE,
        "href": f"#/katy/{SLUG}",
        "live_execution": False,
        "submits": False,
        "fill_status": "FILL_UNAVAILABLE",
        "candle_path_not_fill": True,
        "pbp_sequence_not_pit": True,
        "policy_frozen": False,
        "confirmation_accessed": False,
        "austin_used": False,
        "austin_refit": False,
        "independent_study": True,
        "universe": "derived_four_936",
        "season": "2025-2026",
        "components": {
            "path": {
                "role": "warehouse 1m TRADABLE_YES_BID + PBP clock at 2H last 10",
                "note": "PBP sequence is not candle PIT. Last bar before the first PBP at or after the mark.",
            },
            "houston": houston_identity(),
            "austin": {
                "role": "NOT USED",
                "hedge_if": "price band only",
                "missing_ev": "Austin EV is not a member of this experiment",
            },
        },
        "question": (
            "At 2H last 10 on the locked four FIRST80 books, examine losers, then search "
            "which yes_bid range would make mixed 80/40 beat always-80/40. Independent of Austin."
        ),
        "marks": {
            "label": "2H last 10",
            "nba": {
                "conversion": "4Q 12:00 remaining → 2H last 10",
                "period": 4,
                "remaining_s": NBA_MARK_REMAINING,
            },
            "ncaab": {
                "conversion": "2H 10:00 remaining = 2H last 10",
                "period": 2,
                "remaining_s": NCAAB_MARK_REMAINING,
            },
        },
        "grid_declared": {
            "price_lo": PRICE_LO,
            "price_hi": list(PRICE_HI_GRID),
            "signal": "yes_bid only",
            "austin_ev": False,
            "objective": "per-book maximize mixed_8040 − always_8040",
            "tie_break": "fewer hedges, then tighter price_hi",
            "declared_before_selection": True,
        },
        "loser_exam": {key: searched[key]["loser_exam"] for key in BOOK_KEYS},
        "selected": selected,
        "top_cells": {key: searched[key]["top_cells"] for key in BOOK_KEYS},
        "grid": {key: searched[key]["cells"] for key in BOOK_KEYS},
        "books": books,
        "book_order": list(BOOK_KEYS),
        "row_counts": {key: len(searched[key]["rows"]) for key in BOOK_KEYS},
        "ledgers": {key: searched[key]["rows"] for key in BOOK_KEYS},
        "card": card(selected=selected),
        "combined_headline_forbidden": True,
        "search_is_not_a_freeze": True,
        "note": (
            "Katy experiment 3. Independent of Austin. Four locked 2025-26 FIRST80 books. "
            "Houston lock is declared, not a fill. Search ≠ freeze."
        ),
    }
    for key in BOOK_KEYS:
        payload[key] = {
            "partition_id": key,
            "label": searched[key]["label"],
            "selected": searched[key]["selected"],
            "summary": searched[key]["summary"],
        }
    _persist(payload)
    return payload


def _persist(payload: dict[str, Any]) -> None:
    root = experiment_dir()
    body = {k: payload[k] for k in payload if k not in {"ledgers", "grid"}}
    _write_json(root / "MANIFEST.json", body)
    _write_json(root / "statistics.json", payload["books"])
    _write_json(root / "houston.json", houston_identity())
    _write_json(root / "selected.json", payload["selected"])
    _write_json(root / "loser_exam.json", payload["loser_exam"])
    _write_json(root / "grid.json", payload["grid"])
    _write_json(root / "ledgers.json", payload["ledgers"])
    (root / "REPORT.md").write_text(_report_md(payload), encoding="utf-8")


def _fmt_cell(cell: dict[str, Any] | None) -> str:
    if not cell:
        return "NONE"
    if cell.get("status") == "NONE":
        best = cell.get("best_nonpositive") or {}
        return f"NONE (best Δsum={best.get('delta_sum_cents')} at {best.get('price_lo')}–{best.get('price_hi')})"
    return (
        f"{cell.get('price_lo')}–{cell.get('price_hi')} hedge={cell.get('n_hedge')} "
        f"(L{cell.get('n_hedge_losers')}/W{cell.get('n_hedge_winners')}) "
        f"Δmean={cell.get('delta_mean_cents')} Δsum={cell.get('delta_sum_cents')}"
    )


def _fmt_exam(exam: dict[str, Any]) -> list[str]:
    losers = exam.get("losers") or {}
    winners = exam.get("winners") or {}
    return [
        f"reached={exam.get('n_reached')} losers={losers.get('n')} winners={winners.get('n')}",
        (
            f"losers open≥41={losers.get('n_open_ge_41')} already<41={losers.get('n_already_lt_41')} "
            f"already stopped={losers.get('n_t40_already_at_mark')} terminal t40={losers.get('n_t40_terminal')}"
        ),
        f"loser price mean/median {losers.get('price', {}).get('mean')}/{losers.get('price', {}).get('median')} buckets={losers.get('price_buckets')}",
        f"winner price mean/median {winners.get('price', {}).get('mean')}/{winners.get('price', {}).get('median')} buckets={winners.get('price_buckets')}",
        f"loser score-diff n/mean {losers.get('score_differential', {}).get('n')}/{losers.get('score_differential', {}).get('mean')}",
        f"winner score-diff n/mean {winners.get('score_differential', {}).get('n')}/{winners.get('score_differential', {}).get('mean')}",
    ]


def _report_md(payload: dict[str, Any]) -> str:
    lines = [
        "KATY TEXAS — EXPERIMENT 3",
        TITLE.upper(),
        "",
        "RESEARCH ONLY",
        "INDEPENDENT OF AUSTIN",
        "CANDLE PATH ≠ FILL",
        "PBP SEQUENCE ≠ PIT",
        "SEARCH ≠ FREEZE",
        "EXECUTION DISABLED",
        "",
        "# 1. QUESTION",
        "",
        payload["question"],
        "",
        "2H last 10: NBA Q4 12:00 remaining converted to that label. NCAAB 2H 10:00 remaining.",
        "Books: NBA 2Q 314, NBA 3Q 290, NCAAB 1H 193, NCAAB 2H 139. N=936 locked. Not asked-six.",
        "",
        "# 2. LOSER EXAM AT 2H LAST 10",
        "",
    ]
    for key in BOOK_KEYS:
        lines.append(f"## {LABELS[key]}")
        lines.extend(_fmt_exam(payload["loser_exam"][key]))
        lines.append("")
    lines.extend(["# 3. SELECTED PRICE BANDS", ""])
    for key in BOOK_KEYS:
        lines.append(f"{LABELS[key]}: {_fmt_cell(payload['selected'][key])}")
    lines.extend(["", "# 4. MIXED 80/40", ""])
    for key in BOOK_KEYS:
        book = payload["books"][key]
        lines.append(
            f"{LABELS[key]} mixed {book['katy_vs_8040']['mean_cents']} vs always 80/40 {book['always_8040']['mean_cents']} hedges={book['n_hedge_scenario']}"
        )
    lines.extend(
        [
            "",
            "# 5. WHAT THIS DOES NOT PROVE",
            "",
            "In-sample price search on 2025-26 locked books. Not a fill. Not Austin. Not 2026-27.",
            "Books are never combined.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def load_v3() -> dict[str, Any] | None:
    manifest = _load_json(experiment_dir() / "MANIFEST.json")
    if not manifest:
        return None
    ledgers = _load_json(experiment_dir() / "ledgers.json") or {}
    grid = _load_json(experiment_dir() / "grid.json") or {}
    return {**manifest, "ledgers": ledgers, "grid": grid}


def handle_v3() -> dict[str, Any]:
    payload = load_v3()
    if payload:
        return payload
    return build_v3()
