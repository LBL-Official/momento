"""Katy experiment 5: 2H last 10 Austin range × EV on four books vs 80/40."""

from __future__ import annotations

from typing import Any

from roller.austin.experiments.ids import EXPERIMENT_A, EXPERIMENT_B
from roller.austin.store import load_json, write_json
from roller.choosin_texas.houston import houston_identity
from roller.choosin_texas.katy.common import (
    apply_rule,
    assert_confirmation_sealed,
    components,
    katy_root,
    measure_ncaab,
    measure_nba_slices,
    score_cell,
    select_cell,
    summarize_rule,
)

EXPERIMENT_ID = "KATY_V5_LAST10_AUSTIN_FOUR_BOOK"
SLUG = "last10-austin-four-book"
TITLE = "2H last 10 — four-book Austin range × EV vs 80/40"
NUMBER = 5
PRICE_LO = 41
PRICE_HI_GRID = (50, 55, 60, 65, 70, 75, 79)
EV_LT_GRID = (-20, -10, 0, 5, 10, 15, 20)
NBA_MARK_REMAINING = 720
NCAAB_MARK_REMAINING = 600
BOOK_KEYS = ("nba_2q", "nba_3q", "ncaab_h1_2_discovery", "ncaab_h2_1_discovery")
LABELS = {
    "nba_2q": "NBA 2Q",
    "nba_3q": "NBA 3Q",
    "ncaab_h1_2_discovery": "NCAAB 1H Discovery",
    "ncaab_h2_1_discovery": "NCAAB 2H Discovery",
}


def experiment_dir():
    return katy_root() / SLUG


def card(*, selected: dict[str, Any] | None = None) -> dict[str, Any]:
    lines = []
    if selected:
        for key in BOOK_KEYS:
            cell = selected.get(key) or {}
            if cell.get("status") == "SELECTED":
                lines.append(
                    f"{LABELS[key]} {cell['price_lo']}–{cell['price_hi']} / EV<{cell['austin_ev_lt']} Δ{cell['delta_mean_cents']}¢"
                )
            else:
                lines.append(f"{LABELS[key]} NONE")
    return {
        "number": NUMBER,
        "experiment_id": EXPERIMENT_ID,
        "slug": SLUG,
        "href": f"#/katy/{SLUG}",
        "title": TITLE,
        "question": (
            "At 2H last 10 (NBA Q4 12:00 / NCAAB 2H 10:00), after examining losers, "
            "what yes_bid range and Austin EV cutoff lets a Houston lock beat always-80/40 "
            "on NBA 2Q, NBA 3Q, and NCAAB 1H/2H Discovery?"
        ),
        "marks": {
            "nba": "2H last 10 = Q4 12:00 remaining (720s; on-grid)",
            "ncaab": "2H last 10 = 2H 10:00 remaining (600s; on-grid)",
        },
        "rule": "Preregistered grid. PRICE_LO=41. PRICE_HI ∈ {50,55,60,65,70,75,79}. Austin EV < {-20,-10,0,5,10,15,20}. Maximize mixed 80/40 − always 80/40. Ties → fewer hedges, then tighter band. Austin not refit.",
        "status": "MEASURED" if selected else "DECLARED",
        "one_line": None if not lines else "; ".join(lines) + ". Search ≠ freeze. Books never combined.",
    }


def _grid(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        score_cell(rows, lo=PRICE_LO, hi=hi, ev_lt=float(ev_lt))
        for hi in PRICE_HI_GRID
        for ev_lt in EV_LT_GRID
    ]


def _book_search(measured: dict[str, Any], *, book_key: str) -> dict[str, Any]:
    rows = measured["rows"]
    cells = _grid(rows)
    selected = select_cell(cells)
    if selected.get("status") == "SELECTED":
        applied = apply_rule(
            rows,
            lo=int(selected["price_lo"]),
            hi=int(selected["price_hi"]),
            ev_lt=float(selected["austin_ev_lt"]),
            block_if_already_stopped=True,
        )
    else:
        applied = apply_rule(rows, lo=PRICE_LO, hi=PRICE_LO - 1, ev_lt=0.0, block_if_already_stopped=True)
    top = sorted(
        cells,
        key=lambda c: (-int(c["delta_sum_cents"]), int(c["n_hedge"]), int(c["price_hi"]), float(c["austin_ev_lt"])),
    )[:5]
    return {
        "book_key": book_key,
        "experiment_id": measured.get("experiment_id"),
        "label": measured.get("label"),
        "loser_exam": measured["loser_exam"],
        "selected": selected,
        "top_cells": top,
        "cells": cells,
        "rows": applied,
        "summary": summarize_rule(applied, book=measured.get("label") or book_key),
    }


def build_v5() -> dict[str, Any]:
    assert_confirmation_sealed()
    ncaab = measure_ncaab(mark_remaining=NCAAB_MARK_REMAINING)
    nba = measure_nba_slices(mark_remaining=NBA_MARK_REMAINING, ev_when="open")
    searched = {
        "nba_2q": _book_search(nba["nba_2q"], book_key="nba_2q"),
        "nba_3q": _book_search(nba["nba_3q"], book_key="nba_3q"),
        "ncaab_h1_2_discovery": _book_search(ncaab[EXPERIMENT_A], book_key="ncaab_h1_2_discovery"),
        "ncaab_h2_1_discovery": _book_search(ncaab[EXPERIMENT_B], book_key="ncaab_h2_1_discovery"),
    }
    selected = {key: searched[key]["selected"] for key in BOOK_KEYS}
    books = {key: searched[key]["summary"] for key in BOOK_KEYS}
    payload = {
        "status": "OBSERVED",
        "kind": "experiment",
        "surface": "search",
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
        "policy_frozen": False,
        "confirmation_accessed": False,
        "confirmation_A": "SEALED_UNSPENT",
        "confirmation_B": "SEALED_UNSPENT",
        "phase5_policy": "NONE",
        "austin_used": True,
        "austin_never_filters_entry": True,
        "austin_refit": False,
        "optimize": "threshold_and_range_search_on_split_books",
        "not_a_retrain": True,
        "components": components(hedge_if="selected per-book cell from the preregistered grid, else NONE"),
        "question": (
            "At 2H last 10, examine eventual 80/40 losers on each book, then search which "
            "yes_bid range and frozen Austin EV cutoff make mixed 80/40 beat always-80/40."
        ),
        "marks": {
            "label": "2H last 10",
            "nba": {"conversion": "4Q 12:00 remaining → 2H last 10", "period": 4, "remaining_s": NBA_MARK_REMAINING},
            "ncaab": {"conversion": "2H 10:00 remaining = 2H last 10", "period": 2, "remaining_s": NCAAB_MARK_REMAINING},
        },
        "grid_declared": {
            "price_lo": PRICE_LO,
            "price_hi": list(PRICE_HI_GRID),
            "austin_ev_lt": list(EV_LT_GRID),
            "objective": "per-book maximize mixed_8040 − always_8040 (sum of cents)",
            "tie_break": "fewer hedges, then tighter price_hi, then lower EV cutoff",
            "fail_closed": "missing Austin EV → no hedge; t40_already or yes_bid < 41 → already stopped",
            "declared_before_selection": True,
            "ncaab_note": "NCAAB Austin EV is Discovery only. Confirmation sealed. Full 193/139 is experiments 3–4.",
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
            "Katy experiment 5. Frozen Austin is queried, not refit. NBA 2Q/3Q are the locked 314/290 books. "
            "NCAAB is Discovery only. Houston lock is declared, not a fill. Search ≠ freeze."
        ),
    }
    for key in BOOK_KEYS:
        payload[key] = {
            "label": searched[key]["label"],
            "selected": searched[key]["selected"],
            "summary": searched[key]["summary"],
        }
    _persist(payload)
    return payload


def _persist(payload: dict[str, Any]) -> None:
    root = experiment_dir()
    body = {k: payload[k] for k in payload if k not in {"ledgers", "grid"}}
    write_json(root / "MANIFEST.json", body)
    write_json(root / "statistics.json", payload["books"])
    write_json(root / "houston.json", houston_identity())
    write_json(root / "selected.json", payload["selected"])
    write_json(root / "loser_exam.json", payload["loser_exam"])
    write_json(root / "grid.json", payload["grid"])
    write_json(root / "ledgers.json", payload["ledgers"])
    (root / "REPORT.md").write_text(_report_md(payload), encoding="utf-8")


def _fmt_cell(cell: dict[str, Any] | None) -> str:
    if not cell:
        return "NONE"
    if cell.get("status") == "NONE":
        best = cell.get("best_nonpositive") or {}
        return (
            f"NONE (best Δsum={best.get('delta_sum_cents')} at {best.get('price_lo')}–{best.get('price_hi')} "
            f"EV<{best.get('austin_ev_lt')})"
        )
    return (
        f"{cell.get('price_lo')}–{cell.get('price_hi')} / EV<{cell.get('austin_ev_lt')} "
        f"hedge={cell.get('n_hedge')} (L{cell.get('n_hedge_losers')}/W{cell.get('n_hedge_winners')}) "
        f"Δmean={cell.get('delta_mean_cents')} Δsum={cell.get('delta_sum_cents')}"
    )


def _fmt_exam(exam: dict[str, Any]) -> list[str]:
    losers = exam.get("losers") or {}
    winners = exam.get("winners") or {}
    return [
        f"reached={exam.get('n_reached')} losers={losers.get('n')} winners={winners.get('n')}",
        (
            f"losers open≥41={losers.get('n_open_ge_41')} already<41={losers.get('n_already_lt_41')} "
            f"t40_already={losers.get('n_t40_already_at_mark')} terminal t40={losers.get('n_t40_terminal')}"
        ),
        f"loser price mean/median {losers.get('price', {}).get('mean')}/{losers.get('price', {}).get('median')} buckets={losers.get('price_buckets')}",
        f"winner price mean/median {winners.get('price', {}).get('mean')}/{winners.get('price', {}).get('median')} buckets={winners.get('price_buckets')}",
        f"loser Austin EV n/mean {losers.get('ev', {}).get('n')}/{losers.get('ev', {}).get('mean')} unavailable={losers.get('n_ev_unavailable')}",
        f"winner Austin EV n/mean {winners.get('ev', {}).get('n')}/{winners.get('ev', {}).get('mean')} unavailable={winners.get('n_ev_unavailable')}",
        f"loser score-diff n/mean {losers.get('score_differential', {}).get('n')}/{losers.get('score_differential', {}).get('mean')}",
    ]


def _report_md(payload: dict[str, Any]) -> str:
    lines = [
        "KATY TEXAS — EXPERIMENT 5",
        TITLE.upper(),
        "",
        "RESEARCH ONLY",
        "CANDLE PATH ≠ FILL",
        "CONFIRMATION UNSPENT",
        "AUSTIN NOT REFIT",
        "SEARCH ≠ FREEZE",
        "EXECUTION DISABLED",
        "",
        "# 1. QUESTION",
        "",
        payload["question"],
        "",
        "2H last 10: NBA Q4 12:00 converted to that label. NCAAB 2H 10:00.",
        "NBA books are locked 314 / 290. NCAAB Austin is Discovery (96 / 69). Confirmation sealed.",
        "Grid declared before selection. Houston lock is yes_bid − 80.",
        "",
        "# 2. LOSER EXAM AT 2H LAST 10",
        "",
    ]
    for key in BOOK_KEYS:
        lines.append(f"## {LABELS[key]}")
        lines.extend(_fmt_exam(payload["loser_exam"][key]))
        lines.append("")
    lines.extend(["# 3. SELECTED CELLS (PER BOOK)", ""])
    for key in BOOK_KEYS:
        lines.append(f"{LABELS[key]}: {_fmt_cell(payload['selected'][key])}")
    lines.extend(["", "# 4. MIXED 80/40 UNDER SELECTED CELL OR NONE", ""])
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
            "In-sample search. Not confirmation. Not a fill. Not a frozen policy.",
            "Books are never combined. NCAAB Discovery is not the locked 193/139 tape.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def load_v5() -> dict[str, Any] | None:
    manifest = load_json(experiment_dir() / "MANIFEST.json", required=False)
    if not manifest:
        return None
    ledgers = load_json(experiment_dir() / "ledgers.json", required=False) or {}
    grid = load_json(experiment_dir() / "grid.json", required=False) or {}
    return {**manifest, "ledgers": ledgers, "grid": grid}


def handle_v5() -> dict[str, Any]:
    payload = load_v5()
    if payload:
        return payload
    return build_v5()
